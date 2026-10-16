"""Typed QueryPilotState and node metadata definitions for the 12-node LangGraph workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

LANGGRAPH_NODES_METADATA: List[Dict[str, str]] = [
    {"id": "request_analyzer", "label": "1. Request Analyzer", "category": "planning"},
    {"id": "schema_discovery", "label": "2. Schema Discovery", "category": "planning"},
    {"id": "query_planner", "label": "3. Query Planner", "category": "planning"},
    {"id": "sql_generator", "label": "4. SQL Generator", "category": "generation"},
    {"id": "sql_validator", "label": "5. SQL Validator", "category": "safety"},
    {"id": "cost_estimator", "label": "6. Cost Estimator", "category": "safety"},
    {"id": "approval_gate", "label": "7. Approval Gate", "category": "safety"},
    {"id": "query_executor", "label": "8. Query Executor", "category": "execution"},
    {"id": "result_validator", "label": "9. Result Validator", "category": "validation"},
    {"id": "analysis_agent", "label": "10. Analysis Agent", "category": "synthesis"},
    {"id": "visualization_builder", "label": "11. Visualization Builder", "category": "synthesis"},
    {"id": "response_generator", "label": "12. Response Generator", "category": "synthesis"},
]


class QueryPilotState(TypedDict, total=False):
    """Typed state flowing through the 12-node QueryPilot LangGraph StateGraph."""

    query_id: str
    thread_id: str
    question: str
    conversation_history: List[Dict[str, str]]
    dialect: str
    force_provider: Optional[str]
    cost_threshold_override: Optional[float]

    # Optional test hook to inject an initial SQL error on attempt 0 to verify self-correction
    seed_invalid_sql: Optional[str]
    seed_db_error_sql: Optional[str]

    # Separate bounded retry counters (Requirement #5)
    sql_retry_count: int
    exec_retry_count: int
    result_retry_count: int
    generation_attempts: int

    # Node 1-4 outputs
    intent: Dict[str, Any]
    discovered_schema: Dict[str, Any]
    query_plan: Dict[str, Any]
    generated_sql: str
    sql_rationale: str
    llm_provider_used: str
    llm_model_used: str
    feedback_errors: List[str]

    # Node 5-7 safety & approval outputs
    validation_result: Dict[str, Any]
    cost_estimate: Dict[str, Any]
    approval_status: str  # "not_required" | "pending" | "approved" | "rejected" | "invalidated"
    approval_fingerprint: str
    approval_executed: bool
    reviewer_comment: Optional[str]

    # Node 8-12 execution & synthesis outputs
    execution_result: Dict[str, Any]
    result_validation: Dict[str, Any]
    analysis: Dict[str, Any]
    visualization: Dict[str, Any]
    response: Dict[str, Any]

    # Observability & Telemetry
    trace: List[Dict[str, Any]]
    edges_traversed: List[Dict[str, str]]
    model_calls: int
    tool_calls: int
    total_latency_ms: float
    status: str  # "completed" | "awaiting_approval" | "clarification_needed" | "rejected" | "blocked" | "error"
    error_message: Optional[str]
