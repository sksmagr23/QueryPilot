"""Automated database schema discovery and relationship extraction."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import Engine, inspect, text

from app.db.engine import get_readonly_engine
from app.db.models import WAREHOUSE_TABLES
from app.semantic.catalog import (
    SEMANTIC_METRICS,
    TABLE_SEMANTIC_DESCRIPTIONS,
    VALID_JOIN_GRAPH,
)


def discover_schema(
    engine: Optional[Engine] = None,
    relevant_tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Inspect the live database schema for warehouse tables, columns, data types,
    primary/foreign keys, row counts, and semantic annotations.
    """
    ro_engine = engine or get_readonly_engine()
    inspector = inspect(ro_engine)
    existing_tables = set(inspector.get_table_names())

    target_tables = [
        t for t in WAREHOUSE_TABLES if t in existing_tables and (not relevant_tables or t in relevant_tables)
    ]

    tables_info: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    table_columns_map: Dict[str, List[str]] = {}

    with ro_engine.connect() as conn:
        for table_name in target_tables:
            pk_constraint = inspector.get_pk_constraint(table_name) or {}
            pk_cols = set(pk_constraint.get("constrained_columns") or [])
            fks = inspector.get_foreign_keys(table_name) or []
            fk_map: Dict[str, str] = {}
            for fk in fks:
                referred_table = fk.get("referred_table")
                constrained_cols = fk.get("constrained_columns") or []
                referred_cols = fk.get("referred_columns") or []
                if referred_table and constrained_cols and referred_cols:
                    src_col = constrained_cols[0]
                    dst_col = referred_cols[0]
                    fk_map[src_col] = f"{referred_table}.{dst_col}"
                    relationships.append(
                        {
                            "source_table": table_name,
                            "source_column": src_col,
                            "target_table": referred_table,
                            "target_column": dst_col,
                            "join_sql": f"{table_name}.{src_col} = {referred_table}.{dst_col}",
                        }
                    )

            columns_raw = inspector.get_columns(table_name)
            columns_list: List[Dict[str, Any]] = []
            col_names: List[str] = []
            for col in columns_raw:
                cname = col["name"]
                col_names.append(cname)
                columns_list.append(
                    {
                        "name": cname,
                        "type": str(col["type"]),
                        "nullable": bool(col.get("nullable", True)),
                        "is_primary_key": cname in pk_cols,
                        "foreign_key": fk_map.get(cname),
                    }
                )
            table_columns_map[table_name] = col_names

            try:
                row_count = int(
                    conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
                )
            except Exception:
                row_count = 0

            tables_info.append(
                {
                    "name": table_name,
                    "description": TABLE_SEMANTIC_DESCRIPTIONS.get(table_name, ""),
                    "row_count": row_count,
                    "columns": columns_list,
                    "primary_keys": list(pk_cols),
                }
            )

    fingerprint_source = json.dumps(table_columns_map, sort_keys=True)
    schema_version = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16]

    return {
        "dialect": ro_engine.dialect.name,
        "schema_version": schema_version,
        "tables": tables_info,
        "table_columns": table_columns_map,
        "relationships": relationships,
        "semantic_metrics": SEMANTIC_METRICS,
        "valid_joins": VALID_JOIN_GRAPH,
    }
