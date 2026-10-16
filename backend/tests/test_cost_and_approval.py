"""Phase 2 tests: non-executing EXPLAIN cost estimator, approval fingerprinting, invalidation on SQL/context change, and duplicate execution guard."""

from __future__ import annotations

import pytest

from app.safety.cost_estimator import (
    compute_context_fingerprint,
    estimate_query_cost,
    is_approval_valid,
)
from app.semantic.schema_inspector import discover_schema


@pytest.fixture(scope="module")
def schema_info():
    return discover_schema()


def test_low_cost_query_does_not_require_approval(schema_info):
    sql = """
    SELECT c.name, ROUND(SUM(oi.line_total), 2) AS net_revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN categories c ON p.category_id = c.category_id
    GROUP BY c.name
    LIMIT 10
    """
    est = estimate_query_cost(sql, schema_info=schema_info, cost_threshold=5000.0)
    assert est["requires_approval"] is False
    assert est["risk_level"] in ("low", "medium")
    assert est["estimated_cost"] > 0
    assert len(est["context_fingerprint"]) == 64


def test_expensive_cross_join_requires_approval(schema_info):
    sql = """
    SELECT c.customer_id, we.event_id, oi.order_item_id
    FROM customers c
    CROSS JOIN website_events we
    CROSS JOIN order_items oi
    LIMIT 500
    """
    est = estimate_query_cost(sql, schema_info=schema_info)
    assert est["requires_approval"] is True
    assert est["risk_level"] == "high"
    assert est["has_cross_join"] is True
    assert est["approval_reason"] is not None


def test_approval_invalidation_when_sql_or_context_changes():
    sql_v1 = "SELECT order_id, total_amount FROM orders LIMIT 100"
    sql_v2 = "SELECT order_id, total_amount, discount_amount FROM orders LIMIT 100"

    fp1 = compute_context_fingerprint(
        normalized_sql=sql_v1,
        dialect="postgresql",
        schema_version="v1",
        params={"region": "LATAM"},
        thread_context="turn_1",
    )
    approval_record = {
        "status": "approved",
        "executed": False,
        "context_fingerprint": fp1,
    }

    # Exact match is valid
    assert is_approval_valid(approval_record, fp1) is True

    # Modified SQL invalidates approval
    fp_sql_changed = compute_context_fingerprint(
        normalized_sql=sql_v2,
        dialect="postgresql",
        schema_version="v1",
        params={"region": "LATAM"},
        thread_context="turn_1",
    )
    assert is_approval_valid(approval_record, fp_sql_changed) is False

    # Modified parameters or thread context invalidates approval
    fp_context_changed = compute_context_fingerprint(
        normalized_sql=sql_v1,
        dialect="postgresql",
        schema_version="v1",
        params={"region": "Europe"},
        thread_context="turn_2",
    )
    assert is_approval_valid(approval_record, fp_context_changed) is False

    # Already-executed approval cannot be reused (prevents duplicate execution)
    executed_record = {**approval_record, "executed": True}
    assert is_approval_valid(executed_record, fp1) is False
