"""Health check and runtime LLM configuration endpoints."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.db.engine import execute_readonly_query
from app.db.seed import get_table_counts

router = APIRouter(tags=["health"])


class LLMConfigUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    llm_provider: Optional[str] = None


@router.get("/api/v1/health")
def get_health() -> Dict[str, Any]:
    """Return system, database, read-only role, and LLM provider health status."""
    settings = get_settings()
    db_ok = False
    table_counts: Dict[str, int] = {}
    try:
        ping = execute_readonly_query("SELECT 1 AS ok", max_rows=1)
        db_ok = ping["row_count"] == 1
        table_counts = get_table_counts()
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": {
            "connected": db_ok,
            "dialect": "postgresql",
            "readonly_enforced": True,
            "statement_timeout_ms": settings.statement_timeout_ms,
            "max_result_rows": settings.max_result_rows,
            "table_counts": table_counts,
        },
        "llm": {
            "configured_provider": settings.llm_provider,
            "effective_provider": settings.effective_llm_provider,
            "gemini_api_key_present": bool(settings.active_gemini_api_key),
            "gemini_model": settings.gemini_model,
            "gemini_fallback_model": settings.gemini_fallback_model,
        },
        "safety": {
            "cost_approval_threshold": settings.cost_approval_threshold,
            "max_sql_retries": settings.max_sql_retries,
            "max_exec_retries": settings.max_exec_retries,
            "max_result_retries": settings.max_result_retries,
        },
    }


@router.post("/api/v1/settings/llm")
def update_llm_settings(payload: LLMConfigUpdate) -> Dict[str, Any]:
    """Update runtime Gemini API key, model ID, or provider preference."""
    settings = get_settings()
    if payload.gemini_api_key is not None:
        cleaned_key = payload.gemini_api_key.strip()
        settings.gemini_api_key = cleaned_key
        os.environ["GEMINI_API_KEY"] = cleaned_key
    if payload.gemini_model is not None and payload.gemini_model.strip():
        settings.gemini_model = payload.gemini_model.strip()
        os.environ["GEMINI_MODEL"] = settings.gemini_model
    if payload.llm_provider is not None and payload.llm_provider.strip():
        settings.llm_provider = payload.llm_provider.strip().lower()
        os.environ["LLM_PROVIDER"] = settings.llm_provider

    return {
        "configured_provider": settings.llm_provider,
        "effective_provider": settings.effective_llm_provider,
        "gemini_api_key_present": bool(settings.active_gemini_api_key),
        "gemini_model": settings.gemini_model,
        "gemini_fallback_model": settings.gemini_fallback_model,
    }
