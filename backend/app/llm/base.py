"""Abstract LLM provider interface and factory for QueryPilot."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.config import get_settings


class BaseLLMProvider(ABC):
    """Interface implemented by GeminiProvider."""

    provider_name: str = "gemini"
    model_name: str = "gemini-2.5-flash"

    @abstractmethod
    def analyze_request(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Identify business intent, metrics, dimensions, filters, time ranges, and ambiguity."""

    @abstractmethod
    def plan_query(
        self,
        question: str,
        intent: Dict[str, Any],
        schema_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Develop an analytical plan and identify required tables, joins, and aggregations."""

    @abstractmethod
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
        """Generate dialect-compatible SQL using only discovered schema information."""

    @abstractmethod
    def generate_response(
        self,
        question: str,
        sql: str,
        rows: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Synthesize business insights grounded strictly in query results and statistical analysis."""


def get_llm_provider(force_provider: Optional[str] = None) -> BaseLLMProvider:
    """
    Return the active GeminiProvider configured via .env (GEMINI_API_KEY, GEMINI_MODEL).
    Allows explicit force_provider='mock' only for offline unit/benchmark test suites.
    """
    settings = get_settings()
    if force_provider and force_provider.strip().lower() == "mock":
        from app.llm.mock_provider import MockProvider

        return MockProvider()

    if not settings.active_gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please configure GEMINI_API_KEY and GEMINI_MODEL in your .env file."
        )

    from app.llm.gemini_provider import GeminiProvider

    return GeminiProvider(
        api_key=settings.active_gemini_api_key,
        model=settings.gemini_model,
        fallback_model=settings.gemini_fallback_model,
        temperature=settings.gemini_temperature,
    )
