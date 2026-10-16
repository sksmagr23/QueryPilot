"""Environment-backed configuration for QueryPilot."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load root .env if present
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Provider Configuration (Configured exclusively via .env)
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_fallback_model: str = Field(
        default="gemini-2.5-flash-lite", alias="GEMINI_FALLBACK_MODEL"
    )
    gemini_temperature: float = Field(default=0.1, alias="GEMINI_TEMPERATURE")

    # PostgreSQL Warehouse Configuration
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="querypilot", alias="POSTGRES_DB")
    postgres_admin_user: str = Field(
        default="querypilot_admin", alias="POSTGRES_ADMIN_USER"
    )
    postgres_admin_password: str = Field(
        default="querypilot_admin_pass", alias="POSTGRES_ADMIN_PASSWORD"
    )
    postgres_ro_user: str = Field(default="querypilot_ro", alias="POSTGRES_RO_USER")
    postgres_ro_password: str = Field(
        default="querypilot_ro_pass", alias="POSTGRES_RO_PASSWORD"
    )

    database_url: str = Field(
        default="postgresql+psycopg://querypilot_admin:querypilot_admin_pass@localhost:5433/querypilot",
        alias="DATABASE_URL",
    )
    readonly_database_url: str = Field(
        default="postgresql+psycopg://querypilot_ro:querypilot_ro_pass@localhost:5433/querypilot",
        alias="READONLY_DATABASE_URL",
    )
    app_meta_database_url: str = Field(
        default="postgresql+psycopg://querypilot_admin:querypilot_admin_pass@localhost:5433/querypilot",
        alias="APP_META_DATABASE_URL",
    )

    # Safety, Execution & Guardrail Thresholds
    statement_timeout_ms: int = Field(default=5000, alias="STATEMENT_TIMEOUT_MS")
    max_result_rows: int = Field(default=500, alias="MAX_RESULT_ROWS")
    cost_approval_threshold: float = Field(
        default=2500.0, alias="COST_APPROVAL_THRESHOLD"
    )
    large_table_row_threshold: int = Field(
        default=5000, alias="LARGE_TABLE_ROW_THRESHOLD"
    )

    # Separate Bounded Retry Counters
    max_sql_retries: int = Field(default=2, alias="MAX_SQL_RETRIES")
    max_exec_retries: int = Field(default=2, alias="MAX_EXEC_RETRIES")
    max_result_retries: int = Field(default=1, alias="MAX_RESULT_RETRIES")

    # API & Server
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS"
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def active_gemini_api_key(self) -> str:
        return (
            self.gemini_api_key
            or os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        ).strip()

    @property
    def effective_llm_provider(self) -> str:
        """Return 'gemini' configured via .env."""
        return "gemini"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
