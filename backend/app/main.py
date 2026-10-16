"""FastAPI application entrypoint for QueryPilot — Agentic Analytics Engineer."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_approval import router as approval_router
from app.api.routes_health import router as health_router
from app.api.routes_history import router as history_router
from app.api.routes_query import router as query_router
from app.api.routes_schema import router as schema_router
from app.api.routes_sql import router as sql_router
from app.config import get_settings
from app.db.persistence import init_persistence_db
from app.db.seed import seed_warehouse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize persistence store and ensure synthetic e-commerce warehouse is seeded on startup."""
    init_persistence_db()
    try:
        seed_warehouse(force=False)
    except Exception as exc:
        print(f"[QueryPilot Startup Warning] Warehouse seed check encountered: {exc}")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="QueryPilot — Agentic Analytics Engineer API",
        description=(
            "Natural-language-to-SQL analytics platform powered by a 12-node LangGraph workflow, "
            "SQLGlot AST guardrails, non-executing EXPLAIN cost estimation, read-only PostgreSQL execution, "
            "and Gemini / deterministic Mock inference."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(query_router)
    app.include_router(sql_router)
    app.include_router(schema_router)
    app.include_router(approval_router)
    app.include_router(history_router)

    return app


app = create_app()
