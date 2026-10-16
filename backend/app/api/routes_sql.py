"""SQL Inspector endpoints: structural validation, cost estimation, and safe re-validated execution."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db.engine import execute_readonly_query
from app.db.persistence import get_persisted_state, save_workflow_state
from app.graph.workflow import (
    _STATE_CACHE,
    get_cached_workflow_state,
    invalidate_workflow_approval,
)
from app.llm.base import get_llm_provider
from app.safety.cost_estimator import estimate_query_cost, is_approval_valid
from app.safety.sql_validator import validate_sql
from app.semantic.schema_inspector import discover_schema
from app.services.analyzer import analyze_query_results
from app.services.visualizer import build_visualization_spec

router = APIRouter(tags=["sql"])


class SQLValidateRequest(BaseModel):
    sql: str = Field(..., description="SQL query to validate structurally via SQLGlot")
    dialect: str = Field(default="postgresql")
    max_rows: Optional[int] = Field(default=None)


class SQLCostRequest(BaseModel):
    sql: str = Field(..., description="SQL query to estimate cost via EXPLAIN")
    thread_id: str = Field(default="")
    cost_threshold_override: Optional[float] = Field(default=None)


class SQLExecuteRequest(BaseModel):
    sql: str = Field(..., description="User-edited SQL query to revalidate and execute safely")
    query_id: Optional[str] = Field(default=None, description="Optional existing query_id being edited")
    question: Optional[str] = Field(default=None, description="Associated business question")
    thread_id: Optional[str] = Field(default=None)
    cost_threshold_override: Optional[float] = Field(default=None)


@router.post("/api/v1/sql/validate")
def api_validate_sql(payload: SQLValidateRequest) -> Dict[str, Any]:
    """Validate SQL syntax, read-only AST rules, CTEs, functions, and schema identifiers."""
    schema_info = discover_schema()
    return validate_sql(
        sql=payload.sql,
        schema_info=schema_info,
        dialect=payload.dialect,
        max_rows=payload.max_rows,
    )


@router.post("/api/v1/sql/cost")
def api_estimate_sql_cost(payload: SQLCostRequest) -> Dict[str, Any]:
    """Validate SQL first, then run non-executing EXPLAIN plan and evaluate risk policy."""
    schema_info = discover_schema()
    val = validate_sql(sql=payload.sql, schema_info=schema_info)
    if not val["is_valid"]:
        return {
            "is_valid": False,
            "validation": val,
            "cost_estimate": None,
        }
    cost = estimate_query_cost(
        sql=val["normalized_sql"],
        schema_info=schema_info,
        thread_context=payload.thread_id,
        cost_threshold=payload.cost_threshold_override,
    )
    return {
        "is_valid": True,
        "validation": val,
        "cost_estimate": cost,
    }


@router.post("/api/v1/sql/execute")
def api_execute_sql(payload: SQLExecuteRequest) -> Dict[str, Any]:
    """
    Revalidate user-edited SQL, invalidate any prior approval if SQL or context changed,
    enforce cost/risk approval policy, and execute via the read-only database role.
    """
    schema_info = discover_schema()
    qid = payload.query_id or f"qp_sql_{uuid.uuid4().hex[:10]}"
    existing_state = (
        get_cached_workflow_state(qid) or get_persisted_state(qid) or {}
    )
    tid = payload.thread_id or existing_state.get("thread_id") or f"thread_{uuid.uuid4().hex[:8]}"
    question = payload.question or existing_state.get("question") or "Interactive SQL Query"

    # 1. Always revalidate user-edited SQL before execution
    val = validate_sql(sql=payload.sql, schema_info=schema_info)
    if not val["is_valid"]:
        if payload.query_id:
            invalidate_workflow_approval(payload.query_id, new_sql=payload.sql, new_thread_id=tid)
        status = "blocked" if not val["is_safe"] else "error"
        err_state: Dict[str, Any] = {
            **existing_state,
            "query_id": qid,
            "thread_id": tid,
            "question": question,
            "generated_sql": payload.sql,
            "validation_result": val,
            "approval_status": "invalidated" if existing_state.get("approval_status") == "approved" else "not_required",
            "approval_fingerprint": "",
            "approval_executed": False,
            "status": status,
            "error_message": "; ".join(val["errors"]),
            "response": {
                "headline": "SQL Validation Failed",
                "summary": "; ".join(val["errors"]),
                "key_findings": val["errors"],
                "assumptions": ["User-edited SQL is always revalidated structurally before execution."],
                "limitations": ["Query was rejected prior to database execution."],
                "follow_up_suggestions": [],
                "sql_reference": payload.sql,
            },
        }
        _STATE_CACHE[qid] = err_state  # type: ignore[assignment]
        save_workflow_state(err_state)
        return err_state

    norm_sql = val["normalized_sql"]

    # 2. Estimate query cost & compute context fingerprint
    cost = estimate_query_cost(
        sql=norm_sql,
        schema_info=schema_info,
        thread_context=tid,
        cost_threshold=payload.cost_threshold_override,
    )
    current_fp = cost["context_fingerprint"]

    # 3. Check whether an existing approval is still valid for this exact fingerprint
    prior_approval_record = {
        "status": existing_state.get("approval_status"),
        "executed": bool(existing_state.get("approval_executed", False)),
        "context_fingerprint": existing_state.get("approval_fingerprint", ""),
    }
    approval_still_valid = is_approval_valid(prior_approval_record, current_fp)

    # If the query requires approval and no valid matching approval exists, pause at Approval Gate
    if cost["requires_approval"] and not approval_still_valid:
        paused_state: Dict[str, Any] = {
            **existing_state,
            "query_id": qid,
            "thread_id": tid,
            "question": question,
            "discovered_schema": schema_info,
            "generated_sql": norm_sql,
            "validation_result": val,
            "cost_estimate": cost,
            "approval_status": "pending",
            "approval_fingerprint": current_fp,
            "approval_executed": False,
            "execution_result": None,
            "status": "awaiting_approval",
            "response": {
                "headline": "Edited SQL Paused for High-Cost Approval",
                "summary": cost.get("approval_reason") or "Query exceeds cost policy threshold and requires review.",
                "key_findings": cost.get("approval_reasons", []),
                "assumptions": ["Prior approvals were invalidated when the SQL or context changed."],
                "limitations": ["Awaiting human reviewer approval in the Approval Queue."],
                "follow_up_suggestions": [],
                "sql_reference": norm_sql,
            },
        }
        _STATE_CACHE[qid] = paused_state  # type: ignore[assignment]
        save_workflow_state(paused_state)
        return paused_state

    # 4. Safe read-only execution
    exec_res = execute_readonly_query(sql=norm_sql)
    rows = exec_res["rows"]
    columns = exec_res["columns"]
    analysis = analyze_query_results(rows=rows, columns=columns, question=question)
    viz = build_visualization_spec(rows=rows, columns=columns, analysis=analysis, question=question)
    llm = get_llm_provider()
    resp = llm.generate_response(
        question=question,
        sql=norm_sql,
        rows=rows,
        analysis=analysis,
        intent=existing_state.get("intent") or {},
    )
    resp["sql_reference"] = norm_sql

    completed_state: Dict[str, Any] = {
        **existing_state,
        "query_id": qid,
        "thread_id": tid,
        "question": question,
        "discovered_schema": schema_info,
        "generated_sql": norm_sql,
        "validation_result": val,
        "cost_estimate": cost,
        "approval_status": "approved" if cost["requires_approval"] else "not_required",
        "approval_fingerprint": current_fp,
        "approval_executed": True if cost["requires_approval"] else False,
        "execution_result": exec_res,
        "analysis": analysis,
        "visualization": viz,
        "response": resp,
        "status": "completed",
        "error_message": None,
    }
    _STATE_CACHE[qid] = completed_state  # type: ignore[assignment]
    save_workflow_state(completed_state)
    return completed_state
