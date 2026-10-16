"""Compiled 12-node LangGraph StateGraph with checkpointing and approval resumption."""

from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.edges import (
    route_after_approval_gate,
    route_after_cost_estimator,
    route_after_query_executor,
    route_after_request_analyzer,
    route_after_result_validator,
    route_after_sql_validator,
)
from app.graph.nodes import (
    analysis_agent_node,
    approval_gate_node,
    cost_estimator_node,
    query_executor_node,
    query_planner_node,
    request_analyzer_node,
    response_generator_node,
    result_validator_node,
    schema_discovery_node,
    sql_generator_node,
    sql_validator_node,
    visualization_builder_node,
)
from app.graph.state import LANGGRAPH_NODES_METADATA, QueryPilotState
from app.safety.cost_estimator import compute_context_fingerprint, is_approval_valid

# Shared checkpointer and in-memory state store + execution lock for idempotency
_CHECKPOINTER = MemorySaver()
_STATE_CACHE: Dict[str, QueryPilotState] = {}
_EXECUTION_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def _get_query_lock(query_id: str) -> threading.Lock:
    with _GLOBAL_LOCK:
        if query_id not in _EXECUTION_LOCKS:
            _EXECUTION_LOCKS[query_id] = threading.Lock()
        return _EXECUTION_LOCKS[query_id]


def _extract_edges_from_trace(trace: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    edges: List[Dict[str, str]] = []
    for idx in range(len(trace) - 1):
        edges.append(
            {
                "source": trace[idx]["node_id"],
                "target": trace[idx + 1]["node_id"],
            }
        )
    return edges


def build_querypilot_graph() -> StateGraph:
    """Build the 12-node QueryPilot LangGraph StateGraph."""
    builder = StateGraph(QueryPilotState)

    # Register all 12 specialized nodes
    builder.add_node("request_analyzer", request_analyzer_node)
    builder.add_node("schema_discovery", schema_discovery_node)
    builder.add_node("query_planner", query_planner_node)
    builder.add_node("sql_generator", sql_generator_node)
    builder.add_node("sql_validator", sql_validator_node)
    builder.add_node("cost_estimator", cost_estimator_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("query_executor", query_executor_node)
    builder.add_node("result_validator", result_validator_node)
    builder.add_node("analysis_agent", analysis_agent_node)
    builder.add_node("visualization_builder", visualization_builder_node)
    builder.add_node("response_generator", response_generator_node)

    # Entry edge
    builder.add_edge(START, "request_analyzer")

    # Conditional edge 1: Request Analyzer -> Schema Discovery OR Response Generator
    builder.add_conditional_edges(
        "request_analyzer",
        route_after_request_analyzer,
        {
            "schema_discovery": "schema_discovery",
            "response_generator": "response_generator",
        },
    )

    # Linear planning & generation edges
    builder.add_edge("schema_discovery", "query_planner")
    builder.add_edge("query_planner", "sql_generator")
    builder.add_edge("sql_generator", "sql_validator")

    # Conditional edge 2: SQL Validator -> Cost Estimator OR SQL Generator (retry) OR Response Generator
    builder.add_conditional_edges(
        "sql_validator",
        route_after_sql_validator,
        {
            "cost_estimator": "cost_estimator",
            "sql_generator": "sql_generator",
            "response_generator": "response_generator",
        },
    )

    # Conditional edge 3: Cost Estimator -> Approval Gate OR Query Executor OR SQL Generator
    builder.add_conditional_edges(
        "cost_estimator",
        route_after_cost_estimator,
        {
            "approval_gate": "approval_gate",
            "query_executor": "query_executor",
            "sql_generator": "sql_generator",
            "response_generator": "response_generator",
        },
    )

    # Conditional edge 4: Approval Gate -> Query Executor OR Response Generator OR END (interrupt pause)
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval_gate,
        {
            "query_executor": "query_executor",
            "response_generator": "response_generator",
            END: END,
        },
    )

    # Conditional edge 5: Query Executor -> Result Validator OR SQL Generator (retry) OR Response Generator
    builder.add_conditional_edges(
        "query_executor",
        route_after_query_executor,
        {
            "result_validator": "result_validator",
            "sql_generator": "sql_generator",
            "response_generator": "response_generator",
            END: END,
        },
    )

    # Conditional edge 6: Result Validator -> Analysis Agent OR SQL Generator (retry)
    builder.add_conditional_edges(
        "result_validator",
        route_after_result_validator,
        {
            "analysis_agent": "analysis_agent",
            "sql_generator": "sql_generator",
        },
    )

    # Final synthesis pipeline
    builder.add_edge("analysis_agent", "visualization_builder")
    builder.add_edge("visualization_builder", "response_generator")
    builder.add_edge("response_generator", END)

    return builder


_COMPILED_GRAPH = build_querypilot_graph().compile(checkpointer=_CHECKPOINTER)


def build_resume_graph() -> Any:
    """Build a subgraph starting at approval_gate for resuming checkpointed interrupts."""
    builder = StateGraph(QueryPilotState)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("sql_generator", sql_generator_node)
    builder.add_node("sql_validator", sql_validator_node)
    builder.add_node("cost_estimator", cost_estimator_node)
    builder.add_node("query_executor", query_executor_node)
    builder.add_node("result_validator", result_validator_node)
    builder.add_node("analysis_agent", analysis_agent_node)
    builder.add_node("visualization_builder", visualization_builder_node)
    builder.add_node("response_generator", response_generator_node)

    builder.add_edge(START, "approval_gate")
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval_gate,
        {
            "query_executor": "query_executor",
            "response_generator": "response_generator",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "query_executor",
        route_after_query_executor,
        {
            "result_validator": "result_validator",
            "sql_generator": "sql_generator",
            "response_generator": "response_generator",
            END: END,
        },
    )
    builder.add_edge("sql_generator", "sql_validator")
    builder.add_conditional_edges(
        "sql_validator",
        route_after_sql_validator,
        {
            "cost_estimator": "cost_estimator",
            "sql_generator": "sql_generator",
            "response_generator": "response_generator",
        },
    )
    builder.add_conditional_edges(
        "cost_estimator",
        route_after_cost_estimator,
        {
            "approval_gate": "approval_gate",
            "query_executor": "query_executor",
            "sql_generator": "sql_generator",
            "response_generator": "response_generator",
        },
    )
    builder.add_conditional_edges(
        "result_validator",
        route_after_result_validator,
        {
            "analysis_agent": "analysis_agent",
            "sql_generator": "sql_generator",
        },
    )
    builder.add_edge("analysis_agent", "visualization_builder")
    builder.add_edge("visualization_builder", "response_generator")
    builder.add_edge("response_generator", END)
    return builder.compile(checkpointer=_CHECKPOINTER)


_RESUME_GRAPH = build_resume_graph()


def run_querypilot_workflow(
    question: str,
    thread_id: Optional[str] = None,
    query_id: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    force_provider: Optional[str] = None,
    cost_threshold_override: Optional[float] = None,
    seed_invalid_sql: Optional[str] = None,
    seed_db_error_sql: Optional[str] = None,
) -> QueryPilotState:
    """Run the 12-node QueryPilot workflow from START and persist checkpoint state."""
    qid = query_id or f"qp_{uuid.uuid4().hex[:12]}"
    tid = thread_id or f"thread_{uuid.uuid4().hex[:10]}"

    initial_state: QueryPilotState = {
        "query_id": qid,
        "thread_id": tid,
        "question": question,
        "conversation_history": conversation_history or [],
        "dialect": "postgresql",
        "force_provider": force_provider,
        "cost_threshold_override": cost_threshold_override,
        "seed_invalid_sql": seed_invalid_sql,
        "seed_db_error_sql": seed_db_error_sql,
        "sql_retry_count": 0,
        "exec_retry_count": 0,
        "result_retry_count": 0,
        "generation_attempts": 0,
        "approval_status": "not_required",
        "approval_fingerprint": "",
        "approval_executed": False,
        "reviewer_comment": None,
        "feedback_errors": [],
        "trace": [],
        "edges_traversed": [],
        "model_calls": 0,
        "tool_calls": 0,
        "total_latency_ms": 0.0,
        "status": "running",
        "error_message": None,
    }

    config = {"configurable": {"thread_id": qid}}
    final_state: QueryPilotState = _COMPILED_GRAPH.invoke(initial_state, config=config)
    final_state["edges_traversed"] = _extract_edges_from_trace(final_state.get("trace", []))
    _STATE_CACHE[qid] = final_state
    return final_state


def get_cached_workflow_state(query_id: str) -> Optional[QueryPilotState]:
    """Return cached workflow state by query_id."""
    return _STATE_CACHE.get(query_id)


def invalidate_workflow_approval(
    query_id: str,
    new_sql: Optional[str] = None,
    new_thread_id: Optional[str] = None,
) -> Optional[QueryPilotState]:
    """
    Invalidate an existing approval if SQL or execution context changes.
    """
    state = _STATE_CACHE.get(query_id)
    if not state:
        return None
    sql_to_check = new_sql if new_sql is not None else state.get("generated_sql", "")
    thread_to_check = new_thread_id if new_thread_id is not None else state.get("thread_id", "")
    schema_version = (state.get("discovered_schema") or {}).get("schema_version", "")

    new_fp = compute_context_fingerprint(
        normalized_sql=sql_to_check,
        dialect="postgresql",
        schema_version=schema_version,
        thread_context=thread_to_check,
    )
    if new_fp != state.get("approval_fingerprint", ""):
        state["approval_status"] = "invalidated"
        state["approval_executed"] = False
        state["status"] = "awaiting_approval"
        if new_sql is not None:
            state["generated_sql"] = new_sql
        if new_thread_id is not None:
            state["thread_id"] = new_thread_id
        _STATE_CACHE[query_id] = state
    return state


def resume_querypilot_approval(
    query_id: str,
    decision: str,
    reviewer_comment: Optional[str] = None,
    expected_sql: Optional[str] = None,
) -> QueryPilotState:
    """
    Resume a paused QueryPilot workflow from the Approval Gate checkpoint.
    Enforces:
    1. Atomic per-query lock to prevent concurrent duplicate execution.
    2. Rejects duplicate execution if already executed/completed.
    3. Invalidates approval if SQL or execution context fingerprint changed.
    """
    lock = _get_query_lock(query_id)
    with lock:
        saved = _STATE_CACHE.get(query_id)
        if not saved:
            raise KeyError(f"Query '{query_id}' not found in checkpoint store.")

        if saved.get("approval_executed", False) or saved.get("status") == "completed":
            raise RuntimeError(
                f"Duplicate execution prevented: query '{query_id}' has already been executed."
            )

        if saved.get("approval_status") == "rejected" and saved.get("status") == "rejected":
            raise RuntimeError(
                f"Query '{query_id}' was already rejected and terminated."
            )

        # If caller provides expected_sql (or if SQL in state was modified), verify fingerprint
        sql_to_verify = expected_sql if expected_sql is not None else saved.get("generated_sql", "")
        schema_version = (saved.get("discovered_schema") or {}).get("schema_version", "")
        current_fp = compute_context_fingerprint(
            normalized_sql=sql_to_verify,
            dialect="postgresql",
            schema_version=schema_version,
            thread_context=saved.get("thread_id", ""),
        )

        if current_fp != saved.get("approval_fingerprint", ""):
            saved["approval_status"] = "invalidated"
            saved["status"] = "awaiting_approval"
            saved["error_message"] = (
                "Approval invalidated because SQL or execution context changed since cost estimation."
            )
            _STATE_CACHE[query_id] = saved
            raise ValueError(saved["error_message"])

        normalized_decision = decision.strip().lower()
        if normalized_decision not in ("approve", "approved", "reject", "rejected"):
            raise ValueError("Decision must be 'approved' or 'rejected'.")

        new_app_status = "approved" if normalized_decision.startswith("approve") else "rejected"
        resumed_input: QueryPilotState = {
            **saved,
            "approval_status": new_app_status,
            "reviewer_comment": reviewer_comment,
        }

        config = {"configurable": {"thread_id": f"{query_id}_resume"}}
        final_state: QueryPilotState = _RESUME_GRAPH.invoke(resumed_input, config=config)
        final_state["edges_traversed"] = _extract_edges_from_trace(final_state.get("trace", []))
        _STATE_CACHE[query_id] = final_state
        return final_state


def get_graph_topology() -> Dict[str, Any]:
    """Return canonical 12-node metadata and conditional edges for the React Flow Execution Trace."""
    return {
        "nodes": LANGGRAPH_NODES_METADATA,
        "edges": [
            {"source": "request_analyzer", "target": "schema_discovery", "label": "Clear Intent"},
            {"source": "request_analyzer", "target": "response_generator", "label": "Ambiguous / Out of Scope"},
            {"source": "schema_discovery", "target": "query_planner", "label": "Schema + Metrics"},
            {"source": "query_planner", "target": "sql_generator", "label": "Analytical Plan"},
            {"source": "sql_generator", "target": "sql_validator", "label": "Candidate SQL"},
            {"source": "sql_validator", "target": "cost_estimator", "label": "Valid & Safe"},
            {"source": "sql_validator", "target": "sql_generator", "label": "Invalid SQL (sql_retry)"},
            {"source": "sql_validator", "target": "response_generator", "label": "Unsafe / Retries Exhausted"},
            {"source": "cost_estimator", "target": "approval_gate", "label": "High Cost / Risk"},
            {"source": "cost_estimator", "target": "query_executor", "label": "Low/Medium Cost"},
            {"source": "approval_gate", "target": "query_executor", "label": "Approved & Verified"},
            {"source": "approval_gate", "target": "response_generator", "label": "Rejected"},
            {"source": "query_executor", "target": "result_validator", "label": "Rows Returned"},
            {"source": "query_executor", "target": "sql_generator", "label": "DB Error (exec_retry)"},
            {"source": "query_executor", "target": "response_generator", "label": "DB Retries Exhausted"},
            {"source": "result_validator", "target": "analysis_agent", "label": "Validated Results"},
            {"source": "result_validator", "target": "sql_generator", "label": "Result Anomaly (result_retry)"},
            {"source": "analysis_agent", "target": "visualization_builder", "label": "Rankings & KPIs"},
            {"source": "visualization_builder", "target": "response_generator", "label": "Chart Spec"},
        ],
    }
