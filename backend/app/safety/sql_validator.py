"""Strengthened structural SQL validator using SQLGlot full-AST inspection."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.config import get_settings
from app.db.models import WAREHOUSE_TABLES

# Forbidden AST node types anywhere in the query (including inside CTEs or subqueries)
FORBIDDEN_AST_TYPES: Tuple[type, ...] = tuple(
    t
    for t in (
        getattr(exp, "Insert", None),
        getattr(exp, "Update", None),
        getattr(exp, "Delete", None),
        getattr(exp, "Merge", None),
        getattr(exp, "Drop", None),
        getattr(exp, "Alter", None),
        getattr(exp, "Create", None),
        getattr(exp, "TruncateTable", None),
        getattr(exp, "Command", None),
        getattr(exp, "Copy", None),
        getattr(exp, "Grant", None),
        getattr(exp, "Revoke", None),
        getattr(exp, "Set", None),
        getattr(exp, "Pragma", None),
        getattr(exp, "Transaction", None),
        getattr(exp, "Commit", None),
        getattr(exp, "Rollback", None),
        getattr(exp, "Lock", None),
        getattr(exp, "Use", None),
        getattr(exp, "Into", None),
        getattr(exp, "LockingProperty", None),
        getattr(exp, "LockingStatement", None),
    )
    if t is not None
)

# Dangerous or side-effect functions blocked anywhere in the AST
PROHIBITED_FUNCTIONS: Set[str] = {
    "pg_sleep",
    "pg_sleep_for",
    "pg_sleep_until",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
    "dblink",
    "dblink_exec",
    "dblink_connect",
    "query_to_xml",
    "table_to_xml",
    "database_to_xml",
    "set_config",
    "read_csv",
    "read_csv_auto",
    "read_parquet",
    "read_json",
    "read_json_auto",
}

# Forbidden system schemas and catalog tables
PROHIBITED_SCHEMAS: Set[str] = {
    "pg_catalog",
    "information_schema",
    "pg_toast",
    "pg_temp",
}

PROHIBITED_SYSTEM_TABLES: Set[str] = {
    "pg_roles",
    "pg_shadow",
    "pg_authid",
    "pg_user",
    "pg_stat_activity",
    "pg_settings",
    "pg_tables",
    "pg_class",
    "pg_namespace",
    "pg_proc",
}

# Raw SQL keywords that indicate stacked/administrative/locking operations even if sqlglot parses them loosely
FORBIDDEN_TOP_PATTERNS = [
    (re.compile(r"\bFOR\s+(UPDATE|SHARE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", re.IGNORECASE), "Row locking clauses (FOR UPDATE/SHARE) are prohibited."),
    (re.compile(r"\bSELECT\b[\s\S]*?\bINTO\s+(TEMP|TEMPORARY|UNLOGGED|TABLE)?\s*[a-zA-Z_]", re.IGNORECASE), "SELECT ... INTO table creation is prohibited."),
    (re.compile(r"\b(COPY|GRANT|REVOKE|VACUUM|ANALYZE|TRUNCATE|CALL|DO|EXECUTE|PREPARE|DEALLOCATE|LISTEN|NOTIFY|DISCARD)\b", re.IGNORECASE), "Administrative or procedural SQL statements are prohibited."),
]


def _extract_function_name(node: exp.Expression) -> str:
    """Extract normalized lowercase function name from an AST function node."""
    if isinstance(node, exp.Anonymous):
        return (node.name or "").lower()
    if isinstance(node, exp.Func):
        # Check SQL name or class sql_name
        raw_name = node.sql_name() if hasattr(node, "sql_name") else node.key
        if isinstance(node, exp.Anonymous) and node.name:
            return node.name.lower()
        # Also inspect sql representation of the function head
        sql_head = node.sql("postgres").split("(", 1)[0].strip().lower()
        if "." in sql_head:
            sql_head = sql_head.split(".")[-1]
        return sql_head or str(raw_name).lower()
    return ""


def validate_sql(
    sql: str,
    schema_info: Optional[Dict[str, Any]] = None,
    dialect: str = "postgres",
    max_rows: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Parse and validate SQL structurally using SQLGlot across the entire AST.

    Enforces:
    1. Non-empty, single-statement SQL (rejects stacked ';' multi-statement queries).
    2. Root AST must be SELECT or set operation (UNION/INTERSECT/EXCEPT).
    3. Full-AST walk blocking writable/dangerous CTEs, DDL/DML, locking clauses, and SELECT INTO.
    4. Full-AST walk blocking dangerous functions (pg_sleep, pg_read_file, dblink, etc.).
    5. Blocks system catalog/schema access (pg_catalog, information_schema, pg_*).
    6. Verifies all referenced tables and columns against discovered warehouse schema.
    7. Caps or injects LIMIT <= max_rows.
    """
    settings = get_settings()
    effective_max_rows = int(max_rows if max_rows is not None else settings.max_result_rows)
    sg_dialect = "postgres" if dialect.startswith("postgres") else dialect

    cleaned = (sql or "").strip()
    if not cleaned:
        return {
            "is_valid": False,
            "is_safe": True,
            "statement_type": "EMPTY",
            "errors": ["SQL query is empty."],
            "referenced_tables": [],
            "referenced_columns": [],
            "normalized_sql": "",
        }

    # Check raw multi-statement semicolons before/during parse
    try:
        statements = [s for s in sqlglot.parse(cleaned, read=sg_dialect) if s is not None]
    except ParseError as exc:
        return {
            "is_valid": False,
            "is_safe": True,
            "statement_type": "PARSE_ERROR",
            "errors": [f"SQL syntax error: {exc}"],
            "referenced_tables": [],
            "referenced_columns": [],
            "normalized_sql": cleaned,
        }

    if len(statements) != 1:
        return {
            "is_valid": False,
            "is_safe": False,
            "statement_type": "MULTI_STATEMENT",
            "errors": [
                f"Multi-statement queries are prohibited (found {len(statements)} statements). Only a single SELECT statement is allowed."
            ],
            "referenced_tables": [],
            "referenced_columns": [],
            "normalized_sql": cleaned,
        }

    ast = statements[0]
    stmt_type = ast.key.upper()
    errors: List[str] = []
    is_safe = True

    # 1. Check root statement type
    allowed_roots = (exp.Select, exp.Union, exp.Intersect, exp.Except)
    if not isinstance(ast, allowed_roots):
        is_safe = False
        errors.append(
            f"Unsafe statement type '{stmt_type}' rejected. Only read-only SELECT queries are permitted."
        )

    # 2. Check regex guardrails for locking / procedural constructs
    for pattern, msg in FORBIDDEN_TOP_PATTERNS:
        if pattern.search(cleaned):
            is_safe = False
            errors.append(msg)

    # 3. Walk the ENTIRE AST (including CTEs and subqueries) for forbidden node types and functions
    for node in ast.walk():
        if isinstance(node, FORBIDDEN_AST_TYPES):
            is_safe = False
            errors.append(
                f"Prohibited operation '{node.key.upper()}' detected inside query or CTE."
            )
        if isinstance(node, exp.Func):
            fn_name = _extract_function_name(node)
            if fn_name in PROHIBITED_FUNCTIONS:
                is_safe = False
                errors.append(
                    f"Prohibited or dangerous function '{fn_name}()' is not allowed."
                )

    # 4. Collect CTE names so we distinguish CTE references from physical tables
    cte_names: Set[str] = set()
    cte_projected_cols: Set[str] = set()
    for cte in ast.find_all(exp.CTE):
        alias = cte.alias_or_name
        if alias:
            cte_names.add(alias.lower())
        cte_this = cte.this
        if isinstance(cte_this, exp.Select):
            for proj in cte_this.expressions:
                if proj.alias_or_name:
                    cte_projected_cols.add(proj.alias_or_name.lower())

    # Also collect subquery aliases and select aliases (for ORDER BY / HAVING / outer SELECT references)
    select_aliases: Set[str] = set()
    for sel in ast.find_all(exp.Select):
        for proj in sel.expressions:
            if isinstance(proj, exp.Alias) and proj.alias:
                select_aliases.add(proj.alias.lower())

    subquery_aliases: Set[str] = set()
    for subq in ast.find_all(exp.Subquery):
        if subq.alias:
            subquery_aliases.add(subq.alias.lower())
        if isinstance(subq.this, exp.Select):
            for proj in subq.this.expressions:
                if proj.alias_or_name:
                    cte_projected_cols.add(proj.alias_or_name.lower())

    # 5. Inspect all physical table references and alias mappings
    allowed_tables_map: Dict[str, Set[str]] = {}
    if schema_info and "table_columns" in schema_info:
        for tname, cols in schema_info["table_columns"].items():
            allowed_tables_map[tname.lower()] = {c.lower() for c in cols}
    else:
        for tname in WAREHOUSE_TABLES:
            allowed_tables_map[tname.lower()] = set()

    referenced_tables: List[str] = []
    alias_to_table: Dict[str, str] = {}

    for tbl in ast.find_all(exp.Table):
        t_name = (tbl.name or "").lower()
        t_db = (tbl.db or "").lower()
        t_alias = (tbl.alias or "").lower()

        if not t_name:
            continue

        # Check prohibited system schemas or system catalog tables
        if t_db in PROHIBITED_SCHEMAS or t_name in PROHIBITED_SCHEMAS:
            is_safe = False
            errors.append(f"Access to system schema '{t_db or t_name}' is prohibited.")
            continue

        if t_name in PROHIBITED_SYSTEM_TABLES or t_name.startswith("pg_"):
            is_safe = False
            errors.append(f"Access to system catalog table '{t_name}' is prohibited.")
            continue

        if t_db and t_db != "public":
            is_safe = False
            errors.append(f"Unauthorized schema '{t_db}' referenced on table '{t_name}'.")
            continue

        if t_name in cte_names:
            if t_alias:
                alias_to_table[t_alias] = t_name
            alias_to_table[t_name] = t_name
            continue

        if t_name not in allowed_tables_map:
            errors.append(
                f"Unknown or unauthorized table '{t_name}'. Allowed tables: {', '.join(sorted(allowed_tables_map.keys()))}."
            )
            continue

        if t_name not in referenced_tables:
            referenced_tables.append(t_name)

        alias_to_table[t_name] = t_name
        if t_alias:
            alias_to_table[t_alias] = t_name

    # 6. Validate column identifiers against discovered schema when schema_info is provided
    referenced_columns: List[str] = []
    if schema_info and "table_columns" in schema_info and not errors:
        all_valid_cols_in_query: Set[str] = set(cte_projected_cols) | set(select_aliases)
        for rt in referenced_tables:
            all_valid_cols_in_query |= allowed_tables_map.get(rt, set())

        for col in ast.find_all(exp.Column):
            c_name = (col.name or "").lower()
            c_table = (col.table or "").lower()
            if not c_name or c_name == "*":
                continue

            # Ignore DATE_TRUNC / EXTRACT date part identifiers if parsed as Column
            if isinstance(col.parent, (exp.Extract, exp.Anonymous, exp.TimestampTrunc, exp.DateTrunc)):
                if c_name in {"year", "quarter", "month", "week", "day", "hour", "minute", "second", "dow", "doy", "epoch"}:
                    continue

            col_label = f"{c_table}.{c_name}" if c_table else c_name
            if col_label not in referenced_columns:
                referenced_columns.append(col_label)

            if c_table:
                if c_table in cte_names or c_table in subquery_aliases:
                    continue
                resolved_table = alias_to_table.get(c_table)
                if not resolved_table:
                    errors.append(
                        f"Column '{c_table}.{c_name}' references unknown table or alias '{c_table}'."
                    )
                elif resolved_table in allowed_tables_map:
                    valid_cols = allowed_tables_map[resolved_table]
                    if valid_cols and c_name not in valid_cols:
                        errors.append(
                            f"Column '{c_name}' does not exist on table '{resolved_table}'. "
                            f"Valid columns on '{resolved_table}': {', '.join(sorted(valid_cols))}."
                        )
            else:
                if referenced_tables and c_name not in all_valid_cols_in_query:
                    errors.append(
                        f"Column '{c_name}' does not exist in referenced tables ({', '.join(referenced_tables)})."
                    )

    # 7. Enforce or cap LIMIT on the top-level query if valid & safe
    normalized_sql = cleaned
    if not errors and is_safe and isinstance(ast, allowed_roots):
        existing_limit = ast.args.get("limit")
        if existing_limit is not None and isinstance(existing_limit, exp.Limit):
            try:
                limit_val = int(existing_limit.expression.name)
                if limit_val > effective_max_rows:
                    ast = ast.limit(effective_max_rows)
            except (ValueError, AttributeError):
                pass
        else:
            ast = ast.limit(effective_max_rows)
        normalized_sql = ast.sql(dialect=sg_dialect)

    return {
        "is_valid": len(errors) == 0 and is_safe,
        "is_safe": is_safe,
        "statement_type": stmt_type,
        "errors": errors,
        "referenced_tables": referenced_tables,
        "referenced_columns": referenced_columns,
        "normalized_sql": normalized_sql,
    }
