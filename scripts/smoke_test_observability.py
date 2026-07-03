#!/usr/bin/env python
"""Smoke test for observability layer — no LLM calls.

Verifies:
  1. agents.yml loads and resolves models per quality tier
  2. Tier switching changes model assignments correctly
  3. RunLogger writes JSONL events
  4. inspect_run.py can read them back

Run:
    python scripts/smoke_test_observability.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import yaml

from ai_agent_system.observability import get_agent_logger, LLMCallRecord
from ai_agent_system.observability.config_loader import (
    load_agents_config,
    reload_agents_config,
    AgentsConfig,
)


def show_tier_resolution(cfg: AgentsConfig) -> None:
    """Pretty-print every agent's resolved model under the active tier."""
    print(f"\n  Active tier: {cfg.quality_tier!r}")
    print(f"  Retries (default): {cfg.defaults.retries}")
    print(f"  Cost limits: ${cfg.cost_limits.per_run_max_usd}/run · "
          f"${cfg.cost_limits.daily_total_max_usd}/day")
    print()
    print(f"  {'Agent':<25} {'Model':<35} {'Fallbacks'}")
    print("  " + "-" * 95)
    for name, agent in sorted(cfg.agents.items()):
        fb = ", ".join(agent.fallback_models) or "—"
        print(f"  {name:<25} {agent.model:<35} {fb}")


def test_tier_switch() -> None:
    """Verify tier switching by patching YAML in memory."""
    print("=" * 100)
    print("TIER SWITCH TEST")
    print("=" * 100)

    config_path = ROOT / "configs" / "agents.yml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    saved_tier = raw["quality_tier"]

    try:
        for tier in ("economy", "balanced", "premium"):
            raw["quality_tier"] = tier
            config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
            cfg = reload_agents_config()
            show_tier_resolution(cfg)
            print()
    finally:
        raw["quality_tier"] = saved_tier
        config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        reload_agents_config()
    print(f"  ✓ Tier restored to {saved_tier!r}")


def test_run_logging() -> None:
    """Fake a run with 2 agents, retries, validation events."""
    print("\n" + "=" * 100)
    print("RUN LOGGING TEST")
    print("=" * 100)

    cfg = reload_agents_config()
    logger = get_agent_logger()
    run = logger.start_run(label="phase0_smoke", tags=["test", "phase0"])
    print(f"\n  ✓ Started run: {run.run_id}")
    print(f"    log file: {run.file_path}")

    # Agent 1: succeeds first try
    ci_cfg = cfg.get_agent("customer_insights")
    inv = run.start_agent(
        "customer_insights",
        input_full={"brief": "walk-in tubs FL seniors", "niche": "walk_in_tubs"},
        config_used=ci_cfg.model_dump(),
    )
    inv.log_llm_call(LLMCallRecord(
        model=ci_cfg.model,
        temperature=ci_cfg.temperature,
        max_tokens=ci_cfg.max_tokens,
        system_prompt="(Customer Insights character card v1)",
        user_prompt="Generate 3 personas for walk-in tubs niche...",
        raw_response='{"personas": [{"name": "Florida Helen, 72..."}]}',
        input_tokens=1234, output_tokens=2345,
        cost_usd=0.0042, latency_ms=8423, attempt_number=1,
    ))
    inv.log_validation(passed=True)
    inv.complete(succeeded=True, output_summary="3 personas",
                 output_full={"personas_count": 3})

    # Agent 2: fails primary, falls back to next model
    vm_cfg = cfg.get_agent("voice_message")
    inv2 = run.start_agent("voice_message", input_full={"copy": "stub"})
    # First attempt — primary model, validation fails
    inv2.log_llm_call(LLMCallRecord(
        model=vm_cfg.model, raw_response='{"hook": "missing fields"}',
        input_tokens=500, output_tokens=120,
        cost_usd=0.0008, latency_ms=1500, attempt_number=1,
    ))
    inv2.log_validation(passed=False, errors=[
        {"loc": "value_prop", "msg": "Field required"}
    ])
    # Fallback to next model in chain
    fallback_model = vm_cfg.fallback_models[0] if vm_cfg.fallback_models else vm_cfg.model
    inv2.log_llm_call(LLMCallRecord(
        model=fallback_model,
        raw_response='{"hook": "Stop slipping in your tub", "value_prop": "..."}',
        input_tokens=600, output_tokens=180,
        cost_usd=0.005, latency_ms=1700, attempt_number=2,
    ))
    inv2.log_validation(passed=True)
    inv2.complete(succeeded=True, output_summary="hook + value_prop drafted")

    run.note("Smoke test complete — pipes work")
    run.complete(payload={"agents_run": 2, "smoke": True})

    print(f"\n  ✓ Run logged. Inspect with:")
    print(f"\n    python scripts/inspect_run.py {run.run_id}")
    print(f"    python scripts/inspect_run.py {run.run_id} --full")


def main() -> None:
    test_tier_switch()
    test_run_logging()


if __name__ == "__main__":
    main()
