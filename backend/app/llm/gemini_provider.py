"""Gemini LLM Provider using the official google-genai SDK."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.llm.base import BaseLLMProvider


def _extract_json_dict(raw_text: str) -> Dict[str, Any]:
    """Parse JSON from model output text, stripping markdown code fences if present."""
    text = (raw_text or "").strip()
    if not text:
        return {}
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"data": parsed}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return {}


class GeminiProvider(BaseLLMProvider):
    """
    Production Gemini provider powered by `google-genai` and configured strictly via `.env`.
    Zero mock fallback in production runtime.
    """

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        fallback_model: str = "gemini-2.5-flash-lite",
        temperature: float = 0.1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.model_name = model
        self.fallback_model = fallback_model
        self.temperature = temperature
        self.client = genai.Client(api_key=api_key)

    def _call_structured_json(
        self,
        system_instruction: str,
        user_prompt: str,
        json_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call Gemini `client.models.generate_content` with structured JSON output."""
        models_to_try = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models_to_try.append(self.fallback_model)
        for default_m in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
            if default_m not in models_to_try:
                models_to_try.append(default_m)

        last_err: Optional[Exception] = None
        for target_model in models_to_try:
            try:
                resp = self.client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=self.temperature,
                        response_mime_type="application/json",
                        response_schema=json_schema,
                    ),
                )
                output_text = getattr(resp, "text", None) or ""
                parsed = _extract_json_dict(output_text)
                if parsed:
                    self.model_name = target_model
                    return parsed
            except Exception as exc:
                last_err = exc
                continue

        raise RuntimeError(
            f"Gemini API call failed across configured models {models_to_try}: {last_err}"
        ) from last_err

    def analyze_request(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Analyze business intent, metrics, dimensions, filters, ambiguity, and schema scope via Gemini."""
        schema = {
            "type": "OBJECT",
            "properties": {
                "business_intent": {"type": "STRING"},
                "metrics": {"type": "ARRAY", "items": {"type": "STRING"}},
                "dimensions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "filters": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_range": {"type": "STRING"},
                "is_ambiguous": {"type": "BOOLEAN"},
                "clarification_question": {"type": "STRING"},
                "scope_status": {
                    "type": "STRING",
                    "enum": ["in_scope", "missing_schema", "unsafe_request", "ambiguous"],
                },
                "relevant_tables": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": [
                "business_intent",
                "metrics",
                "dimensions",
                "filters",
                "time_range",
                "is_ambiguous",
                "clarification_question",
                "scope_status",
                "relevant_tables",
            ],
        }

        history_str = json.dumps(conversation_history or [], indent=2)
        system_instruction = (
            "You are the Request Analyzer for QueryPilot, an AI e-commerce analytics assistant.\n"
            "The PostgreSQL warehouse contains ONLY these 7 tables:\n"
            "- categories (category_id, name, department, target_margin_pct, created_at)\n"
            "- products (product_id, sku, name, category_id, brand, unit_cost, unit_price, is_active, launch_date)\n"
            "- customers (customer_id, email, full_name, segment, region, country, signup_date, lifetime_tier)\n"
            "- orders (order_id, customer_id, order_date, order_timestamp, status, region, channel, subtotal_amount, discount_amount, tax_amount, shipping_amount, total_amount, cancellation_reason)\n"
            "- order_items (order_item_id, order_id, product_id, quantity, unit_price, unit_cost, discount_amount, line_total)\n"
            "- payments (payment_id, order_id, payment_date, payment_method, payment_status, amount, processing_fee)\n"
            "- website_events (event_id, customer_id, session_id, event_timestamp, event_type, product_id, device_type, traffic_source, region)\n\n"
            "Strict Classification Rules:\n"
            "1. If the user asks to modify, delete, drop, truncate, update, insert, grant, copy, lock (FOR UPDATE), or query system tables (pg_catalog, pg_shadow, information_schema) or sleep/read files, set scope_status='unsafe_request' and is_ambiguous=false.\n"
            "2. If the user asks about concepts absent from these 7 tables (e.g., employee salaries, HR payroll, stock prices, weather, support tickets, helpdesk, NPS score, warehouse facility capacity, supplier lead times), set scope_status='missing_schema' and explain in clarification_question which tables are available.\n"
            "3. If the question is too vague to identify a metric or subject (e.g., 'How are things going?', 'Show me the numbers', 'Is performance good?') and Conversation History does not clarify it, set is_ambiguous=true, scope_status='ambiguous', and provide a helpful clarification_question.\n"
            "4. Otherwise set scope_status='in_scope' and is_ambiguous=false."
        )
        prompt = (
            f"Conversation History:\n{history_str}\n\n"
            f"Current User Question:\n{question}\n"
        )
        return self._call_structured_json(system_instruction, prompt, schema)

    def plan_query(
        self,
        question: str,
        intent: Dict[str, Any],
        schema_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Develop an analytical query plan using discovered schema and semantic metrics via Gemini."""
        schema = {
            "type": "OBJECT",
            "properties": {
                "summary": {"type": "STRING"},
                "steps": {"type": "ARRAY", "items": {"type": "STRING"}},
                "required_tables": {"type": "ARRAY", "items": {"type": "STRING"}},
                "joins": {"type": "ARRAY", "items": {"type": "STRING"}},
                "aggregations": {"type": "ARRAY", "items": {"type": "STRING"}},
                "filters": {"type": "ARRAY", "items": {"type": "STRING"}},
                "ordering": {"type": "STRING"},
            },
            "required": [
                "summary",
                "steps",
                "required_tables",
                "joins",
                "aggregations",
                "filters",
                "ordering",
            ],
        }
        system_instruction = (
            "You are the Query Planner for QueryPilot. Create a clear analytical plan "
            "using ONLY the discovered warehouse tables, columns, and valid joins."
        )
        prompt = (
            f"Question: {question}\n"
            f"Parsed Intent: {json.dumps(intent)}\n"
            f"Discovered Tables & Columns: {json.dumps(schema_info.get('table_columns', {}))}\n"
            f"Semantic Metrics: {json.dumps(schema_info.get('semantic_metrics', []))}\n"
            f"Valid Joins: {json.dumps(schema_info.get('valid_joins', []))}\n"
        )
        return self._call_structured_json(system_instruction, prompt, schema)

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
        """Generate dialect-compatible PostgreSQL SELECT query grounded strictly in discovered schema via Gemini."""
        schema = {
            "type": "OBJECT",
            "properties": {
                "sql": {"type": "STRING"},
                "rationale": {"type": "STRING"},
            },
            "required": ["sql", "rationale"],
        }
        feedback_block = ""
        if feedback_errors:
            feedback_block = (
                f"\nPREVIOUS SQL ATTEMPT:\n{previous_sql or ''}\n"
                f"VALIDATION / EXECUTION ERRORS TO FIX:\n"
                + "\n".join(f"- {e}" for e in feedback_errors)
                + "\nFix every error above using ONLY valid tables and columns from the schema."
            )

        system_instruction = (
            "You are the SQL Generator for QueryPilot, an expert PostgreSQL analytics engineer.\n"
            "Strict Rules:\n"
            "1. Output ONLY a single read-only PostgreSQL SELECT statement (CTEs with `WITH ... SELECT` are allowed). Do NOT include a trailing semicolon.\n"
            "2. NEVER use DDL/DML (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, COPY, GRANT).\n"
            "3. NEVER invent tables or columns. Use ONLY the exact table and column names in `table_columns`:\n"
            "   - categories: category_id, name, department, target_margin_pct, created_at\n"
            "   - products: product_id, sku, name, category_id, brand, unit_cost, unit_price, is_active, launch_date\n"
            "   - customers: customer_id, email, full_name, segment, region, country, signup_date, lifetime_tier\n"
            "   - orders: order_id, customer_id, order_date, order_timestamp, status, region, channel, subtotal_amount, discount_amount, tax_amount, shipping_amount, total_amount, cancellation_reason\n"
            "   - order_items: order_item_id, order_id, product_id, quantity, unit_price, unit_cost, discount_amount, line_total\n"
            "   - payments: payment_id, order_id, payment_date, payment_method, payment_status, amount, processing_fee\n"
            "   - website_events: event_id, customer_id, session_id, event_timestamp, event_type, product_id, device_type, traffic_source, region\n"
            "4. Put the primary human-readable label column FIRST in the SELECT list (e.g., `c.name AS category_name`, `c.segment AS customer_segment`, `o.region`, `p.name AS product_name`).\n"
            "5. Note the warehouse date range is 2025-10-01 through 2026-09-30 (latest completed month is 2026-09, previous month is 2026-08; Q2 2026 is 2026-04-01..2026-06-30, Q3 2026 is 2026-07-01..2026-09-30).\n"
            "6. For realized net revenue, sales, or AOV metrics, exclude cancelled and refunded orders (`o.status NOT IN ('cancelled', 'refunded')`) unless the user specifically asks about cancellations or refunds.\n"
            "7. If the user explicitly asks for a cross join or cartesian product across large tables (e.g., customers, website_events, order_items), write the `CROSS JOIN` query as requested so the Cost Estimator and Approval Gate can evaluate and pause it for human review.\n"
            "8. In PostgreSQL, `ROUND(x, 2)` requires `NUMERIC` input: cast `FLOAT` expressions if needed (`ROUND((expr)::numeric, 2)`)."
        )
        prompt = (
            f"Question: {question}\n"
            f"Intent: {json.dumps(intent)}\n"
            f"Query Plan: {json.dumps(query_plan)}\n"
            f"Exact Warehouse Schema (table_columns): {json.dumps(schema_info.get('table_columns', {}))}\n"
            f"Valid Joins: {json.dumps(schema_info.get('valid_joins', []))}\n"
            f"{feedback_block}"
        )
        res = self._call_structured_json(system_instruction, prompt, schema)
        sql_text = (res.get("sql") or "").strip().rstrip(";")
        return {
            "sql": sql_text,
            "rationale": res.get("rationale", "Generated by Gemini using discovered schema."),
            "provider": "gemini",
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
        """Generate evidence-backed business insights grounded strictly in query results via Gemini."""
        schema = {
            "type": "OBJECT",
            "properties": {
                "headline": {"type": "STRING"},
                "summary": {"type": "STRING"},
                "key_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "assumptions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "limitations": {"type": "ARRAY", "items": {"type": "STRING"}},
                "follow_up_suggestions": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": [
                "headline",
                "summary",
                "key_findings",
                "assumptions",
                "limitations",
                "follow_up_suggestions",
            ],
        }
        sample_rows = rows[:20]
        system_instruction = (
            "You are the Executive Analytics Narrator for QueryPilot.\n"
            "Write in clear, non-technical business English for store managers and executives:\n"
            "1. Cite exact numerical figures from `Query Results` and `Statistical Analysis`.\n"
            "2. NEVER invent numbers, tables, or causal explanations unsupported by the returned data.\n"
            "3. Clearly state business assumptions (e.g., excluding cancelled and refunded orders) and data limitations in plain language.\n"
            "4. Suggest 3 natural follow-up business questions."
        )
        prompt = (
            f"User Question: {question}\n"
            f"Executed SQL: {sql}\n"
            f"Statistical Analysis Summary: {json.dumps(analysis, default=str)}\n"
            f"Query Results (top {len(sample_rows)} of {len(rows)} rows): {json.dumps(sample_rows, default=str)}\n"
        )
        return self._call_structured_json(system_instruction, prompt, schema)
