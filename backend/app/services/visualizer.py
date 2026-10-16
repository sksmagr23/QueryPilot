"""Visualization Builder service: generates validated Recharts chart specifications."""

from __future__ import annotations

from typing import Any, Dict, List


def build_visualization_spec(
    rows: List[Dict[str, Any]],
    columns: List[str],
    analysis: Dict[str, Any],
    question: str = "",
) -> Dict[str, Any]:
    """
    Generate a validated chart specification compatible with Recharts in the frontend.
    Selects between 'line', 'area', 'bar', 'pie', 'composed', or 'table_only'.
    """
    if not rows or not columns:
        return {
            "chart_type": "table_only",
            "title": "No Data Available for Visualization",
            "subtitle": "Query returned 0 rows",
            "x_key": "",
            "y_keys": [],
            "series": [],
            "data": [],
        }

    primary_dim = analysis.get("primary_dimension") or columns[0]
    primary_metric = analysis.get("primary_metric") or columns[-1]
    numeric_cols: List[str] = analysis.get("numeric_columns") or [primary_metric]

    q_lower = (question or "").lower()
    dim_lower = primary_dim.lower()

    # Determine optimal chart type
    if any(k in dim_lower for k in ("month", "date", "day", "week", "year", "quarter")):
        chart_type = "area" if "revenue" in primary_metric.lower() else "line"
    elif "share" in q_lower or "distribution" in q_lower or (len(rows) <= 5 and "segment" in dim_lower):
        chart_type = "bar"
    elif len(numeric_cols) >= 2 and any(k in q_lower for k in ("compare", "previous month", "why", "declin")):
        chart_type = "composed"
    else:
        chart_type = "bar"

    # Choose up to 2 y_keys for clarity
    y_keys = [primary_metric]
    if chart_type == "composed":
        for col in numeric_cols:
            if col != primary_metric and len(y_keys) < 2:
                y_keys.append(col)

    palette = ["#10b981", "#6366f1", "#f59e0b", "#06b6d4", "#ec4899"]
    series = [
        {
            "key": yk,
            "label": yk.replace("_", " ").title(),
            "color": palette[idx % len(palette)],
            "type": "bar" if idx == 0 else "line",
        }
        for idx, yk in enumerate(y_keys)
    ]

    title_metric = primary_metric.replace("_", " ").title()
    title_dim = primary_dim.replace("_", " ").title()

    return {
        "chart_type": chart_type,
        "title": f"{title_metric} by {title_dim}",
        "subtitle": f"Showing top {min(len(rows), 25)} of {len(rows)} rows",
        "x_key": primary_dim,
        "y_keys": y_keys,
        "series": series,
        "data": rows[:25],
    }
