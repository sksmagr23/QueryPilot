"""Implementation of all 12 specialized LangGraph nodes for QueryPilot."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.config import get_settings
from app.db.engine import execute_readonly_query
from app.graph.state import QueryPilotState
from app.llm.base import get_llm_provider
from app.safety.cost_estimator import (
    compute_context_fingerprint,
    estimate_query_cost,
    is_approval_valid,
)
from app.safety.sql_validator import validate_sql
from app.semantic.schema_inspector import discover_schema
from app.services.analyzer import analyze_query_results
from app.services.visualizer import build_visualization_spec


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_trace(
    state: QueryPilotState,
    node_id: str,
    label: str,
    status: str,
    started_at: str,
    latency_ms: float,
    summary: str,
    input_snapshot: Dict[str, Any],
    output_snapshot: Dict[str, Any],
    attempt: int = 1,
) -> List[Dict[str, Any]]:
    trace = list(state.get("trace") or [])
    trace.append(
        {
            "node_id": node_id,
            "label": label,
            "status": status,
            "started_at": started_at,
            "completed_at": _now_iso(),
            "latency_ms": round(latency_ms, 2),
            "attempt": attempt,
            "summary": summary,
            "input_snapshot": input_snapshot,
            "output_snapshot": output_snapshot,
        }
    )
    return trace


# ============================================================================
# 1. Request Analyzer
# ============================================================================
def request_analyzer_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    question = state.get("question", "")
    history = state.get("conversation_history") or []
    llm = get_llm_provider(state.get("force_provider"))

    intent = llm.analyze_request(question=question, conversation_history=history)
    elapsed = (time.perf_counter() - t0) * 1000.0

    scope_status = intent.get("scope_status", "in_scope")
    is_ambiguous = bool(intent.get("is_ambiguous", False))
    node_status = "completed"
    summary = intent.get("business_intent", "Analyzed business question.")
    if is_ambiguous or scope_status == "ambiguous":
        summary = f"Ambiguous request detected: {intent.get('clarification_question', '')}"
    elif scope_status == "missing_schema":
        summary = f"Out-of-scope schema concept: {intent.get('clarification_question', '')}"
    elif scope_status == "unsafe_request":
        summary = "Unsafe/destructive operation detected in request."

    trace = _append_trace(
        state,
        node_id="request_analyzer",
        label="1. Request Analyzer",
        status=node_status,
        started_at=started,
        latency_ms=elapsed,
        summary=summary,
        input_snapshot={"question": question, "history_turns": len(history)},
        output_snapshot=intent,
    )
    return {
        "intent": intent,
        "llm_provider_used": llm.provider_name,
        "llm_model_used": llm.model_name,
        "model_calls": int(state.get("model_calls", 0)) + 1,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }


# ============================================================================
# 2. Schema Discovery
# ============================================================================
def schema_discovery_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    intent = state.get("intent") or {}
    schema_info = discover_schema()
    elapsed = (time.perf_counter() - t0) * 1000.0

    table_names = [t["name"] for t in schema_info.get("tables", [])]
    summary = (
        f"Discovered {len(table_names)} tables ({', '.join(table_names)}), "
        f"{len(schema_info.get('relationships', []))} FK relationships, and "
        f"{len(schema_info.get('semantic_metrics', []))} semantic metrics."
    )
    trace = _append_trace(
        state,
        node_id="schema_discovery",
        label="2. Schema Discovery",
        status="completed",
        started_at=started,
        latency_ms=elapsed,
        summary=summary,
        input_snapshot={"relevant_tables": intent.get("relevant_tables", [])},
        output_snapshot={
            "tables": table_names,
            "schema_version": schema_info.get("schema_version"),
            "relationship_count": len(schema_info.get("relationships", [])),
        },
    )
    return {
        "discovered_schema": schema_info,
        "tool_calls": int(state.get("tool_calls", 0)) + 1,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }


# ============================================================================
# 3. Query Planner
# ============================================================================
def query_planner_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    question = state.get("question", "")
    intent = state.get("intent") or {}
    schema_info = state.get("discovered_schema") or {}
    llm = get_llm_provider(state.get("force_provider"))

    plan = llm.plan_query(question=question, intent=intent, schema_info=schema_info)
    elapsed = (time.perf_counter() - t0) * 1000.0

    trace = _append_trace(
        state,
        node_id="query_planner",
        label="3. Query Planner",
        status="completed",
        started_at=started,
        latency_ms=elapsed,
        summary=plan.get("summary", "Constructed analytical query plan."),
        input_snapshot={"metrics": intent.get("metrics"), "dimensions": intent.get("dimensions")},
        output_snapshot=plan,
    )
    return {
        "query_plan": plan,
        "model_calls": int(state.get("model_calls", 0)) + 1,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }


# ============================================================================
# 4. SQL Generator
# ============================================================================
def sql_generator_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    question = state.get("question", "")
    intent = state.get("intent") or {}
    plan = state.get("query_plan") or {}
    schema_info = state.get("discovered_schema") or {}
    dialect = state.get("dialect", "postgresql")
    feedback_errors = state.get("feedback_errors") or []
    prev_sql = state.get("generated_sql")
    attempt = int(state.get("generation_attempts", 0)) + 1

    llm = get_llm_provider(state.get("force_provider"))

    # Support test hook for verifying bounded self-correction on attempt 1
    if attempt == 1 and state.get("seed_invalid_sql"):
        gen_result = {
            "sql": state["seed_invalid_sql"],
            "rationale": "Initial SQL generation attempt (seeded for validation recovery test).",
            "provider": llm.provider_name,
            "model": llm.model_name,
        }
    elif attempt == 1 and state.get("seed_db_error_sql"):
        gen_result = {
            "sql": state["seed_db_error_sql"],
            "rationale": "Initial SQL generation attempt (seeded for DB error recovery test).",
            "provider": llm.provider_name,
            "model": llm.model_name,
        }
    else:
        gen_result = llm.generate_sql(
            question=question,
            intent=intent,
            query_plan=plan,
            schema_info=schema_info,
            dialect=dialect,
            feedback_errors=feedback_errors if feedback_errors else None,
            previous_sql=prev_sql,
        )

    sql = gen_result.get("sql", "")
    rationale = gen_result.get("rationale", "")
    elapsed = (time.perf_counter() - t0) * 1000.0

    # Any new SQL generation invalidates previous approvals
    prior_approval = state.get("approval_status", "not_required")
    new_approval_status = "invalidated" if prior_approval == "approved" else "not_required"

    trace = _append_trace(
        state,
        node_id="sql_generator",
        label="4. SQL Generator",
        status="completed",
        started_at=started,
        latency_ms=elapsed,
        attempt=attempt,
        summary=(
            f"Generated SQL (attempt #{attempt})"
            + (f" fixing {len(feedback_errors)} error(s)." if feedback_errors else ".")
        ),
        input_snapshot={
            "attempt": attempt,
            "feedback_errors": feedback_errors,
        },
        output_snapshot={"sql": sql, "rationale": rationale},
    )
    return {
        "generated_sql": sql,
        "sql_rationale": rationale,
        "generation_attempts": attempt,
        "approval_status": new_approval_status,
        "approval_fingerprint": "",
        "approval_executed": False,
        "model_calls": int(state.get("model_calls", 0)) + 1,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }


# ============================================================================
# 5. SQL Validator
# ============================================================================
def sql_validator_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    sql = state.get("generated_sql", "")
    schema_info = state.get("discovered_schema") or {}
    dialect = state.get("dialect", "postgresql")
    sql_retries = int(state.get("sql_retry_count", 0))

    val_res = validate_sql(sql=sql, schema_info=schema_info, dialect=dialect)
    elapsed = (time.perf_counter() - t0) * 1000.0

    is_valid = bool(val_res.get("is_valid", False))
    is_safe = bool(val_res.get("is_safe", True))
    errors = val_res.get("errors") or []

    if is_valid:
        node_status = "completed"
        summary = f"Validated read-only SELECT AST across tables: {', '.join(val_res.get('referenced_tables', []))}."
        new_sql_retries = sql_retries
        feedback: List[str] = []
        norm_sql = val_res.get("normalized_sql", sql)
    elif not is_safe:
        node_status = "blocked"
        summary = f"Blocked unsafe SQL statement: {'; '.join(errors)}"
        new_sql_retries = sql_retries
        feedback = errors
        norm_sql = sql
    else:
        node_status = "retry"
        new_sql_retries = sql_retries + 1
        summary = f"SQL validation failed (sql_retry #{new_sql_retries}): {'; '.join(errors)}"
        feedback = errors
        norm_sql = sql

    trace = _append_trace(
        state,
        node_id="sql_validator",
        label="5. SQL Validator",
        status=node_status,
        started_at=started,
        latency_ms=elapsed,
        attempt=new_sql_retries + 1 if not is_valid else 1,
        summary=summary,
        input_snapshot={"sql": sql},
        output_snapshot=val_res,
    )
    updates: Dict[str, Any] = {
        "validation_result": val_res,
        "generated_sql": norm_sql,
        "sql_retry_count": new_sql_retries,
        "feedback_errors": feedback,
        "tool_calls": int(state.get("tool_calls", 0)) + 1,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }
    if not is_safe:
        updates["status"] = "blocked"
        updates["error_message"] = "; ".join(errors)
    return updates


# ============================================================================
# 6. Cost Estimator
# ============================================================================
def cost_estimator_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    sql = state.get("generated_sql", "")
    schema_info = state.get("discovered_schema") or {}
    thread_id = state.get("thread_id", "")
    threshold_override = state.get("cost_threshold_override")
    exec_retries = int(state.get("exec_retry_count", 0))

    try:
        cost_res = estimate_query_cost(
            sql=sql,
            schema_info=schema_info,
            thread_context=thread_id,
            cost_threshold=threshold_override,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        summary = (
            f"Estimated cost={cost_res['estimated_cost']} (risk={cost_res['risk_level']}, "
            f"requires_approval={cost_res['requires_approval']})."
        )
        trace = _append_trace(
            state,
            node_id="cost_estimator",
            label="6. Cost Estimator",
            status="completed",
            started_at=started,
            latency_ms=elapsed,
            summary=summary,
            input_snapshot={"sql": sql},
            output_snapshot={
                "estimated_cost": cost_res["estimated_cost"],
                "estimated_rows": cost_res["estimated_rows"],
                "risk_level": cost_res["risk_level"],
                "requires_approval": cost_res["requires_approval"],
                "context_fingerprint": cost_res["context_fingerprint"],
            },
        )
        return {
            "cost_estimate": cost_res,
            "tool_calls": int(state.get("tool_calls", 0)) + 1,
            "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
            "trace": trace,
        }
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000.0
        new_exec_retries = exec_retries + 1
        err_msg = f"Database EXPLAIN error: {exc}"
        trace = _append_trace(
            state,
            node_id="cost_estimator",
            label="6. Cost Estimator",
            status="retry",
            started_at=started,
            latency_ms=elapsed,
            attempt=new_exec_retries,
            summary=err_msg,
            input_snapshot={"sql": sql},
            output_snapshot={"error": err_msg},
        )
        return {
            "cost_estimate": {"error": err_msg, "requires_approval": False},
            "exec_retry_count": new_exec_retries,
            "feedback_errors": [err_msg],
            "tool_calls": int(state.get("tool_calls", 0)) + 1,
            "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
            "trace": trace,
        }


# ============================================================================
# 7. Approval Gate
# ============================================================================
def approval_gate_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    cost_est = state.get("cost_estimate") or {}
    current_fp = cost_est.get("context_fingerprint", "")
    approval_status = state.get("approval_status", "not_required")
    recorded_fp = state.get("approval_fingerprint", "")
    already_executed = bool(state.get("approval_executed", False))

    if approval_status == "approved":
        # Verify fingerprint and single-execution idempotency
        approval_record = {
            "status": "approved",
            "executed": already_executed,
            "context_fingerprint": recorded_fp,
        }
        if is_approval_valid(approval_record, current_fp):
            node_status = "completed"
            summary = "Query approved by human reviewer and fingerprint verified."
            next_app_status = "approved"
            wf_status = state.get("status", "running")
        else:
            node_status = "blocked"
            summary = "Prior approval invalidated because SQL or execution context changed (or already executed)."
            next_app_status = "invalidated"
            wf_status = "awaiting_approval"
    elif approval_status == "rejected":
        node_status = "rejected"
        summary = f"Query execution rejected by reviewer: {state.get('reviewer_comment') or 'High cost/risk policy'}."
        next_app_status = "rejected"
        wf_status = "rejected"
    else:
        node_status = "awaiting_approval"
        summary = f"Execution paused for human approval: {cost_est.get('approval_reason') or 'High query cost'}."
        next_app_status = "pending"
        wf_status = "awaiting_approval"

    elapsed = (time.perf_counter() - t0) * 1000.0
    trace = _append_trace(
        state,
        node_id="approval_gate",
        label="7. Approval Gate",
        status=node_status,
        started_at=started,
        latency_ms=elapsed,
        summary=summary,
        input_snapshot={
            "requires_approval": cost_est.get("requires_approval"),
            "estimated_cost": cost_est.get("estimated_cost"),
            "risk_level": cost_est.get("risk_level"),
        },
        output_snapshot={
            "approval_status": next_app_status,
            "approval_fingerprint": current_fp,
            "reviewer_comment": state.get("reviewer_comment"),
        },
    )
    return {
        "approval_status": next_app_status,
        "approval_fingerprint": current_fp,
        "status": wf_status,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }


# ============================================================================
# 8. Query Executor
# ============================================================================
def query_executor_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    sql = state.get("generated_sql", "")
    schema_info = state.get("discovered_schema") or {}
    cost_est = state.get("cost_estimate") or {}
    exec_retries = int(state.get("exec_retry_count", 0))

    # Guard 1: Prevent duplicate execution of an already-executed approval
    if state.get("approval_executed", False):
        raise RuntimeError("Duplicate execution prevented: this approved query has already been executed.")

    # Guard 2: If query required approval, verify fingerprint matches current SQL & context
    if cost_est.get("requires_approval"):
        current_fp = compute_context_fingerprint(
            normalized_sql=sql,
            dialect="postgresql",
            schema_version=schema_info.get("schema_version", ""),
            thread_context=state.get("thread_id", ""),
        )
        approval_record = {
            "status": state.get("approval_status"),
            "executed": bool(state.get("approval_executed", False)),
            "context_fingerprint": state.get("approval_fingerprint", ""),
        }
        if not is_approval_valid(approval_record, current_fp):
            elapsed = (time.perf_counter() - t0) * 1000.0
            msg = "Approval invalidated: SQL or execution context changed since approval."
            trace = _append_trace(
                state,
                node_id="query_executor",
                label="8. Query Executor",
                status="blocked",
                started_at=started,
                latency_ms=elapsed,
                summary=msg,
                input_snapshot={"sql": sql},
                output_snapshot={"error": msg},
            )
            return {
                "approval_status": "invalidated",
                "status": "awaiting_approval",
                "error_message": msg,
                "trace": trace,
            }

    try:
        res = execute_readonly_query(sql=sql)
        elapsed = (time.perf_counter() - t0) * 1000.0
        summary = (
            f"Executed read-only query in {res['execution_time_ms']}ms; "
            f"returned {res['row_count']} row(s)"
            + (" (truncated to max_rows)." if res.get("truncated") else ".")
        )
        trace = _append_trace(
            state,
            node_id="query_executor",
            label="8. Query Executor",
            status="completed",
            started_at=started,
            latency_ms=elapsed,
            summary=summary,
            input_snapshot={"sql": sql},
            output_snapshot={
                "row_count": res["row_count"],
                "columns": res["columns"],
                "truncated": res["truncated"],
                "execution_time_ms": res["execution_time_ms"],
            },
        )
        return {
            "execution_result": res,
            "approval_executed": True if cost_est.get("requires_approval") else False,
            "feedback_errors": [],
            "tool_calls": int(state.get("tool_calls", 0)) + 1,
            "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
            "trace": trace,
        }
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000.0
        new_exec_retries = exec_retries + 1
        err_msg = f"Database execution error: {exc}"
        trace = _append_trace(
            state,
            node_id="query_executor",
            label="8. Query Executor",
            status="retry",
            started_at=started,
            latency_ms=elapsed,
            attempt=new_exec_retries,
            summary=f"Query execution failed (exec_retry #{new_exec_retries}): {err_msg}",
            input_snapshot={"sql": sql},
            output_snapshot={"error": err_msg},
        )
        return {
            "execution_result": {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "execution_time_ms": round(elapsed, 2),
                "error": err_msg,
            },
            "exec_retry_count": new_exec_retries,
            "feedback_errors": [err_msg],
            "tool_calls": int(state.get("tool_calls", 0)) + 1,
            "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
            "trace": trace,
        }


# ============================================================================
# 9. Result Validator
# ============================================================================
def result_validator_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    exec_res = state.get("execution_result") or {}
    rows: List[Dict[str, Any]] = exec_res.get("rows") or []
    columns: List[str] = exec_res.get("columns") or []
    result_retries = int(state.get("result_retry_count", 0))
    settings = get_settings()

    is_empty = len(rows) == 0
    has_null_anomalies = False
    unexpected_aggregation = False
    diagnostics: List[str] = []
    needs_regeneration = False

    if is_empty:
        diagnostics.append("Query returned 0 rows. Insufficient evidence for numerical claims.")
    else:
        # Check if an aggregation column is 100% NULL across returned rows
        for col in columns:
            vals = [r.get(col) for r in rows]
            if all(v is None for v in vals) and "reason" not in col.lower():
                has_null_anomalies = True
                diagnostics.append(f"Column '{col}' contains only NULL values across all {len(rows)} rows.")
            for v in vals:
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    unexpected_aggregation = True
                    diagnostics.append(f"Column '{col}' contains NaN or Inf values.")
                    break

        if (has_null_anomalies or unexpected_aggregation) and result_retries < settings.max_result_retries:
            needs_regeneration = True

    elapsed = (time.perf_counter() - t0) * 1000.0
    new_result_retries = result_retries + (1 if needs_regeneration else 0)

    res_val = {
        "is_empty": is_empty,
        "has_null_anomalies": has_null_anomalies,
        "unexpected_aggregation": unexpected_aggregation,
        "sufficient_evidence": not is_empty and not unexpected_aggregation,
        "diagnostics": diagnostics,
        "needs_regeneration": needs_regeneration,
    }
    summary = (
        "Result validation passed with sufficient evidence."
        if res_val["sufficient_evidence"]
        else f"Result diagnostics: {'; '.join(diagnostics)}"
    )
    trace = _append_trace(
        state,
        node_id="result_validator",
        label="9. Result Validator",
        status="retry" if needs_regeneration else "completed",
        started_at=started,
        latency_ms=elapsed,
        attempt=new_result_retries if needs_regeneration else 1,
        summary=summary,
        input_snapshot={"row_count": len(rows), "columns": columns},
        output_snapshot=res_val,
    )
    updates: Dict[str, Any] = {
        "result_validation": res_val,
        "result_retry_count": new_result_retries,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }
    if needs_regeneration:
        updates["feedback_errors"] = diagnostics
    return updates


# ============================================================================
# 10. Analysis Agent
# ============================================================================
def analysis_agent_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    exec_res = state.get("execution_result") or {}
    rows = exec_res.get("rows") or []
    columns = exec_res.get("columns") or []
    question = state.get("question", "")

    analysis = analyze_query_results(rows=rows, columns=columns, question=question)
    elapsed = (time.perf_counter() - t0) * 1000.0

    top_perf = analysis.get("top_performer")
    summary = (
        f"Computed rankings and statistics across {len(rows)} rows; "
        f"top performer: {top_perf['dimension']} ({top_perf['value']})."
        if top_perf
        else f"Analyzed {len(rows)} rows (no numeric metrics to rank)."
    )
    trace = _append_trace(
        state,
        node_id="analysis_agent",
        label="10. Analysis Agent",
        status="completed",
        started_at=started,
        latency_ms=elapsed,
        summary=summary,
        input_snapshot={"row_count": len(rows)},
        output_snapshot={
            "primary_dimension": analysis.get("primary_dimension"),
            "primary_metric": analysis.get("primary_metric"),
            "metric_total": analysis.get("metric_total"),
            "top_performer": top_perf,
        },
    )
    return {
        "analysis": analysis,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }


# ============================================================================
# 11. Visualization Builder
# ============================================================================
def visualization_builder_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    exec_res = state.get("execution_result") or {}
    rows = exec_res.get("rows") or []
    columns = exec_res.get("columns") or []
    analysis = state.get("analysis") or {}
    question = state.get("question", "")

    viz = build_visualization_spec(
        rows=rows,
        columns=columns,
        analysis=analysis,
        question=question,
    )
    elapsed = (time.perf_counter() - t0) * 1000.0

    trace = _append_trace(
        state,
        node_id="visualization_builder",
        label="11. Visualization Builder",
        status="completed",
        started_at=started,
        latency_ms=elapsed,
        summary=f"Built '{viz.get('chart_type')}' chart specification ({viz.get('title')}).",
        input_snapshot={"primary_dimension": analysis.get("primary_dimension"), "primary_metric": analysis.get("primary_metric")},
        output_snapshot={
            "chart_type": viz.get("chart_type"),
            "title": viz.get("title"),
            "x_key": viz.get("x_key"),
            "y_keys": viz.get("y_keys"),
        },
    )
    return {
        "visualization": viz,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }


# ============================================================================
# 12. Response Generator
# ============================================================================
def response_generator_node(state: QueryPilotState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    started = _now_iso()
    question = state.get("question", "")
    intent = state.get("intent") or {}
    scope_status = intent.get("scope_status", "in_scope")
    is_ambiguous = bool(intent.get("is_ambiguous", False))
    approval_status = state.get("approval_status", "not_required")
    val_res = state.get("validation_result") or {}
    exec_res = state.get("execution_result") or {}
    analysis = state.get("analysis") or {}
    sql = state.get("generated_sql", "")

    final_status = "completed"
    model_calls_inc = 0

    # Case A: Ambiguous question requiring clarification
    if is_ambiguous or scope_status == "ambiguous":
        final_status = "clarification_needed"
        clarification = intent.get("clarification_question") or (
            "Please clarify which metric and dimension you would like to analyze."
        )
        response_payload = {
            "headline": "Clarification Needed to Generate Accurate SQL",
            "summary": clarification,
            "key_findings": [
                "Your question could map to multiple business metrics or breakdown dimensions.",
                clarification,
            ],
            "assumptions": ["No SQL query was executed to avoid guessing your business intent."],
            "limitations": ["Awaiting user clarification on target metric and grouping dimension."],
            "follow_up_suggestions": [
                "Which product categories generate the most revenue?",
                "What is the average order value by customer segment?",
                "Which regions have the highest order cancellation rates?",
            ],
            "sql_reference": None,
        }

    # Case B: Missing schema / unsupported concept
    elif scope_status == "missing_schema":
        final_status = "blocked"
        msg = intent.get("clarification_question") or (
            "The requested data is not stored in the e-commerce warehouse schema."
        )
        response_payload = {
            "headline": "Requested Data Not Available in Warehouse Schema",
            "summary": msg,
            "key_findings": [
                msg,
                "Available warehouse tables: categories, products, customers, orders, order_items, payments, website_events.",
            ],
            "assumptions": ["QueryPilot strictly refuses to invent tables, columns, or synthetic answers."],
            "limitations": ["Schema boundary reached: requested entities are outside the e-commerce dataset."],
            "follow_up_suggestions": [
                "Which product categories generate the most revenue?",
                "Which products have declining sales?",
            ],
            "sql_reference": None,
        }

    # Case C: Unsafe request or unsafe SQL blocked by validator
    elif scope_status == "unsafe_request" or (val_res and not val_res.get("is_safe", True)):
        final_status = "blocked"
        err_list = val_res.get("errors") or [
            "Destructive, DDL/DML, system catalog, or multi-statement SQL operations are strictly prohibited."
        ]
        response_payload = {
            "headline": "Unsafe Query Blocked by SQL Safety Guardrails",
            "summary": " ".join(err_list),
            "key_findings": err_list,
            "assumptions": ["QueryPilot enforces read-only SELECT access at both AST and PostgreSQL role levels."],
            "limitations": ["Write operations, administrative commands, and dangerous functions are never executed."],
            "follow_up_suggestions": [
                "Which product categories generate the most revenue?",
                "What is the average order value by customer segment?",
            ],
            "sql_reference": sql or None,
        }

    # Case D: Rejected in Approval Queue
    elif approval_status == "rejected":
        final_status = "rejected"
        reason = state.get("reviewer_comment") or "Rejected by reviewer in the Approval Queue."
        response_payload = {
            "headline": "Query Execution Rejected by Reviewer",
            "summary": f"This high-cost query was paused by the Approval Gate and rejected: {reason}",
            "key_findings": [
                f"Reviewer decision: Rejected ({reason})",
                f"Estimated query cost was {state.get('cost_estimate', {}).get('estimated_cost', 'N/A')}.",
            ],
            "assumptions": ["Query was terminated safely without touching the database."],
            "limitations": ["No results were fetched because approval was denied."],
            "follow_up_suggestions": [
                "Try adding a date range or category filter to reduce query cost.",
            ],
            "sql_reference": sql or None,
        }

    # Case E: Exhausted SQL validation or DB execution retries
    elif (val_res and not val_res.get("is_valid", False)) or exec_res.get("error"):
        final_status = "error"
        errs = state.get("feedback_errors") or val_res.get("errors") or [exec_res.get("error", "Unknown error")]
        response_payload = {
            "headline": "Query Execution Halted After Bounded Retries",
            "summary": f"QueryPilot could not validate or execute the query after bounded retry attempts: {'; '.join(str(e) for e in errs)}",
            "key_findings": [str(e) for e in errs],
            "assumptions": ["Bounded retry limits prevented an infinite regeneration loop."],
            "limitations": ["No verified query results were produced."],
            "follow_up_suggestions": [
                "Which product categories generate the most revenue?",
                "What is the average order value by customer segment?",
            ],
            "sql_reference": sql or None,
        }

    # Case F: Successful execution -> synthesize evidence-backed insights
    else:
        llm = get_llm_provider(state.get("force_provider"))
        rows = exec_res.get("rows") or []
        gen = llm.generate_response(
            question=question,
            sql=sql,
            rows=rows,
            analysis=analysis,
            intent=intent,
        )
        model_calls_inc = 1
        response_payload = {
            **gen,
            "sql_reference": sql,
        }

    elapsed = (time.perf_counter() - t0) * 1000.0
    trace = _append_trace(
        state,
        node_id="response_generator",
        label="12. Response Generator",
        status="completed",
        started_at=started,
        latency_ms=elapsed,
        summary=response_payload.get("headline", "Generated response."),
        input_snapshot={"final_status": final_status},
        output_snapshot={
            "headline": response_payload.get("headline"),
            "findings_count": len(response_payload.get("key_findings", [])),
        },
    )
    return {
        "response": response_payload,
        "status": final_status,
        "model_calls": int(state.get("model_calls", 0)) + model_calls_inc,
        "total_latency_ms": round(float(state.get("total_latency_ms", 0.0)) + elapsed, 2),
        "trace": trace,
    }
