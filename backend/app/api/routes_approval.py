"""Human-in-the-loop Approval Queue endpoints with fingerprint verification and duplicate execution guard."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.persistence import get_persisted_state, list_approvals, save_workflow_state
from app.graph.workflow import (
    _STATE_CACHE,
    get_cached_workflow_state,
    resume_querypilot_approval,
)

router = APIRouter(tags=["approvals"])


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="'approved' or 'rejected'")
    reviewer_comment: Optional[str] = Field(default=None)
    expected_sql: Optional[str] = Field(
        default=None,
        description="Optional SQL snapshot to verify that the query was not modified after approval request",
    )


@router.get("/api/v1/approvals")
def get_approval_queue(status: Optional[str] = None) -> Dict[str, Any]:
    """List approval queue items (pending, approved, rejected, invalidated)."""
    items: List[Dict[str, Any]] = list_approvals(status_filter=status)
    pending_count = sum(1 for item in items if item["approval_status"] == "pending")
    return {
        "pending_count": pending_count,
        "items": items,
    }


@router.post("/api/v1/approvals/{query_id}/decision")
def decide_approval(query_id: str, payload: ApprovalDecisionRequest) -> Dict[str, Any]:
    """
    Approve or reject a paused query in the Approval Queue and resume the LangGraph workflow.
    Enforces:
    1. Fingerprint validation (invalidates if SQL or context changed).
    2. Single-execution idempotency (prevents duplicate execution).
    """
    # Hydrate in-memory cache from persistence if needed
    if not get_cached_workflow_state(query_id):
        persisted = get_persisted_state(query_id)
        if not persisted:
            raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")
        _STATE_CACHE[query_id] = persisted  # type: ignore[assignment]

    try:
        resumed = resume_querypilot_approval(
            query_id=query_id,
            decision=payload.decision,
            reviewer_comment=payload.reviewer_comment,
            expected_sql=payload.expected_sql,
        )
        save_workflow_state(dict(resumed))
        return dict(resumed)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        # Fingerprint mismatch -> save invalidated state and return 409 Conflict
        cached = get_cached_workflow_state(query_id)
        if cached:
            save_workflow_state(dict(cached))
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Duplicate execution prevented -> return 409 Conflict
        raise HTTPException(status_code=409, detail=str(exc)) from exc
