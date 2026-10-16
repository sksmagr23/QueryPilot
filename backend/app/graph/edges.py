"""Conditional routing functions for QueryPilot's 12-node LangGraph StateGraph."""

from __future__ import annotations

from langgraph.graph import END

from app.config import get_settings
from app.graph.state import QueryPilotState

MAX_TOTAL_GENERATIONS = 4


def route_after_request_analyzer(state: QueryPilotState) -> str:
    """Route ambiguous, out-of-scope, or unsafe requests directly to Response Generator."""
    intent = state.get("intent") or {}
    scope_status = intent.get("scope_status", "in_scope")
    if intent.get("is_ambiguous") or scope_status in ("ambiguous", "missing_schema", "unsafe_request"):
        return "response_generator"
    return "schema_discovery"


def route_after_sql_validator(state: QueryPilotState) -> str:
    """Route valid SQL to Cost Estimator, invalid safe SQL to bounded regeneration, unsafe SQL to Response Generator."""
    settings = get_settings()
    val_res = state.get("validation_result") or {}
    if val_res.get("is_valid"):
        return "cost_estimator"
    if not val_res.get("is_safe", True):
        return "response_generator"

    sql_retries = int(state.get("sql_retry_count", 0))
    gen_attempts = int(state.get("generation_attempts", 0))
    if sql_retries <= settings.max_sql_retries and gen_attempts < MAX_TOTAL_GENERATIONS:
        return "sql_generator"
    return "response_generator"


def route_after_cost_estimator(state: QueryPilotState) -> str:
    """Route expensive queries to Approval Gate, normal queries to Query Executor, or EXPLAIN errors to retry."""
    settings = get_settings()
    cost_est = state.get("cost_estimate") or {}
    if cost_est.get("error"):
        exec_retries = int(state.get("exec_retry_count", 0))
        gen_attempts = int(state.get("generation_attempts", 0))
        if exec_retries <= settings.max_exec_retries and gen_attempts < MAX_TOTAL_GENERATIONS:
            return "sql_generator"
        return "response_generator"

    if cost_est.get("requires_approval"):
        return "approval_gate"
    return "query_executor"


def route_after_approval_gate(state: QueryPilotState) -> str:
    """
    Pause graph execution at checkpoint when pending/invalidated,
    proceed to Query Executor when approved with valid fingerprint,
    or terminate safely at Response Generator when rejected.
    """
    app_status = state.get("approval_status", "pending")
    if app_status == "approved":
        return "query_executor"
    if app_status == "rejected":
        return "response_generator"
    return END


def route_after_query_executor(state: QueryPilotState) -> str:
    """Route successful execution to Result Validator, invalidated approval to END, or DB errors to bounded retry."""
    if state.get("approval_status") == "invalidated":
        return END

    settings = get_settings()
    exec_res = state.get("execution_result") or {}
    if exec_res.get("error"):
        exec_retries = int(state.get("exec_retry_count", 0))
        gen_attempts = int(state.get("generation_attempts", 0))
        if exec_retries <= settings.max_exec_retries and gen_attempts < MAX_TOTAL_GENERATIONS:
            return "sql_generator"
        return "response_generator"
    return "result_validator"


def route_after_result_validator(state: QueryPilotState) -> str:
    """Route recoverable result anomalies to SQL Generator (bounded by max_result_retries), else Analysis Agent."""
    settings = get_settings()
    res_val = state.get("result_validation") or {}
    result_retries = int(state.get("result_retry_count", 0))
    gen_attempts = int(state.get("generation_attempts", 0))

    if (
        res_val.get("needs_regeneration")
        and result_retries <= settings.max_result_retries
        and gen_attempts < MAX_TOTAL_GENERATIONS
    ):
        return "sql_generator"
    return "analysis_agent"
