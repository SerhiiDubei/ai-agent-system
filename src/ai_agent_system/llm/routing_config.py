"""Per-operation LLM routing config — loaded from YAML.

Per N10 research: config-driven model selection. Change models without redeploy.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ai_agent_system.config import settings
from ai_agent_system.llm.exceptions import OperationNotConfiguredException

log = logging.getLogger(__name__)


class OperationRouting(BaseModel):
    """Routing rules для одної operation_id."""

    model: str
    fallback_models: list[str] = Field(default_factory=list)
    provider_pin: list[str] | None = None  # OpenRouter provider order
    notes: str | None = None


class Defaults(BaseModel):
    """Global defaults applied to всіх operations якщо не overridden."""

    temperature: float = 0.0
    max_retries: int = 2
    timeout_seconds: int = 90


class BenchmarkConfig(BaseModel):
    """Benchmark candidate set (per N9 — used by /api/v1/benchmark/run)."""

    candidate_models: list[str] = Field(default_factory=list)
    reps_per_combo: int = 2
    golden_set_size: int = 5


class RoutingConfig:
    """Loads + caches llm_routing.yml. Provides lookup per operation_id."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or settings.llm_routing_config_path
        self._defaults: Defaults
        self._operations: dict[str, OperationRouting]
        self._benchmark: BenchmarkConfig
        self._raw: dict[str, Any]
        self._load()

    def _load(self) -> None:
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"LLM routing config not found at {self._config_path}. "
                f"Set LLM_ROUTING_CONFIG_PATH env var або створи configs/llm_routing.yml"
            )

        with self._config_path.open("r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f) or {}

        self._defaults = Defaults(**(self._raw.get("defaults") or {}))

        operations_raw = self._raw.get("operations") or {}
        self._operations = {
            op_id: OperationRouting(**op_cfg)
            for op_id, op_cfg in operations_raw.items()
        }

        self._benchmark = BenchmarkConfig(**(self._raw.get("benchmark") or {}))

        log.info(
            "loaded routing config from %s (%d operations)",
            self._config_path,
            len(self._operations),
        )

    def reload(self) -> None:
        """Hot-reload з диску (для tests + dev)."""
        self._load()

    def get_operation(self, operation_id: str) -> OperationRouting:
        """Look up routing for operation_id. Raises якщо не configured."""
        if operation_id not in self._operations:
            raise OperationNotConfiguredException(operation_id)
        return self._operations[operation_id]

    @property
    def defaults(self) -> Defaults:
        return self._defaults

    @property
    def benchmark(self) -> BenchmarkConfig:
        return self._benchmark

    @property
    def operation_ids(self) -> list[str]:
        return list(self._operations.keys())


@lru_cache(maxsize=1)
def get_routing_config() -> RoutingConfig:
    """Singleton — safe to call from anywhere."""
    return RoutingConfig()
