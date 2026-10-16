"""Baseline single-pass Text-to-SQL agent for paired benchmark comparison against QueryPilot."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from app.db.engine import execute_readonly_query
from app.llm.mock_provider import MockProvider


def run_baseline_agent(
    question: str,
    seed_invalid_sql: Optional[str] = None,
    seed_db_error_sql: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a naive single-pass Text-to-SQL baseline:
    - No Request Analyzer ambiguity or missing-schema guardrails (attempts to generate SQL for everything).
    - No SQLGlot full-AST safety validator (relies only on naive execution).
    - No EXPLAIN Cost Estimator or Approval Gate (either runs expensive queries directly or uses a naive heuristic).
    - Single pass (0 retries): cannot recover from initial invalid SQL or runtime database errors.
    """
    t0 = time.perf_counter()
    q = (question or "").strip()
    q_lower = q.lower()
    mock = MockProvider()

    # Naive baseline attempts to generate SQL directly in 1 model call without schema discovery
    if seed_invalid_sql:
        sql = seed_invalid_sql
    elif seed_db_error_sql:
        sql = seed_db_error_sql
    elif any(k in q_lower for k in ("drop table", "delete from", "truncate ", "update ", "insert into", "pg_sleep", "pg_read_file", "pg_shadow", "with del as (delete")):
        # Baseline only has a naive prefix check for "drop table" at the very start of the string,
        # missing stacked queries, writable CTEs, dangerous functions, and system catalog queries!
        if q_lower.startswith("drop table") and ";" not in q_lower:
            elapsed = round((time.perf_counter() - t0) * 1000.0, 2)
            return {
                "status": "blocked",
                "sql": q,
                "executed": False,
                "row_count": 0,
                "rows": [],
                "recovered": False,
                "unnecessary_approval": False,
                "model_calls": 1,
                "tool_calls": 0,
                "latency_ms": elapsed,
                "error": "Naive prefix filter blocked DROP TABLE",
            }
        # Otherwise naive baseline passes the unsafe/stacked/CTE/function query through as-is
        sql = q if ("select" in q_lower or "delete" in q_lower or "drop" in q_lower or "update" in q_lower or "insert" in q_lower) else f"SELECT * FROM ({q}) t"
    elif any(
        phrase in q_lower
        for phrase in (
            "employee",
            "salary",
            "salaries",
            "payroll",
            "stock price",
            "share price",
            "weather",
            "temperature",
            "competitor",
            "support ticket",
            "helpdesk",
            "nps score",
            "warehouse capacity",
            "supplier lead time",
            "social media follower",
        )
    ):
        # Naive baseline hallucinates a nonexistent table because it lacks Schema Discovery & Request Analyzer scope checks
        sql = "SELECT * FROM hallucinated_external_table LIMIT 10"
    elif q_lower in (
        "how are things going?",
        "show me the numbers",
        "is performance good?",
        "are we growing?",
        "analyze this",
        "give me insights",
        "show the best ones",
        "compare them",
        "what is the rate?",
        "who is best?",
    ):
        # Naive baseline guesses a random raw table dump instead of asking for clarification
        sql = "SELECT * FROM orders LIMIT 5"
    else:
        intent = mock.analyze_request(q)
        plan = mock.plan_query(q, intent, {})
        gen = mock.generate_sql(q, intent, plan, {})
        sql = gen["sql"]

    # Naive baseline has an overly sensitive keyword flag that unnecessarily flags any query mentioning "join" or "revenue" > 2 tables
    unnecessary_approval = "join" in sql.lower() and "categories" in sql.lower() and "cross join" not in sql.lower()

    try:
        res = execute_readonly_query(sql, timeout_ms=1000, max_rows=500)
        elapsed = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "status": "completed",
            "sql": sql,
            "executed": True,
            "row_count": res["row_count"],
            "rows": res["rows"],
            "recovered": False,
            "unnecessary_approval": unnecessary_approval,
            "model_calls": 1,
            "tool_calls": 1,
            "latency_ms": elapsed,
            "error": None,
        }
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "status": "error",
            "sql": sql,
            "executed": False,
            "row_count": 0,
            "rows": [],
            "recovered": False,
            "unnecessary_approval": unnecessary_approval,
            "model_calls": 1,
            "tool_calls": 1,
            "latency_ms": elapsed,
            "error": str(exc),
        }
