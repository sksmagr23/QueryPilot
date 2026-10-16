"""Phase 2 tests: strengthened SQLGlot full-AST validation against dangerous CTEs, functions, multi-statements, and invalid identifiers."""

from __future__ import annotations

import pytest

from app.safety.sql_validator import validate_sql
from app.semantic.schema_inspector import discover_schema


@pytest.fixture(scope="module")
def schema_info():
    return discover_schema()


def test_valid_select_and_cte_queries(schema_info):
    sql = """
    WITH cat_rev AS (
        SELECT p.category_id, SUM(oi.line_total) AS revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        GROUP BY p.category_id
    )
    SELECT c.name, cr.revenue
    FROM cat_rev cr
    JOIN categories c ON cr.category_id = c.category_id
    ORDER BY cr.revenue DESC
    """
    res = validate_sql(sql, schema_info=schema_info, max_rows=100)
    assert res["is_valid"] is True
    assert res["is_safe"] is True
    assert res["errors"] == []
    assert "LIMIT 100" in res["normalized_sql"].upper()


def test_reject_multi_statement_queries(schema_info):
    sql = "SELECT category_id, name FROM categories; DROP TABLE categories;"
    res = validate_sql(sql, schema_info=schema_info)
    assert res["is_valid"] is False
    assert res["is_safe"] is False
    assert res["statement_type"] == "MULTI_STATEMENT"


def test_reject_dangerous_writable_cte(schema_info):
    sql = """
    WITH deleted_rows AS (
        DELETE FROM orders WHERE order_id = 1 RETURNING *
    )
    SELECT * FROM deleted_rows
    """
    res = validate_sql(sql, schema_info=schema_info)
    assert res["is_valid"] is False
    assert res["is_safe"] is False
    assert any("DELETE" in err.upper() or "PROHIBITED" in err.upper() for err in res["errors"])


@pytest.mark.parametrize(
    "unsafe_sql",
    [
        "SELECT pg_sleep(10) FROM categories",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_terminate_backend(1234)",
        "SELECT dblink('dbname=postgres', 'SELECT 1')",
        "SELECT lo_import('/tmp/test')",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.columns",
        "SELECT * FROM pg_shadow",
        "SELECT * INTO temp_hack FROM categories",
        "SELECT * FROM categories FOR UPDATE",
        "DROP TABLE orders",
        "UPDATE orders SET total_amount = 0",
        "INSERT INTO categories VALUES (99, 'X', 'Y', 10, NOW())",
        "COPY categories TO '/tmp/out.csv'",
        "GRANT ALL ON categories TO public",
    ],
)
def test_reject_dangerous_functions_system_tables_and_ddl_dml(unsafe_sql, schema_info):
    res = validate_sql(unsafe_sql, schema_info=schema_info)
    assert res["is_valid"] is False
    assert res["is_safe"] is False
    assert len(res["errors"]) > 0


def test_reject_unknown_tables_and_columns(schema_info):
    # Unknown table
    res_tbl = validate_sql("SELECT * FROM employee_salaries", schema_info=schema_info)
    assert res_tbl["is_valid"] is False
    assert any("employee_salaries" in e for e in res_tbl["errors"])

    # Unknown column on known table
    res_col = validate_sql(
        "SELECT o.order_id, o.nonexistent_secret_column FROM orders o",
        schema_info=schema_info,
    )
    assert res_col["is_valid"] is False
    assert any("nonexistent_secret_column" in e for e in res_col["errors"])


def test_limit_capping(schema_info):
    res = validate_sql("SELECT order_id FROM orders LIMIT 99999", schema_info=schema_info, max_rows=250)
    assert res["is_valid"] is True
    assert "LIMIT 250" in res["normalized_sql"].upper()
