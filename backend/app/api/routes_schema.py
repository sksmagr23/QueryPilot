"""Schema discovery and semantic catalog endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.semantic.catalog import get_semantic_catalog
from app.semantic.schema_inspector import discover_schema

router = APIRouter(tags=["schema"])


@router.get("/api/v1/schema")
def get_warehouse_schema() -> Dict[str, Any]:
    """Return discovered warehouse tables, columns, data types, row counts, and FK relationships."""
    return discover_schema()


@router.get("/api/v1/schema/semantic")
def get_semantic_metrics_catalog() -> Dict[str, Any]:
    """Return canonical business metrics, SQL formulas, and verified join paths."""
    return get_semantic_catalog()
