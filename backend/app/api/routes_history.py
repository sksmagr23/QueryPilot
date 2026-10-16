"""Query history, saved analyses bookmarking, and LangGraph execution trace endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.persistence import (
    delete_history_item,
    get_persisted_state,
    list_query_history,
    toggle_bookmark,
)
from app.graph.workflow import get_cached_workflow_state, get_graph_topology

router = APIRouter(tags=["history", "traces"])


class BookmarkRequest(BaseModel):
    bookmarked: Optional[bool] = None
    title: Optional[str] = None


@router.get("/api/v1/history")
def api_list_history(
    bookmarked_only: bool = False,
    search: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List previous analyses and saved/bookmarked queries."""
    items = list_query_history(bookmarked_only=bookmarked_only, search=search, limit=limit)
    return {
        "count": len(items),
        "items": items,
    }


@router.post("/api/v1/history/{query_id}/bookmark")
def api_toggle_bookmark(query_id: str, payload: BookmarkRequest) -> Dict[str, Any]:
    """Bookmark or unbookmark an analysis and optionally rename its title."""
    updated = toggle_bookmark(
        query_id=query_id,
        bookmarked=payload.bookmarked,
        title=payload.title,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")
    return updated


@router.delete("/api/v1/history/{query_id}")
def api_delete_history(query_id: str) -> Dict[str, Any]:
    """Delete a query analysis from history."""
    deleted = delete_history_item(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")
    return {"deleted": True, "query_id": query_id}


@router.get("/api/v1/traces/topology/graph")
def api_get_graph_topology() -> Dict[str, Any]:
    """Return canonical 12-node LangGraph topology for React Flow visualization."""
    return get_graph_topology()


@router.get("/api/v1/traces/{query_id}")
def api_get_query_trace(query_id: str) -> Dict[str, Any]:
    """Return detailed 12-node LangGraph execution trace, retries, latencies, and traversed edges."""
    state = get_persisted_state(query_id) or get_cached_workflow_state(query_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Trace for query '{query_id}' not found.")

    topology = get_graph_topology()
    return {
        "query_id": query_id,
        "question": state.get("question"),
        "status": state.get("status"),
        "sql_retry_count": state.get("sql_retry_count", 0),
        "exec_retry_count": state.get("exec_retry_count", 0),
        "result_retry_count": state.get("result_retry_count", 0),
        "generation_attempts": state.get("generation_attempts", 0),
        "model_calls": state.get("model_calls", 0),
        "tool_calls": state.get("tool_calls", 0),
        "total_latency_ms": state.get("total_latency_ms", 0.0),
        "trace": state.get("trace", []),
        "edges_traversed": state.get("edges_traversed", []),
        "topology": topology,
    }
