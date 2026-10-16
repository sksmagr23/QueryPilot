"""Database engines and database-level read-only, timeout, and row-limit execution."""

from __future__ import annotations

import time
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import Engine, create_engine, text

from app.config import get_settings


def _serialize_value(val: Any) -> Any:
    """Convert database cell values to JSON-friendly Python primitives."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


@lru_cache(maxsize=2)
def get_admin_engine(database_url: Optional[str] = None) -> Engine:
    """Return the administrative engine used strictly for DDL, seeding, and role grants."""
    settings = get_settings()
    url = database_url or settings.database_url
    return create_engine(url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=2)
def get_readonly_engine(readonly_url: Optional[str] = None) -> Engine:
    """Return the dedicated read-only engine used for all analytical queries and EXPLAIN."""
    settings = get_settings()
    url = readonly_url or settings.readonly_database_url
    return create_engine(url, pool_pre_ping=True, future=True)


def ensure_readonly_role(admin_engine: Optional[Engine] = None) -> None:
    """Ensure the PostgreSQL read-only role exists and has SELECT-only privileges on warehouse tables."""
    engine = admin_engine or get_admin_engine()
    if engine.dialect.name != "postgresql":
        return

    sql_path = Path(__file__).resolve().parent / "init_ro_role.sql"
    sql_script = sql_path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql_script)


def execute_readonly_query(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    timeout_ms: Optional[int] = None,
    max_rows: Optional[int] = None,
    engine: Optional[Engine] = None,
) -> Dict[str, Any]:
    """
    Execute a validated SQL query through the dedicated read-only connection
    with database-level read-only transaction mode, statement timeout, and driver row limit.
    """
    settings = get_settings()
    ro_engine = engine or get_readonly_engine()
    effective_timeout_ms = int(timeout_ms if timeout_ms is not None else settings.statement_timeout_ms)
    effective_max_rows = int(max_rows if max_rows is not None else settings.max_result_rows)
    if effective_max_rows <= 0:
        effective_max_rows = settings.max_result_rows

    start = time.perf_counter()
    with ro_engine.connect() as conn:
        trans = conn.begin()
        try:
            if ro_engine.dialect.name == "postgresql":
                # Enforce read-only transaction and statement timeout at the PostgreSQL database level
                conn.exec_driver_sql("SET LOCAL TRANSACTION READ ONLY")
                conn.exec_driver_sql(f"SET LOCAL statement_timeout = '{effective_timeout_ms}ms'")
                conn.exec_driver_sql("SET LOCAL lock_timeout = '2000ms'")

            result = conn.execute(text(sql), params or {})
            if not result.returns_rows:
                trans.rollback()
                raise PermissionError("Query did not return rows; non-SELECT statements are prohibited.")

            columns = list(result.keys())
            raw_rows = result.fetchmany(effective_max_rows + 1)
            truncated = len(raw_rows) > effective_max_rows
            if truncated:
                raw_rows = raw_rows[:effective_max_rows]

            rows: List[Dict[str, Any]] = [
                {col: _serialize_value(row[idx]) for idx, col in enumerate(columns)}
                for row in raw_rows
            ]
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
            trans.rollback()
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
                "max_rows_enforced": effective_max_rows,
                "timeout_ms_enforced": effective_timeout_ms,
                "execution_time_ms": elapsed_ms,
                "error": None,
            }
        except Exception:
            trans.rollback()
            raise


def run_explain_plan(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    engine: Optional[Engine] = None,
) -> Dict[str, Any]:
    """
    Run a non-executing EXPLAIN plan on the read-only connection inside a read-only transaction.
    Returns parsed plan details for PostgreSQL (EXPLAIN FORMAT JSON) or generic text plan.
    """
    ro_engine = engine or get_readonly_engine()
    with ro_engine.connect() as conn:
        trans = conn.begin()
        try:
            if ro_engine.dialect.name == "postgresql":
                conn.exec_driver_sql("SET LOCAL TRANSACTION READ ONLY")
                conn.exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
                explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
                res = conn.execute(text(explain_sql), params or {})
                plan_payload = res.scalar()
                trans.rollback()
                if isinstance(plan_payload, list) and plan_payload:
                    root = plan_payload[0].get("Plan", {})
                    return {
                        "dialect": "postgresql",
                        "raw_plan": plan_payload,
                        "total_cost": float(root.get("Total Cost", 0.0)),
                        "startup_cost": float(root.get("Startup Cost", 0.0)),
                        "plan_rows": int(root.get("Plan Rows", 0)),
                        "node_type": root.get("Node Type", "Unknown"),
                    }
                return {
                    "dialect": "postgresql",
                    "raw_plan": plan_payload,
                    "total_cost": 0.0,
                    "startup_cost": 0.0,
                    "plan_rows": 0,
                    "node_type": "Unknown",
                }
            else:
                explain_sql = f"EXPLAIN {sql}"
                res = conn.execute(text(explain_sql), params or {})
                rows = [str(r[0]) for r in res.fetchall()]
                trans.rollback()
                return {
                    "dialect": ro_engine.dialect.name,
                    "raw_plan": "\n".join(rows),
                    "total_cost": 10.0,
                    "startup_cost": 0.0,
                    "plan_rows": 100,
                    "node_type": "QueryPlan",
                }
        except Exception:
            trans.rollback()
            raise
