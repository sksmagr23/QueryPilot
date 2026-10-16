"""Phase 1 tests: deterministic seeding, PostgreSQL read-only role, query timeouts, row limits, and schema discovery."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.config import get_settings
from app.db.engine import execute_readonly_query, get_admin_engine, get_readonly_engine, run_explain_plan
from app.db.models import WAREHOUSE_TABLES
from app.db.seed import get_table_counts, seed_warehouse
from app.semantic.schema_inspector import discover_schema


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    """Ensure the PostgreSQL warehouse is deterministically seeded before tests run."""
    counts = seed_warehouse(force=False)
    return counts


def test_deterministic_seeding_counts(seeded_db):
    """Verify all 7 e-commerce tables exist and contain deterministic row counts."""
    counts = get_table_counts()
    for table in WAREHOUSE_TABLES:
        assert table in counts
        assert counts[table] > 0

    assert counts["categories"] == 8
    assert counts["products"] == 32
    assert counts["customers"] == 450
    assert counts["orders"] == 3020


def test_database_level_readonly_enforcement():
    """Verify the dedicated PostgreSQL read-only role rejects DML and DDL at the database level."""
    with pytest.raises((ProgrammingError, DBAPIError, PermissionError)):
        execute_readonly_query("DELETE FROM categories WHERE category_id = 1")

    with pytest.raises((ProgrammingError, DBAPIError, PermissionError)):
        execute_readonly_query("DROP TABLE categories")

    with pytest.raises((ProgrammingError, DBAPIError, PermissionError)):
        execute_readonly_query(
            "INSERT INTO categories (category_id, name, department, target_margin_pct, created_at) "
            "VALUES (999, 'Hack', 'Hack', 10.0, NOW())"
        )

    # Also verify direct connection on get_readonly_engine() rejects writes due to role privileges
    ro_engine = get_readonly_engine()
    with pytest.raises(DBAPIError):
        with ro_engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM categories WHERE category_id = 1")


def test_database_level_statement_timeout():
    """Verify database-level statement_timeout terminates slow queries on PostgreSQL."""
    with pytest.raises(DBAPIError):
        execute_readonly_query("SELECT pg_sleep(1.0)", timeout_ms=150)


def test_driver_level_row_limits():
    """Verify execute_readonly_query enforces max_rows at the driver cursor level and sets truncated=True."""
    res = execute_readonly_query("SELECT order_id, total_amount FROM orders ORDER BY order_id", max_rows=25)
    assert res["row_count"] == 25
    assert len(res["rows"]) == 25
    assert res["truncated"] is True
    assert res["max_rows_enforced"] == 25


def test_non_executing_explain_plan():
    """Verify run_explain_plan returns PostgreSQL EXPLAIN JSON metadata without modifying data."""
    plan = run_explain_plan(
        "SELECT c.name, SUM(oi.line_total) AS revenue "
        "FROM order_items oi "
        "JOIN products p ON oi.product_id = p.product_id "
        "JOIN categories c ON p.category_id = c.category_id "
        "GROUP BY c.name"
    )
    assert plan["dialect"] == "postgresql"
    assert plan["total_cost"] > 0
    assert plan["plan_rows"] > 0


def test_schema_discovery_and_semantic_catalog():
    """Verify discover_schema inspects all 7 tables, relationships, and semantic metrics."""
    schema = discover_schema()
    assert schema["dialect"] == "postgresql"
    assert len(schema["tables"]) == 7
    assert len(schema["schema_version"]) == 16
    assert len(schema["relationships"]) >= 6
    assert len(schema["semantic_metrics"]) >= 6

    # Check specific foreign keys discovered
    rel_pairs = {(r["source_table"], r["target_table"]) for r in schema["relationships"]}
    assert ("products", "categories") in rel_pairs
    assert ("orders", "customers") in rel_pairs
    assert ("order_items", "orders") in rel_pairs
    assert ("order_items", "products") in rel_pairs
    assert ("payments", "orders") in rel_pairs


def test_flagship_business_data_patterns():
    """Verify the seeded dataset supports the 5 flagship business questions with expected patterns."""
    # 1. Category revenue ranking: Electronics and Home & Office at the top
    cat_rev = execute_readonly_query(
        """
        SELECT c.name AS category, ROUND(SUM(oi.line_total), 2) AS net_revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN products p ON oi.product_id = p.product_id
        JOIN categories c ON p.category_id = c.category_id
        WHERE o.status NOT IN ('cancelled', 'refunded')
        GROUP BY c.name
        ORDER BY net_revenue DESC
        """
    )
    top_two_categories = [r["category"] for r in cat_rev["rows"][:2]]
    assert "Electronics" in top_two_categories
    assert "Home & Office" in top_two_categories

    # 2. Month-over-month revenue decrease in latest month (2026-09 vs 2026-08)
    mom_rev = execute_readonly_query(
        """
        SELECT TO_CHAR(DATE_TRUNC('month', order_date), 'YYYY-MM') AS month,
               ROUND(SUM(total_amount), 2) AS revenue
        FROM orders
        WHERE status NOT IN ('cancelled', 'refunded')
          AND order_date >= '2026-08-01'
        GROUP BY 1
        ORDER BY 1
        """
    )
    assert len(mom_rev["rows"]) == 2
    aug_rev = mom_rev["rows"][0]["revenue"]
    sep_rev = mom_rev["rows"][1]["revenue"]
    assert sep_rev < aug_rev

    # 3. AOV by customer segment: Enterprise > VIP > SMB > Consumer
    aov_seg = execute_readonly_query(
        """
        SELECT c.segment, ROUND(AVG(o.total_amount), 2) AS aov
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.status NOT IN ('cancelled', 'refunded')
        GROUP BY c.segment
        ORDER BY aov DESC
        """
    )
    seg_order = [r["segment"] for r in aov_seg["rows"]]
    assert seg_order[0] == "Enterprise"
    assert seg_order[-1] == "Consumer"

    # 5. Regional cancellation rate: LATAM has highest cancellation rate
    cancel_reg = execute_readonly_query(
        """
        SELECT region,
               ROUND(100.0 * SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancel_rate
        FROM orders
        GROUP BY region
        ORDER BY cancel_rate DESC
        """
    )
    assert cancel_reg["rows"][0]["region"] == "LATAM"


def test_configurable_gemini_model_settings():
    """Verify Gemini model IDs are configurable from .env and default to gemini-2.5-flash."""
    settings = get_settings()
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.gemini_fallback_model == "gemini-2.5-flash-lite"
