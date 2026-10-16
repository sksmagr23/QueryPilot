"""Non-executing query cost estimator, risk policy evaluator, and approval fingerprinting."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

import sqlglot
from sqlglot import exp

from app.config import get_settings
from app.db.engine import run_explain_plan

LARGE_TABLES = {"website_events", "order_items", "orders", "payments"}


def compute_context_fingerprint(
    normalized_sql: str,
    dialect: str = "postgresql",
    schema_version: str = "",
    params: Optional[Dict[str, Any]] = None,
    thread_context: str = "",
) -> str:
    """
    Compute an immutable SHA-256 fingerprint binding an approval to the exact normalized SQL,
    dialect, schema version, bound parameters, and execution context.
    Any modification to SQL or context produces a different fingerprint, invalidating stale approvals.
    """
    canonical_sql = " ".join((normalized_sql or "").strip().split()).lower()
    payload = {
        "sql": canonical_sql,
        "dialect": (dialect or "postgresql").lower(),
        "schema_version": schema_version or "",
        "params": params or {},
        "thread_context": thread_context or "",
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def is_approval_valid(
    approval_record: Optional[Dict[str, Any]],
    current_fingerprint: str,
) -> bool:
    """
    Verify whether an existing approval record is still valid for the current execution context.
    Returns False if:
    - no approval exists
    - status is not 'approved'
    - already executed (prevents duplicate execution)
    - context_fingerprint does not match current_fingerprint (invalidated by SQL/context change)
    """
    if not approval_record:
        return False
    if approval_record.get("status") != "approved":
        return False
    if approval_record.get("executed", False):
        return False
    recorded_fp = approval_record.get("context_fingerprint", "")
    if not recorded_fp or recorded_fp != current_fingerprint:
        return False
    return True


def _inspect_postgres_plan_nodes(
    plan_node: Dict[str, Any],
    seq_scan_tables: List[str],
    nested_loop_unfiltered: List[str],
) -> None:
    """Recursively inspect PostgreSQL EXPLAIN JSON nodes for seq scans and unfiltered nested loops."""
    if not isinstance(plan_node, dict):
        return
    node_type = plan_node.get("Node Type", "")
    rel_name = plan_node.get("Relation Name", "")
    plan_rows = int(plan_node.get("Plan Rows", 0))

    if node_type == "Seq Scan" and rel_name in LARGE_TABLES and plan_rows >= 1000:
        if rel_name not in seq_scan_tables:
            seq_scan_tables.append(rel_name)

    if node_type == "Nested Loop" and plan_rows >= 25000:
        nested_loop_unfiltered.append(f"Nested Loop ({plan_rows} est. rows)")

    for child in plan_node.get("Plans", []) or []:
        _inspect_postgres_plan_nodes(child, seq_scan_tables, nested_loop_unfiltered)


def estimate_query_cost(
    sql: str,
    schema_info: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    thread_context: str = "",
    cost_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluate query cost and risk using both structural AST analysis and a non-executing
    database EXPLAIN plan. Determines whether human-in-the-loop approval is required.
    """
    settings = get_settings()
    threshold = float(
        cost_threshold if cost_threshold is not None else settings.cost_approval_threshold
    )
    schema_version = (schema_info or {}).get("schema_version", "")

    approval_reasons: List[str] = []
    has_cross_join = False
    unfiltered_large_scan = False
    join_count = 0

    # 1. Structural AST heuristics
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
        joins = list(parsed.find_all(exp.Join))
        join_count = len(joins)
        for j in joins:
            j_kind = (j.kind or "").upper()
            has_on = j.args.get("on") is not None
            has_using = j.args.get("using") is not None
            if "CROSS" in j_kind or (not has_on and not has_using):
                has_cross_join = True
                approval_reasons.append(
                    "Cartesian/CROSS JOIN detected without an explicit join predicate."
                )

        # Check if large tables are scanned without WHERE or GROUP BY and with high limit
        tables = [t.name.lower() for t in parsed.find_all(exp.Table) if t.name]
        has_where = parsed.find(exp.Where) is not None
        has_group = parsed.find(exp.Group) is not None
        has_agg = any(
            isinstance(n, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max))
            for n in parsed.walk()
        )
        if any(t in {"website_events", "order_items"} for t in tables):
            if not has_where and not has_group and not has_agg and join_count >= 2:
                unfiltered_large_scan = True
                approval_reasons.append(
                    "Multi-table unaggregated scan over high-volume fact table without WHERE filter."
                )
    except Exception:
        pass

    # 2. Non-executing database EXPLAIN plan
    explain_info = run_explain_plan(sql, params=params)
    total_cost = float(explain_info.get("total_cost", 0.0))
    estimated_rows = int(explain_info.get("plan_rows", 0))
    seq_scan_tables: List[str] = []
    nested_loops: List[str] = []

    raw_plan = explain_info.get("raw_plan")
    if isinstance(raw_plan, list) and raw_plan:
        root_plan = raw_plan[0].get("Plan", {})
        _inspect_postgres_plan_nodes(root_plan, seq_scan_tables, nested_loops)

    if nested_loops:
        approval_reasons.append(
            f"High-cardinality Nested Loop detected ({', '.join(nested_loops)})."
        )

    # Apply cost policy
    if has_cross_join:
        total_cost = max(total_cost, threshold * 2.5)

    if total_cost >= threshold:
        approval_reasons.append(
            f"Estimated query cost ({total_cost:.2f}) exceeds policy threshold ({threshold:.2f})."
        )

    requires_approval = bool(
        has_cross_join or unfiltered_large_scan or nested_loops or total_cost >= threshold
    )

    if requires_approval or total_cost >= threshold:
        risk_level = "high"
    elif total_cost >= threshold * 0.55 or len(seq_scan_tables) >= 2 or join_count >= 3:
        risk_level = "medium"
    else:
        risk_level = "low"

    fingerprint = compute_context_fingerprint(
        normalized_sql=sql,
        dialect=explain_info.get("dialect", "postgresql"),
        schema_version=schema_version,
        params=params,
        thread_context=thread_context,
    )

    return {
        "estimated_cost": round(total_cost, 2),
        "estimated_rows": estimated_rows,
        "cost_threshold": threshold,
        "risk_level": risk_level,
        "has_cross_join": has_cross_join,
        "seq_scan_tables": seq_scan_tables,
        "join_count": join_count,
        "requires_approval": requires_approval,
        "approval_reasons": approval_reasons,
        "approval_reason": " ".join(approval_reasons) if approval_reasons else None,
        "context_fingerprint": fingerprint,
        "explain_plan": explain_info.get("raw_plan"),
    }
