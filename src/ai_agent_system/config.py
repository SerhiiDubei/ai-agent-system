"""Application settings via Pydantic Settings.

All env vars centralized here. Never read os.environ directly elsewhere —
import `settings` from this module.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """All env-driven settings. Hot-reload safe (frozen via lru_cache)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────
    app_env: Literal["dev", "test", "qa", "prod"] = "dev"
    app_port: int = 8001
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    internal_api_key: SecretStr = Field(default=SecretStr("dev-only-replace-me"))

    # ── Database ─────────────────────────────────
    database_url: str = "postgresql+psycopg://ai_agent:ai_agent@localhost:5432/ai_agent_system"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── LLM / OpenRouter (per N10) ───────────────
    openrouter_api_key: SecretStr = Field(default=SecretStr(""))
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = "https://your-domain.com"
    openrouter_app_title: str = "ai-agent-system"
    llm_routing_config_path: Path = Path("./configs/llm_routing.yml")

    # ── Cost controller ──────────────────────────
    cost_per_call_max_usd: float = 0.30
    cost_per_snapshot_soft_usd: float = 0.50
    cost_per_snapshot_hard_usd: float = 1.50
    cost_daily_cap_usd: float = 5.00
    cost_kill_switch_enabled: bool = False  # toggled через /api/admin/cost/freeze

    # ── Firecrawl (per N1) ───────────────────────
    firecrawl_base_url: str = "http://localhost:3002"
    firecrawl_api_key: str = "anything-self-host-ignores-it"
    firecrawl_timeout_seconds: int = 45
    firecrawl_mobile_parallel: bool = True  # N1: 2 parallel calls > viewport-switch

    fallback_jina_reader_url: str = "https://r.jina.ai"
    fallback_firecrawl_cloud_key: SecretStr = Field(default=SecretStr(""))

    # ── Knowledge / Obsidian ─────────────────────
    obsidian_vault_path: Path = Path("./local-vault")
    knowledge_etl_watch_enabled: bool = True
    knowledge_etl_nightly_cron_enabled: bool = True
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = 1536

    # ── Tracing (per N10) ────────────────────────
    langsmith_tracing: bool = True
    langsmith_api_key: SecretStr = Field(default=SecretStr(""))
    langsmith_project: str = "ai-agent-system"
    langsmith_sampling_rate: float = 1.0

    # ── Rate limiting ────────────────────────────
    rate_limit_requests_per_second: int = 10
    rate_limit_burst: int = 20

    # ── CORS ─────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Singleton settings — safe to call from anywhere."""
    return AppSettings()


# Convenience top-level for typed import
settings = get_settings()
