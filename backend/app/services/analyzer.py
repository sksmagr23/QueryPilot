"""Analysis Agent service: deterministic comparisons, rankings, shares, and deltas from query results."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _is_numeric(val: Any) -> bool:
    if isinstance(val, bool) or val is None:
        return False
    if isinstance(val, (int, float)):
        return not (math.isnan(val) or math.isinf(val))
    return False


def analyze_query_results(
    rows: List[Dict[str, Any]],
    columns: List[str],
    question: str = "",
) -> Dict[str, Any]:
    """
    Calculate comparisons, rankings, shares of total, percentage changes, and KPI cards
    directly from actual query result rows. Never fabricates numbers.
    """
    if not rows or not columns:
        return {
            "row_count": 0,
            "primary_dimension": None,
            "primary_metric": None,
            "numeric_columns": [],
            "dimension_columns": [],
            "metric_total": None,
            "metric_mean": None,
            "metric_min": None,
            "metric_max": None,
            "top_performer": None,
            "bottom_performer": None,
            "top_share_pct": None,
            "period_over_period_change_pct": None,
            "rankings": [],
            "kpis": [
                {"label": "Matching Rows", "value": "0", "subtext": "Empty result set"}
            ],
        }

    sample = rows[0]
    numeric_cols: List[str] = []
    dimension_cols: List[str] = []

    for col in columns:
        col_l = col.lower()
        # IDs are treated as dimensions unless they are counts
        if col_l.endswith("_id") and not col_l.startswith("count"):
            dimension_cols.append(col)
            continue
        if any(_is_numeric(r.get(col)) for r in rows):
            numeric_cols.append(col)
        else:
            dimension_cols.append(col)

    non_id_dims = [c for c in dimension_cols if not c.lower().endswith("_id") and c.lower() != "id"]
    primary_dim = non_id_dims[0] if non_id_dims else (dimension_cols[0] if dimension_cols else columns[0])
    # Prefer revenue/rate/aov/delta/sales columns as the primary metric
    preferred_metric: Optional[str] = None
    for candidate in numeric_cols:
        cl = candidate.lower()
        if any(
            kw in cl
            for kw in (
                "revenue",
                "aov",
                "average_order_value",
                "rate",
                "delta",
                "change",
                "sales",
                "profit",
                "margin",
                "spend",
                "amount",
            )
        ):
            preferred_metric = candidate
            break
    primary_metric = preferred_metric or (numeric_cols[-1] if numeric_cols else columns[-1])

    metric_values: List[float] = [
        float(r[primary_metric])
        for r in rows
        if _is_numeric(r.get(primary_metric))
    ]

    if not metric_values:
        return {
            "row_count": len(rows),
            "primary_dimension": primary_dim,
            "primary_metric": primary_metric,
            "numeric_columns": numeric_cols,
            "dimension_columns": dimension_cols,
            "metric_total": None,
            "metric_mean": None,
            "metric_min": None,
            "metric_max": None,
            "top_performer": None,
            "bottom_performer": None,
            "top_share_pct": None,
            "period_over_period_change_pct": None,
            "rankings": [],
            "kpis": [
                {"label": "Total Rows", "value": str(len(rows)), "subtext": primary_dim}
            ],
        }

    total_val = round(sum(metric_values), 2)
    mean_val = round(total_val / len(metric_values), 2)
    min_val = round(min(metric_values), 2)
    max_val = round(max(metric_values), 2)

    # Sort rows by primary_metric descending for ranking analysis
    sorted_by_metric = sorted(
        rows,
        key=lambda r: float(r.get(primary_metric, 0.0)) if _is_numeric(r.get(primary_metric)) else float("-inf"),
        reverse=True,
    )
    top_row = sorted_by_metric[0]
    bottom_row = sorted_by_metric[-1]

    top_val = float(top_row.get(primary_metric, 0.0))
    bottom_val = float(bottom_row.get(primary_metric, 0.0))

    is_rate_or_avg = any(
        k in primary_metric.lower() for k in ("rate", "pct", "avg", "average", "aov", "margin")
    )
    top_share_pct: Optional[float] = None
    if not is_rate_or_avg and total_val > 0 and top_val >= 0:
        top_share_pct = round((top_val / total_val) * 100.0, 2)

    # Period-over-period change if ordered chronologically (e.g. month)
    pop_change_pct: Optional[float] = None
    if "month" in primary_dim.lower() or "date" in primary_dim.lower():
        if len(metric_values) >= 2 and metric_values[-2] != 0:
            prev_v = metric_values[-2]
            curr_v = metric_values[-1]
            pop_change_pct = round(((curr_v - prev_v) / abs(prev_v)) * 100.0, 2)

    rankings: List[Dict[str, Any]] = []
    for idx, r in enumerate(sorted_by_metric[:10], start=1):
        val = float(r.get(primary_metric, 0.0)) if _is_numeric(r.get(primary_metric)) else 0.0
        share = round((val / total_val) * 100.0, 2) if (not is_rate_or_avg and total_val > 0) else None
        rankings.append(
            {
                "rank": idx,
                "dimension": str(r.get(primary_dim, "")),
                "metric_value": val,
                "share_pct": share,
            }
        )

    # Build KPI cards for frontend Results Explorer
    kpis: List[Dict[str, Any]] = [
        {
            "label": f"Top {primary_dim.replace('_', ' ').title()}",
            "value": f"{top_row.get(primary_dim)}",
            "subtext": f"{primary_metric}: {top_val:,.2f}",
        },
        {
            "label": (
                f"Average {primary_metric.replace('_', ' ').title()}"
                if is_rate_or_avg
                else f"Total {primary_metric.replace('_', ' ').title()}"
            ),
            "value": f"{mean_val:,.2f}" if is_rate_or_avg else f"{total_val:,.2f}",
            "subtext": f"Across {len(rows)} groups",
        },
        {
            "label": f"Mean {primary_metric.replace('_', ' ').title()}",
            "value": f"{mean_val:,.2f}",
            "subtext": f"Min: {min_val:,.2f} | Max: {max_val:,.2f}",
        },
    ]
    if pop_change_pct is not None:
        kpis.append(
            {
                "label": "Latest MoM Change",
                "value": f"{pop_change_pct:+.2f}%",
                "subtext": f"{rows[-2].get(primary_dim)} -> {rows[-1].get(primary_dim)}",
            }
        )
    elif top_share_pct is not None:
        kpis.append(
            {
                "label": "Leader Share",
                "value": f"{top_share_pct:.2f}%",
                "subtext": f"{top_row.get(primary_dim)} share of total",
            }
        )

    return {
        "row_count": len(rows),
        "primary_dimension": primary_dim,
        "primary_metric": primary_metric,
        "numeric_columns": numeric_cols,
        "dimension_columns": dimension_cols,
        "metric_total": total_val,
        "metric_mean": mean_val,
        "metric_min": min_val,
        "metric_max": max_val,
        "top_performer": {
            "dimension": top_row.get(primary_dim),
            "value": top_val,
        },
        "bottom_performer": {
            "dimension": bottom_row.get(primary_dim),
            "value": bottom_val,
        },
        "top_share_pct": top_share_pct,
        "period_over_period_change_pct": pop_change_pct,
        "rankings": rankings,
        "kpis": kpis,
    }
