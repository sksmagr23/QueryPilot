"""Natural-language analytics query, result retrieval, and CSV export endpoints."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db.persistence import get_persisted_state, save_workflow_state
from app.graph.workflow import get_cached_workflow_state, run_querypilot_workflow

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language business question")
    thread_id: Optional[str] = Field(default=None, description="Conversation thread ID for follow-up context")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default=None)
    force_provider: Optional[str] = Field(default=None, description="Optional override: 'gemini' or 'mock'")
    cost_threshold_override: Optional[float] = Field(default=None)


@router.post("/api/v1/query")
def execute_analytics_query(payload: QueryRequest) -> Dict[str, Any]:
    """Run a natural-language business question through the 12-node QueryPilot LangGraph workflow."""
    state = run_querypilot_workflow(
        question=payload.question,
        thread_id=payload.thread_id,
        conversation_history=payload.conversation_history,
        force_provider=payload.force_provider,
        cost_threshold_override=payload.cost_threshold_override,
    )
    save_workflow_state(dict(state))
    return dict(state)


@router.get("/api/v1/query/{query_id}")
def get_query_result(query_id: str) -> Dict[str, Any]:
    """Fetch a stored query analysis by query_id."""
    persisted = get_persisted_state(query_id)
    if persisted:
        return persisted
    cached = get_cached_workflow_state(query_id)
    if cached:
        return dict(cached)
    raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")


@router.get("/api/v1/query/{query_id}/export")
def export_query_results_csv(query_id: str) -> StreamingResponse:
    """Export the validated query results for a given query_id as a downloadable CSV file."""
    state = get_persisted_state(query_id) or get_cached_workflow_state(query_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")

    exec_res = state.get("execution_result") or {}
    columns: List[str] = exec_res.get("columns") or []
    rows: List[Dict[str, Any]] = exec_res.get("rows") or []

    output = io.StringIO()
    writer = csv.writer(output)
    if columns:
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(col, "") for col in columns])

    output.seek(0)
    filename = f"querypilot_{query_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
