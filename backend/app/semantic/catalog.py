"""Semantic catalog of canonical business metrics, dimensions, and valid table joins."""

from __future__ import annotations

from typing import Any, Dict, List

SEMANTIC_METRICS: List[Dict[str, Any]] = [
    {
        "id": "net_revenue",
        "name": "Net Revenue",
        "description": "Total realized merchandise revenue after discounts from non-cancelled, non-refunded orders.",
        "sql_formula": "SUM(oi.line_total) WHERE o.status NOT IN ('cancelled', 'refunded')",
        "tables": ["orders", "order_items"],
        "unit": "USD",
        "synonyms": ["revenue", "sales", "net sales", "total revenue", "product revenue"],
    },
    {
        "id": "order_total_revenue",
        "name": "Order Total Revenue (Incl. Tax & Shipping)",
        "description": "Sum of orders.total_amount for completed/shipped/processing orders.",
        "sql_formula": "SUM(o.total_amount) WHERE o.status NOT IN ('cancelled', 'refunded')",
        "tables": ["orders"],
        "unit": "USD",
        "synonyms": ["gross order value", "billed revenue", "order revenue"],
    },
    {
        "id": "average_order_value",
        "name": "Average Order Value (AOV)",
        "description": "Average order total amount across valid (non-cancelled, non-refunded) orders.",
        "sql_formula": "ROUND(AVG(o.total_amount), 2) WHERE o.status NOT IN ('cancelled', 'refunded')",
        "tables": ["orders", "customers"],
        "unit": "USD",
        "synonyms": ["aov", "average order size", "mean order value", "basket size"],
    },
    {
        "id": "order_cancellation_rate",
        "name": "Order Cancellation Rate (%)",
        "description": "Percentage of all placed orders that ended in 'cancelled' status.",
        "sql_formula": "ROUND(100.0 * SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)",
        "tables": ["orders"],
        "unit": "percent",
        "synonyms": ["cancellation rate", "cancel rate", "cancelled orders percentage"],
    },
    {
        "id": "gross_margin_pct",
        "name": "Gross Margin (%)",
        "description": "Gross profit divided by net line revenue across fulfilled order items.",
        "sql_formula": "ROUND(100.0 * SUM(oi.line_total - (oi.unit_cost * oi.quantity)) / NULLIF(SUM(oi.line_total), 0), 2)",
        "tables": ["orders", "order_items", "products"],
        "unit": "percent",
        "synonyms": ["margin", "profit margin", "gross profit margin"],
    },
    {
        "id": "payment_failure_rate",
        "name": "Payment Failure Rate (%)",
        "description": "Percentage of payment attempts that resulted in 'failed' status.",
        "sql_formula": "ROUND(100.0 * SUM(CASE WHEN p.payment_status = 'failed' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)",
        "tables": ["payments"],
        "unit": "percent",
        "synonyms": ["failed payments", "decline rate", "payment error rate"],
    },
    {
        "id": "session_conversion_rate",
        "name": "Session-to-Purchase Conversion Rate (%)",
        "description": "Percentage of unique website sessions that include a 'purchase' event.",
        "sql_formula": "ROUND(100.0 * COUNT(DISTINCT CASE WHEN we.event_type = 'purchase' THEN we.session_id END) / NULLIF(COUNT(DISTINCT we.session_id), 0), 2)",
        "tables": ["website_events"],
        "unit": "percent",
        "synonyms": ["conversion rate", "funnel conversion", "website conversion"],
    },
]

VALID_JOIN_GRAPH: List[Dict[str, str]] = [
    {
        "left_table": "products",
        "right_table": "categories",
        "join_condition": "products.category_id = categories.category_id",
        "cardinality": "N:1",
        "description": "Each product belongs to one product category.",
    },
    {
        "left_table": "orders",
        "right_table": "customers",
        "join_condition": "orders.customer_id = customers.customer_id",
        "cardinality": "N:1",
        "description": "Each order is placed by one customer.",
    },
    {
        "left_table": "order_items",
        "right_table": "orders",
        "join_condition": "order_items.order_id = orders.order_id",
        "cardinality": "N:1",
        "description": "Each order line item belongs to one parent order.",
    },
    {
        "left_table": "order_items",
        "right_table": "products",
        "join_condition": "order_items.product_id = products.product_id",
        "cardinality": "N:1",
        "description": "Each order line item references one catalog product.",
    },
    {
        "left_table": "payments",
        "right_table": "orders",
        "join_condition": "payments.order_id = orders.order_id",
        "cardinality": "N:1",
        "description": "Each payment attempt is associated with an order.",
    },
    {
        "left_table": "website_events",
        "right_table": "customers",
        "join_condition": "website_events.customer_id = customers.customer_id",
        "cardinality": "N:1",
        "description": "Authenticated website events link to a customer profile.",
    },
    {
        "left_table": "website_events",
        "right_table": "products",
        "join_condition": "website_events.product_id = products.product_id",
        "cardinality": "N:1",
        "description": "Product-scoped website events link to a catalog product.",
    },
]

TABLE_SEMANTIC_DESCRIPTIONS: Dict[str, str] = {
    "categories": "Product categories and departments with target gross margin benchmarks.",
    "products": "Catalog products with SKU, brand, unit cost, unit price, and launch date.",
    "customers": "Registered customers with segment (Enterprise, VIP, SMB, Consumer), region, country, and tier.",
    "orders": "Customer orders with timestamp, status (completed, shipped, processing, cancelled, refunded), region, marketing channel, totals, and cancellation reason.",
    "order_items": "Line-level order items capturing product, quantity, unit price, unit cost, discount, and line_total.",
    "payments": "Payment transactions per order with payment method, status (captured, failed, refunded), amount, and fee.",
    "website_events": "Web analytics funnel events (page_view, product_view, add_to_cart, checkout_start, purchase) by session, device, and traffic source.",
}


def get_semantic_catalog() -> Dict[str, Any]:
    """Return the complete semantic catalog of metrics, joins, and table descriptions."""
    return {
        "metrics": SEMANTIC_METRICS,
        "valid_joins": VALID_JOIN_GRAPH,
        "table_descriptions": TABLE_SEMANTIC_DESCRIPTIONS,
    }
