"""Deterministic, schema-aware Mock LLM provider for offline testing and fallback."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.llm.base import BaseLLMProvider

UNSAFE_KEYWORDS_RE = re.compile(
    r"\b(drop\s+table|delete\s+from|truncate\s+table|update\s+\w+\s+set|insert\s+into|"
    r"alter\s+table|grant\s+all|revoke\s+all|pg_sleep|pg_read_file|pg_terminate_backend|"
    r"dblink|copy\s+\w+\s+to|create\s+table|create\s+role|select\s+\*\s+into|"
    r"for\s+update|pg_catalog|pg_shadow|information_schema)\b",
    re.IGNORECASE,
)

MISSING_SCHEMA_CONCEPTS = [
    ("employee", "employee or HR records"),
    ("salary", "employee salary/payroll data"),
    ("salaries", "employee salary/payroll data"),
    ("payroll", "HR payroll data"),
    ("stock price", "stock market price data"),
    ("share price", "stock market price data"),
    ("weather", "weather or climate records"),
    ("temperature", "weather temperature data"),
    ("competitor", "competitor intelligence data"),
    ("support ticket", "customer support ticket tables"),
    ("helpdesk", "helpdesk ticket tables"),
    ("nps score", "NPS survey tables"),
    ("warehouse capacity", "physical warehouse facility tables"),
    ("supplier lead time", "supplier procurement tables"),
    ("social media follower", "social media follower counts"),
]

AMBIGUOUS_PATTERNS = [
    re.compile(r"^\s*(how\s+are\s+things(\s+going)?|how\s+is\s+business|how\s+are\s+we\s+doing)\??\s*$", re.I),
    re.compile(r"^\s*(show\s+me\s+(the\s+)?(numbers|data|stats|metrics|report|everything))\??\s*$", re.I),
    re.compile(r"^\s*(is\s+it\s+good|is\s+performance\s+good|are\s+we\s+growing|what\s+happened)\??\s*$", re.I),
    re.compile(r"^\s*(analyze\s+this|give\s+me\s+insights|show\s+the\s+best\s+ones|compare\s+them)\??\s*$", re.I),
    re.compile(r"^\s*(what\s+is\s+the\s+rate|what\s+is\s+the\s+total|who\s+is\s+best)\??\s*$", re.I),
]


class MockProvider(BaseLLMProvider):
    """Deterministic, schema-grounded analytical LLM provider that works without API keys."""

    provider_name = "mock"
    model_name = "querypilot-deterministic-v1"

    def analyze_request(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        q_raw = (question or "").strip()
        q = q_raw.lower()

        # 1. Check unsafe / adversarial requests
        if UNSAFE_KEYWORDS_RE.search(q_raw) or ";" in q_raw and any(
            k in q for k in ("drop ", "delete ", "update ", "insert ", "alter ", "truncate ")
        ):
            return {
                "business_intent": "Rejected unsafe or destructive database operation request.",
                "metrics": [],
                "dimensions": [],
                "filters": [],
                "time_range": "all_time",
                "is_ambiguous": False,
                "clarification_question": "",
                "scope_status": "unsafe_request",
                "relevant_tables": [],
            }

        # 2. Check missing schema / out-of-domain concepts
        for phrase, label in MISSING_SCHEMA_CONCEPTS:
            if phrase in q:
                return {
                    "business_intent": f"Requested analysis on unavailable concept ({label}).",
                    "metrics": [],
                    "dimensions": [],
                    "filters": [],
                    "time_range": "all_time",
                    "is_ambiguous": False,
                    "clarification_question": (
                        f"The warehouse does not contain {label}. Available tables are: "
                        "categories, products, customers, orders, order_items, payments, and website_events."
                    ),
                    "scope_status": "missing_schema",
                    "relevant_tables": [],
                }

        # 3. Check ambiguous prompts (unless conversation_history supplies clear context)
        has_context = bool(conversation_history and len(conversation_history) > 0)
        for pat in AMBIGUOUS_PATTERNS:
            if pat.match(q_raw):
                return {
                    "business_intent": "Ambiguous analytical request requiring metric and dimension clarification.",
                    "metrics": [],
                    "dimensions": [],
                    "filters": [],
                    "time_range": "unspecified",
                    "is_ambiguous": True,
                    "clarification_question": (
                        "Could you clarify which business metric (e.g., Net Revenue, Average Order Value, "
                        "Order Cancellation Rate, or Conversion Rate) and breakdown dimension "
                        "(e.g., Product Category, Customer Segment, Region, or Month) you would like to analyze?"
                    ),
                    "scope_status": "ambiguous",
                    "relevant_tables": ["orders", "order_items", "products", "categories", "customers"],
                }

        if len(q.split()) <= 2 and not has_context and not any(
            w in q for w in ("revenue", "orders", "aov", "categories", "products", "customers", "payments", "cancellation", "events")
        ):
            return {
                "business_intent": "Underspecified request requiring clarification.",
                "metrics": [],
                "dimensions": [],
                "filters": [],
                "time_range": "unspecified",
                "is_ambiguous": True,
                "clarification_question": (
                    "Please specify the metric (such as revenue, order count, AOV, or cancellation rate) "
                    "and dimension (category, product, customer segment, or region) you want to explore."
                ),
                "scope_status": "ambiguous",
                "relevant_tables": ["orders", "products", "customers"],
            }

        # Combine with prior turn context if this is a follow-up question
        combined_q = q
        if has_context and any(
            phrase in q
            for phrase in ("what about", "break that down", "filter", "only for", "by region", "by segment", "by category", "top 5", "instead", "same for")
        ):
            prev_questions = " ".join(
                turn.get("question", "") or turn.get("content", "")
                for turn in (conversation_history or [])
            ).lower()
            combined_q = f"{prev_questions} | follow_up: {q}"

        # Identify metrics, dimensions, and relevant tables
        metrics: List[str] = []
        dimensions: List[str] = []
        filters: List[str] = []
        relevant_tables: List[str] = ["orders"]

        if "cancel" in combined_q:
            metrics.append("order_cancellation_rate")
        if "aov" in combined_q or "average order value" in combined_q or "basket" in combined_q:
            metrics.append("average_order_value")
        if "margin" in combined_q or "profit" in combined_q:
            metrics.append("gross_margin")
            relevant_tables.extend(["order_items", "products"])
        if "payment" in combined_q or "processing fee" in combined_q or "failed payment" in combined_q:
            metrics.append("payment_metrics")
            relevant_tables.append("payments")
        if "event" in combined_q or "funnel" in combined_q or "session" in combined_q or "conversion" in combined_q or "device" in combined_q or "traffic" in combined_q:
            metrics.append("website_funnel_metrics")
            relevant_tables.append("website_events")
        if not metrics or "revenue" in combined_q or "sales" in combined_q:
            if "net_revenue" not in metrics:
                metrics.append("net_revenue")
            relevant_tables.extend(["order_items", "products", "categories"])

        if "category" in combined_q or "categories" in combined_q or "department" in combined_q:
            dimensions.append("category")
            relevant_tables.extend(["order_items", "products", "categories"])
        if "product" in combined_q or "sku" in combined_q or "brand" in combined_q or "declining" in combined_q:
            dimensions.append("product")
            relevant_tables.extend(["order_items", "products", "categories"])
        if "segment" in combined_q or "customer" in combined_q or "tier" in combined_q or "country" in combined_q:
            dimensions.append("customer_segment")
            relevant_tables.append("customers")
        if "region" in combined_q:
            dimensions.append("region")
        if "channel" in combined_q:
            dimensions.append("channel")
        if "month" in combined_q or "trend" in combined_q or "decrease" in combined_q or "declining" in combined_q:
            dimensions.append("month")

        unique_tables = []
        for t in relevant_tables:
            if t not in unique_tables:
                unique_tables.append(t)

        return {
            "business_intent": f"Analyze {', '.join(metrics)} grouped by {', '.join(dimensions or ['overall'])}.",
            "metrics": metrics,
            "dimensions": dimensions or ["overall"],
            "filters": filters,
            "time_range": "2025-10 to 2026-09",
            "is_ambiguous": False,
            "clarification_question": "",
            "scope_status": "in_scope",
            "relevant_tables": unique_tables,
            "resolved_question": combined_q,
        }

    def plan_query(
        self,
        question: str,
        intent: Dict[str, Any],
        schema_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        rel_tables = intent.get("relevant_tables") or ["orders", "order_items", "products", "categories"]
        metrics = intent.get("metrics") or ["net_revenue"]
        dims = intent.get("dimensions") or ["category"]

        joins: List[str] = []
        if "order_items" in rel_tables and "orders" in rel_tables:
            joins.append("order_items.order_id = orders.order_id")
        if "order_items" in rel_tables and "products" in rel_tables:
            joins.append("order_items.product_id = products.product_id")
        if "products" in rel_tables and "categories" in rel_tables:
            joins.append("products.category_id = categories.category_id")
        if "customers" in rel_tables and "orders" in rel_tables:
            joins.append("orders.customer_id = customers.customer_id")
        if "payments" in rel_tables and "orders" in rel_tables:
            joins.append("payments.order_id = orders.order_id")

        return {
            "summary": f"Compute {', '.join(metrics)} across {', '.join(dims)} using {', '.join(rel_tables)}.",
            "steps": [
                f"Select base records from {', '.join(rel_tables)}",
                f"Apply verified joins: {', '.join(joins) if joins else 'single table scan'}",
                "Apply business status filters and compute aggregations",
                "Order results by primary metric descending",
            ],
            "required_tables": rel_tables,
            "joins": joins,
            "aggregations": metrics,
            "filters": intent.get("filters", []),
            "ordering": "primary_metric DESC",
        }

    def generate_sql(
        self,
        question: str,
        intent: Dict[str, Any],
        query_plan: Dict[str, Any],
        schema_info: Dict[str, Any],
        dialect: str = "postgresql",
        feedback_errors: Optional[List[str]] = None,
        previous_sql: Optional[str] = None,
    ) -> Dict[str, Any]:
        q = (intent.get("resolved_question") or question or "").lower()

        # If this is a retry correcting an intentionally broken SQL in recovery tests:
        if feedback_errors and previous_sql:
            # Repair common column/table errors or fall through to canonical query generation
            pass

        # Check if prompt explicitly tests expensive cross-join / cartesian query for approval gate
        if "cross join" in q or "cartesian" in q or "every combination of customer and website event" in q or "unfiltered raw join of all events and order items" in q:
            sql = (
                "SELECT c.customer_id, c.segment, we.event_id, we.event_type, oi.order_item_id, oi.line_total "
                "FROM customers c "
                "CROSS JOIN website_events we "
                "CROSS JOIN order_items oi"
            )
            return {
                "sql": sql,
                "rationale": "Constructed cross-table join as requested (subject to cost estimator and approval gate).",
                "provider": "mock",
                "model": self.model_name,
            }

        # Flagship 2: Why did revenue decrease compared with the previous month?
        if (
            "previous month" in q
            or "month over month" in q
            or "mom" in q
            or ("august" in q and "september" in q)
            or (("why" in q or "decrease" in q or "drop" in q) and ("month" in q or "revenue" in q))
        ):
            if "channel" in q and "why" not in q and "decrease" not in q and "drop" not in q:
                sql = """
SELECT
    o.channel,
    ROUND(SUM(CASE WHEN o.order_date >= '2026-08-01' AND o.order_date < '2026-09-01' AND o.status NOT IN ('cancelled', 'refunded') THEN o.total_amount ELSE 0 END), 2) AS aug_2026_revenue,
    ROUND(SUM(CASE WHEN o.order_date >= '2026-09-01' AND o.order_date <= '2026-09-30' AND o.status NOT IN ('cancelled', 'refunded') THEN o.total_amount ELSE 0 END), 2) AS sep_2026_revenue,
    ROUND(
        SUM(CASE WHEN o.order_date >= '2026-09-01' AND o.order_date <= '2026-09-30' AND o.status NOT IN ('cancelled', 'refunded') THEN o.total_amount ELSE 0 END)
        - SUM(CASE WHEN o.order_date >= '2026-08-01' AND o.order_date < '2026-09-01' AND o.status NOT IN ('cancelled', 'refunded') THEN o.total_amount ELSE 0 END),
        2
    ) AS revenue_change
FROM orders o
WHERE o.order_date >= '2026-08-01'
GROUP BY o.channel
ORDER BY revenue_change ASC
""".strip()
            else:
                sql = """
WITH monthly_channel AS (
    SELECT
        o.channel AS driver_dimension,
        ROUND(SUM(CASE WHEN o.order_date >= '2026-08-01' AND o.order_date < '2026-09-01' AND o.status NOT IN ('cancelled', 'refunded') THEN o.total_amount ELSE 0 END), 2) AS prev_month_revenue,
        ROUND(SUM(CASE WHEN o.order_date >= '2026-09-01' AND o.order_date <= '2026-09-30' AND o.status NOT IN ('cancelled', 'refunded') THEN o.total_amount ELSE 0 END), 2) AS current_month_revenue,
        SUM(CASE WHEN o.order_date >= '2026-08-01' AND o.order_date < '2026-09-01' AND o.status = 'cancelled' THEN 1 ELSE 0 END) AS prev_month_cancelled_orders,
        SUM(CASE WHEN o.order_date >= '2026-09-01' AND o.order_date <= '2026-09-30' AND o.status = 'cancelled' THEN 1 ELSE 0 END) AS current_month_cancelled_orders
    FROM orders o
    WHERE o.order_date >= '2026-08-01' AND o.order_date <= '2026-09-30'
    GROUP BY o.channel
)
SELECT
    driver_dimension,
    prev_month_revenue,
    current_month_revenue,
    ROUND(current_month_revenue - prev_month_revenue, 2) AS revenue_delta,
    ROUND(100.0 * (current_month_revenue - prev_month_revenue) / NULLIF(prev_month_revenue, 0), 2) AS pct_change,
    prev_month_cancelled_orders,
    current_month_cancelled_orders
FROM monthly_channel
ORDER BY revenue_delta ASC
""".strip()
            return {
                "sql": sql,
                "rationale": "Compared monthly realized revenue and cancellation drivers between August 2026 and September 2026.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Flagship 4: Which products have declining sales?
        if "declin" in q and ("product" in q or "sales" in q or "item" in q):
            sql = """
WITH product_periods AS (
    SELECT
        p.product_id,
        p.sku,
        p.name AS product_name,
        c.name AS category_name,
        ROUND(SUM(CASE WHEN o.order_date >= '2026-04-01' AND o.order_date < '2026-07-01' THEN oi.line_total ELSE 0 END), 2) AS q2_2026_sales,
        ROUND(SUM(CASE WHEN o.order_date >= '2026-07-01' AND o.order_date <= '2026-09-30' THEN oi.line_total ELSE 0 END), 2) AS q3_2026_sales
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    JOIN products p ON oi.product_id = p.product_id
    JOIN categories c ON p.category_id = c.category_id
    WHERE o.status NOT IN ('cancelled', 'refunded')
    GROUP BY p.product_id, p.sku, p.name, c.name
)
SELECT
    sku,
    product_name,
    category_name,
    q2_2026_sales,
    q3_2026_sales,
    ROUND(q3_2026_sales - q2_2026_sales, 2) AS sales_change,
    ROUND(100.0 * (q3_2026_sales - q2_2026_sales) / NULLIF(q2_2026_sales, 0), 2) AS decline_pct
FROM product_periods
WHERE q2_2026_sales > 0 AND q3_2026_sales < q2_2026_sales
ORDER BY sales_change ASC
LIMIT 10
""".strip()
            return {
                "sql": sql,
                "rationale": "Compared Q2 2026 vs Q3 2026 realized line-item sales per product to identify products with declining sales.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Flagship 5: Which regions have the highest order cancellation rates?
        if "cancel" in q:
            if "reason" in q:
                sql = """
SELECT
    o.cancellation_reason,
    COUNT(*) AS cancelled_orders,
    ROUND(SUM(o.total_amount), 2) AS lost_order_value
FROM orders o
WHERE o.status = 'cancelled' AND o.cancellation_reason IS NOT NULL
GROUP BY o.cancellation_reason
ORDER BY cancelled_orders DESC
""".strip()
            elif "category" in q:
                sql = """
SELECT
    c.name AS category_name,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT CASE WHEN o.status = 'cancelled' THEN o.order_id END) AS cancelled_orders,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN o.status = 'cancelled' THEN o.order_id END) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS cancellation_rate_pct
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
GROUP BY c.name
ORDER BY cancellation_rate_pct DESC
""".strip()
            elif "month" in q:
                sql = """
SELECT
    TO_CHAR(DATE_TRUNC('month', o.order_date), 'YYYY-MM') AS order_month,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
    ROUND(100.0 * SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS cancellation_rate_pct
FROM orders o
GROUP BY 1
ORDER BY 1 ASC
""".strip()
            else:
                sql = """
SELECT
    o.region,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
    ROUND(100.0 * SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS cancellation_rate_pct,
    ROUND(SUM(CASE WHEN o.status = 'cancelled' THEN o.total_amount ELSE 0 END), 2) AS cancelled_order_value
FROM orders o
GROUP BY o.region
ORDER BY cancellation_rate_pct DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Calculated order cancellation rate and cancelled volume grouped by the requested dimension.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Flagship 3: What is the average order value by customer segment?
        if ("aov" in q or "average order value" in q or ("average" in q and "order" in q)) and "month" not in q and "country" not in q and "countries" not in q:
            if "region" in q and "segment" not in q:
                sql = """
SELECT
    o.region,
    COUNT(o.order_id) AS completed_orders,
    ROUND(AVG(o.total_amount), 2) AS average_order_value,
    ROUND(SUM(o.total_amount), 2) AS total_revenue
FROM orders o
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY o.region
ORDER BY average_order_value DESC
""".strip()
            elif "channel" in q:
                sql = """
SELECT
    o.channel,
    COUNT(o.order_id) AS completed_orders,
    ROUND(AVG(o.total_amount), 2) AS average_order_value,
    ROUND(SUM(o.total_amount), 2) AS total_revenue
FROM orders o
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY o.channel
ORDER BY average_order_value DESC
""".strip()
            elif "tier" in q:
                sql = """
SELECT
    c.lifetime_tier,
    COUNT(o.order_id) AS completed_orders,
    ROUND(AVG(o.total_amount), 2) AS average_order_value,
    ROUND(SUM(o.total_amount), 2) AS total_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY c.lifetime_tier
ORDER BY average_order_value DESC
""".strip()
            else:
                sql = """
SELECT
    c.segment AS customer_segment,
    COUNT(o.order_id) AS valid_orders,
    ROUND(AVG(o.total_amount), 2) AS average_order_value,
    ROUND(SUM(o.total_amount), 2) AS total_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY c.segment
ORDER BY average_order_value DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Computed Average Order Value (AOV) across non-cancelled, non-refunded orders.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Empty result test case: future year or impossible filter
        if "2029" in q or "2030" in q or "antarctica" in q:
            sql = """
SELECT
    o.region,
    COUNT(*) AS order_count,
    ROUND(SUM(o.total_amount), 2) AS total_revenue
FROM orders o
WHERE o.order_date >= '2029-01-01'
GROUP BY o.region
""".strip()
            return {
                "sql": sql,
                "rationale": "Filtered orders for the requested future date range.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Website events / funnel / conversion / device / traffic queries
        if any(w in q for w in ("website", "event", "funnel", "session", "conversion", "device", "traffic")):
            if "device" in q:
                sql = """
SELECT
    we.device_type,
    COUNT(DISTINCT we.session_id) AS total_sessions,
    COUNT(DISTINCT CASE WHEN we.event_type = 'purchase' THEN we.session_id END) AS purchase_sessions,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN we.event_type = 'purchase' THEN we.session_id END) / NULLIF(COUNT(DISTINCT we.session_id), 0), 2) AS conversion_rate_pct
FROM website_events we
GROUP BY we.device_type
ORDER BY total_sessions DESC
""".strip()
            elif "traffic" in q or "source" in q:
                sql = """
SELECT
    we.traffic_source,
    COUNT(DISTINCT we.session_id) AS total_sessions,
    COUNT(DISTINCT CASE WHEN we.event_type = 'purchase' THEN we.session_id END) AS purchase_sessions,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN we.event_type = 'purchase' THEN we.session_id END) / NULLIF(COUNT(DISTINCT we.session_id), 0), 2) AS conversion_rate_pct
FROM website_events we
GROUP BY we.traffic_source
ORDER BY conversion_rate_pct DESC
""".strip()
            else:
                sql = """
SELECT
    we.event_type,
    COUNT(*) AS event_count,
    COUNT(DISTINCT we.session_id) AS unique_sessions
FROM website_events we
GROUP BY we.event_type
ORDER BY unique_sessions DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Aggregated website funnel events and session conversion metrics.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Payment queries
        if "payment" in q or "processing fee" in q:
            if "status" in q and "method" not in q:
                sql = """
SELECT
    p.payment_status,
    COUNT(*) AS payment_count,
    ROUND(SUM(p.amount), 2) AS total_amount,
    ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS share_pct
FROM payments p
GROUP BY p.payment_status
ORDER BY payment_count DESC
""".strip()
            else:
                sql = """
SELECT
    p.payment_method,
    COUNT(*) AS transaction_count,
    ROUND(SUM(p.amount), 2) AS total_processed_amount,
    ROUND(SUM(p.processing_fee), 2) AS total_processing_fees,
    ROUND(100.0 * SUM(CASE WHEN p.payment_status = 'failed' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS failure_rate_pct
FROM payments p
GROUP BY p.payment_method
ORDER BY total_processed_amount DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Analyzed payment volume, processing fees, and failure rates by payment method.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Profit margin queries
        if "margin" in q or "profit" in q:
            if "product" in q or "brand" in q:
                sql = """
SELECT
    p.name AS product_name,
    p.brand,
    ROUND(SUM(oi.line_total), 2) AS net_revenue,
    ROUND(SUM(oi.line_total - (oi.unit_cost * oi.quantity)), 2) AS gross_profit,
    ROUND(100.0 * SUM(oi.line_total - (oi.unit_cost * oi.quantity)) / NULLIF(SUM(oi.line_total), 0), 2) AS gross_margin_pct
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY p.name, p.brand
ORDER BY gross_profit DESC
LIMIT 10
""".strip()
            else:
                sql = """
SELECT
    c.name AS category_name,
    c.department,
    ROUND(SUM(oi.line_total), 2) AS net_revenue,
    ROUND(SUM(oi.line_total - (oi.unit_cost * oi.quantity)), 2) AS gross_profit,
    ROUND(100.0 * SUM(oi.line_total - (oi.unit_cost * oi.quantity)) / NULLIF(SUM(oi.line_total), 0), 2) AS realized_margin_pct,
    c.target_margin_pct
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY c.name, c.department, c.target_margin_pct
ORDER BY gross_profit DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Calculated realized gross profit and gross margin percentage from fulfilled order line items.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Brand breakdown
        if "brand" in q:
            sql = """
SELECT
    p.brand,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(oi.quantity) AS units_sold,
    ROUND(SUM(oi.line_total), 2) AS net_revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY p.brand
ORDER BY net_revenue DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Aggregated units sold and net revenue by product brand.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Department breakdown
        if "department" in q:
            sql = """
SELECT
    c.department,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(oi.quantity) AS units_sold,
    ROUND(SUM(oi.line_total), 2) AS net_revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY c.department
ORDER BY net_revenue DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Aggregated realized net revenue and units sold by category department.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Country breakdown
        if "country" in q or "countries" in q:
            sql = """
SELECT
    c.country,
    c.region,
    COUNT(DISTINCT o.order_id) AS valid_orders,
    ROUND(SUM(o.total_amount), 2) AS total_revenue,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY c.country, c.region
ORDER BY total_revenue DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Aggregated order volume, revenue, and AOV by customer country.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Top customers / lifetime tier
        if "top customer" in q or "customers by" in q or "spending customer" in q:
            sql = """
SELECT
    c.customer_id,
    c.full_name,
    c.segment,
    c.region,
    c.lifetime_tier,
    COUNT(o.order_id) AS completed_orders,
    ROUND(SUM(o.total_amount), 2) AS lifetime_spend
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY c.customer_id, c.full_name, c.segment, c.region, c.lifetime_tier
ORDER BY lifetime_spend DESC
LIMIT 10
""".strip()
            return {
                "sql": sql,
                "rationale": "Ranked top customers by realized lifetime spend.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Top products by revenue/units (excluding "product categories" queries)
        if ("product" in q or "sku" in q) and "categor" not in q and ("top" in q or "most" in q or "best" in q or "revenue" in q or "sales" in q):
            sql = """
SELECT
    p.sku,
    p.name AS product_name,
    c.name AS category_name,
    SUM(oi.quantity) AS units_sold,
    ROUND(SUM(oi.line_total), 2) AS net_revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY p.sku, p.name, c.name
ORDER BY net_revenue DESC
LIMIT 10
""".strip()
            return {
                "sql": sql,
                "rationale": "Ranked products by realized net revenue and units sold.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Channel breakdown
        if "channel" in q:
            sql = """
SELECT
    o.channel,
    COUNT(o.order_id) AS valid_orders,
    ROUND(SUM(o.total_amount), 2) AS total_revenue,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value
FROM orders o
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY o.channel
ORDER BY total_revenue DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Aggregated order count, total revenue, and AOV by acquisition channel.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Region breakdown
        if "region" in q and "category" not in q:
            sql = """
SELECT
    o.region,
    COUNT(o.order_id) AS valid_orders,
    ROUND(SUM(o.total_amount), 2) AS total_revenue,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value
FROM orders o
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY o.region
ORDER BY total_revenue DESC
""".strip()
            return {
                "sql": sql,
                "rationale": "Aggregated realized order volume, revenue, and AOV by region.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Monthly trend
        if "month" in q or "trend" in q or "over time" in q:
            sql = """
SELECT
    TO_CHAR(DATE_TRUNC('month', o.order_date), 'YYYY-MM') AS order_month,
    COUNT(o.order_id) AS valid_orders,
    ROUND(SUM(o.total_amount), 2) AS total_revenue,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value
FROM orders o
WHERE o.status NOT IN ('cancelled', 'refunded')
GROUP BY 1
ORDER BY 1 ASC
""".strip()
            return {
                "sql": sql,
                "rationale": "Aggregated monthly order count, revenue, and AOV trend.",
                "provider": "mock",
                "model": self.model_name,
            }

        # Default / Flagship 1: Which product categories generate the most revenue?
        where_extra = ""
        if "enterprise" in q:
            where_extra = " AND cust.segment = 'Enterprise'"
        elif "north america" in q:
            where_extra = " AND o.region = 'North America'"
        elif "europe" in q:
            where_extra = " AND o.region = 'Europe'"
        elif "latam" in q:
            where_extra = " AND o.region = 'LATAM'"
        elif "apac" in q:
            where_extra = " AND o.region = 'APAC'"

        join_cust = "JOIN customers cust ON o.customer_id = cust.customer_id" if "cust." in where_extra else ""
        sql = f"""
SELECT
    c.name AS category_name,
    c.department,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(oi.quantity) AS units_sold,
    ROUND(SUM(oi.line_total), 2) AS net_revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
{join_cust}
JOIN products p ON oi.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
WHERE o.status NOT IN ('cancelled', 'refunded'){where_extra}
GROUP BY c.name, c.department
ORDER BY net_revenue DESC
""".strip()
        return {
            "sql": sql,
            "rationale": "Joined order_items, orders, products, and categories to rank product categories by realized net revenue.",
            "provider": "mock",
            "model": self.model_name,
        }

    def generate_response(
        self,
        question: str,
        sql: str,
        rows: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not rows:
            return {
                "headline": "No Matching Records Found for Query Criteria",
                "summary": (
                    "The validated query executed successfully against the warehouse but returned 0 rows. "
                    "No numerical claims or extrapolations can be made without matching records."
                ),
                "key_findings": [
                    "Query returned 0 rows for the specified filters/time range.",
                    "Warehouse data covers 2025-10-01 through 2026-09-30 across North America, Europe, APAC, and LATAM.",
                ],
                "assumptions": [
                    "Applied exact filter criteria from the natural-language request.",
                ],
                "limitations": [
                    "Insufficient evidence: 0 matching records in the synthetic warehouse for these constraints.",
                ],
                "follow_up_suggestions": [
                    "Which product categories generate the most revenue?",
                    "What is the monthly revenue trend from 2025-10 to 2026-09?",
                ],
            }

        dim_col = analysis.get("primary_dimension") or list(rows[0].keys())[0]
        metric_col = analysis.get("primary_metric") or list(rows[0].keys())[-1]
        top_row = rows[0]
        bottom_row = rows[-1]
        top_dim = top_row.get(dim_col)
        top_val = top_row.get(metric_col)
        total_val = analysis.get("metric_total")
        top_share = analysis.get("top_share_pct")

        findings: List[str] = []
        for idx, r in enumerate(rows[:4], start=1):
            d_label = r.get(dim_col)
            m_val = r.get(metric_col)
            extra_pairs = [
                f"{k}={v}"
                for k, v in r.items()
                if k not in (dim_col, metric_col)
            ][:2]
            extra_str = f" ({', '.join(extra_pairs)})" if extra_pairs else ""
            findings.append(f"#{idx} {d_label}: {metric_col} = {m_val}{extra_str}")

        if analysis.get("period_over_period_change_pct") is not None:
            findings.append(
                f"Overall period change across returned rows: {analysis['period_over_period_change_pct']}%."
            )

        headline = f"{top_dim} leads on {metric_col} ({top_val})"
        if "decrease" in question.lower() or "why" in question.lower():
            headline = f"Primary driver of revenue change: {top_dim} ({metric_col}: {top_val})"
        elif "declin" in question.lower():
            headline = f"Steepest sales decline observed in {top_dim} ({metric_col}: {top_val})"

        share_clause = f", representing {top_share}% of the total ({total_val})" if top_share is not None else ""
        summary = (
            f"Based on {len(rows)} aggregated result rows from the warehouse, "
            f"{top_dim} ranked first for {metric_col} at {top_val}{share_clause}, "
            f"while {bottom_row.get(dim_col)} recorded {bottom_row.get(metric_col)}."
        )

        return {
            "headline": headline,
            "summary": summary,
            "key_findings": findings,
            "assumptions": [
                "Excluded cancelled and refunded orders when calculating realized revenue and AOV metrics unless cancellation analysis was explicitly requested.",
                "All figures are derived directly from the read-only PostgreSQL warehouse (2025-10-01 to 2026-09-30).",
            ],
            "limitations": [
                "Observational warehouse aggregates reflect recorded transaction and funnel data; external macroeconomic or off-platform ad spend factors are not stored in the schema.",
            ],
            "follow_up_suggestions": [
                "How does this breakdown compare across customer segments (Enterprise, VIP, SMB, Consumer)?",
                "Which regions have the highest order cancellation rates?",
                "Which products have declining sales between Q2 and Q3 2026?",
            ],
        }
