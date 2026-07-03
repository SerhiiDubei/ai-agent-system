"""Loader for configs/agents.yml.

Resolution order for an agent's model (highest precedence first):
    1. agents.<name>.model_override  (per-agent hard override)
    2. tiers.<active>.overrides.<name>.model  (tier-specific upgrade)
    3. tiers.<active>.default_model  (tier default)

Same precedence applies to the fallback chain.

Why a separate resolution step:
  Keeps agents.yml HUMAN-READABLE — you see "all agents are economy by default,
  except customer_insights gets sonnet in balanced tier" instead of repeating
  model names in every agent block.

  Code-side, we resolve once at load time and cache. Runtime callers just see
  AgentConfig with model + fallbacks already filled in.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


# ── Schema ────────────────────────────────────────────────────────────────────

QualityTier = Literal["economy", "balanced", "premium"]


class AgentDefaults(BaseModel):
    temperature: float = 0.3
    max_tokens: int = 8192
    timeout_s: int = 120
    retries: int = 1
    retry_on: list[str] = Field(default_factory=lambda: ["ValidationError"])
    retry_backoff_factor: float = 2.0
    log_full_payload: bool = True


class CostLimits(BaseModel):
    per_run_max_usd: float = 0.50
    per_agent_max_usd: float = 0.20
    daily_total_max_usd: float = 25.00
    warn_at_pct: float = 0.75


class TierOverride(BaseModel):
    model: str
    fallbacks: list[str] = Field(default_factory=list)


class TierDefinition(BaseModel):
    default_model: str
    default_fallbacks: list[str] = Field(default_factory=list)
    overrides: dict[str, TierOverride] = Field(default_factory=dict)


class AgentBlock(BaseModel):
    """Raw per-agent block from YAML — before tier resolution."""
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: int | None = None
    retries: int | None = None
    retry_on: list[str] | None = None
    retry_backoff_factor: float | None = None
    log_full_payload: bool | None = None
    model_override: str | None = None
    fallbacks_override: list[str] | None = None


class AgentConfig(BaseModel):
    """Resolved per-agent config — what the agent actually uses at runtime."""
    name: str
    model: str
    fallback_models: list[str] = Field(default_factory=list)
    temperature: float
    max_tokens: int
    timeout_s: int
    retries: int
    retry_on: list[str]
    retry_backoff_factor: float
    log_full_payload: bool


class AgentsConfig(BaseModel):
    quality_tier: QualityTier = "economy"
    tiers: dict[QualityTier, TierDefinition]
    defaults: AgentDefaults
    cost_limits: CostLimits
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    agents_raw: dict[str, AgentBlock] = Field(alias="agents")

    # Computed at __post_init__
    _resolved: dict[str, AgentConfig] = {}

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _resolve_agents(self) -> "AgentsConfig":
        """Resolve every agent's effective config based on active tier."""
        if self.quality_tier not in self.tiers:
            raise ValueError(
                f"quality_tier '{self.quality_tier}' not found in tiers: {list(self.tiers)}"
            )

        active_tier = self.tiers[self.quality_tier]
        resolved: dict[str, AgentConfig] = {}

        for agent_name, block in self.agents_raw.items():
            # Resolve model
            if block.model_override:
                model = block.model_override
                fallbacks = block.fallbacks_override or active_tier.default_fallbacks
            elif agent_name in active_tier.overrides:
                ov = active_tier.overrides[agent_name]
                model = ov.model
                fallbacks = ov.fallbacks
            else:
                model = active_tier.default_model
                fallbacks = list(active_tier.default_fallbacks)

            # Resolve other fields (block overrides defaults)
            resolved[agent_name] = AgentConfig(
                name=agent_name,
                model=model,
                fallback_models=fallbacks,
                temperature=block.temperature if block.temperature is not None else self.defaults.temperature,
                max_tokens=block.max_tokens if block.max_tokens is not None else self.defaults.max_tokens,
                timeout_s=block.timeout_s if block.timeout_s is not None else self.defaults.timeout_s,
                retries=block.retries if block.retries is not None else self.defaults.retries,
                retry_on=block.retry_on if block.retry_on is not None else self.defaults.retry_on,
                retry_backoff_factor=(
                    block.retry_backoff_factor
                    if block.retry_backoff_factor is not None
                    else self.defaults.retry_backoff_factor
                ),
                log_full_payload=(
                    block.log_full_payload
                    if block.log_full_payload is not None
                    else self.defaults.log_full_payload
                ),
            )

        self._resolved = resolved
        return self

    # Public API ──────────────────────────────────────────────────────────────

    def get_agent(self, name: str) -> AgentConfig:
        if name not in self._resolved:
            raise KeyError(
                f"No config for agent '{name}'. Known: {list(self._resolved)}"
            )
        return self._resolved[name]

    @property
    def agents(self) -> dict[str, AgentConfig]:
        """All resolved agent configs (read-only view)."""
        return dict(self._resolved)

    def all_models_in_use(self) -> set[str]:
        """Every model currently referenced (default + fallbacks)."""
        seen: set[str] = set()
        for cfg in self._resolved.values():
            seen.add(cfg.model)
            seen.update(cfg.fallback_models)
        return seen


# ── Loader ────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_agents_config(path: Path | None = None) -> AgentsConfig:
    """Load configs/agents.yml. Cached — call reload_agents_config() to refresh."""
    if path is None:
        project_root = Path(__file__).resolve().parents[3]
        path = project_root / "configs" / "agents.yml"

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AgentsConfig.model_validate(raw)


def reload_agents_config() -> AgentsConfig:
    """Drop the lru_cache and re-read. Use after editing YAML."""
    load_agents_config.cache_clear()
    return load_agents_config()
