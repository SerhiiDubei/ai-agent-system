"""Unit tests для RoutingConfig — pure YAML loading + lookup logic."""

from pathlib import Path

import pytest
import yaml

from ai_agent_system.llm.exceptions import OperationNotConfiguredException
from ai_agent_system.llm.routing_config import RoutingConfig


@pytest.fixture
def yaml_path(tmp_path: Path) -> Path:
    cfg = {
        "defaults": {"temperature": 0.0, "max_retries": 2, "timeout_seconds": 90},
        "operations": {
            "agent.copy_expert": {
                "model": "anthropic/claude-3.5-sonnet",
                "fallback_models": ["openai/gpt-4o"],
                "notes": "test",
            },
            "agent.uxui_expert": {
                "model": "anthropic/claude-3.5-sonnet",
            },
            "snapshot.semantic_role_mapping": {
                "model": "openai/gpt-4o",
                "provider_pin": ["OpenAI"],
            },
        },
        "benchmark": {
            "candidate_models": ["openai/gpt-4o-mini", "anthropic/claude-3-haiku"],
            "reps_per_combo": 3,
        },
    }
    p = tmp_path / "llm_routing.yml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


def test_loads_config_from_yaml(yaml_path: Path) -> None:
    cfg = RoutingConfig(config_path=yaml_path)
    assert "agent.copy_expert" in cfg.operation_ids
    assert cfg.defaults.temperature == 0.0
    assert cfg.benchmark.candidate_models == [
        "openai/gpt-4o-mini",
        "anthropic/claude-3-haiku",
    ]


def test_get_operation_returns_routing(yaml_path: Path) -> None:
    cfg = RoutingConfig(config_path=yaml_path)
    op = cfg.get_operation("agent.copy_expert")
    assert op.model == "anthropic/claude-3.5-sonnet"
    assert op.fallback_models == ["openai/gpt-4o"]


def test_get_operation_unknown_raises(yaml_path: Path) -> None:
    cfg = RoutingConfig(config_path=yaml_path)
    with pytest.raises(OperationNotConfiguredException) as exc_info:
        cfg.get_operation("nonexistent.op")
    assert exc_info.value.operation_id == "nonexistent.op"


def test_provider_pin_loaded(yaml_path: Path) -> None:
    cfg = RoutingConfig(config_path=yaml_path)
    op = cfg.get_operation("snapshot.semantic_role_mapping")
    assert op.provider_pin == ["OpenAI"]


def test_missing_yaml_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        RoutingConfig(config_path=tmp_path / "missing.yml")


def test_reload_picks_up_changes(yaml_path: Path) -> None:
    cfg = RoutingConfig(config_path=yaml_path)
    initial_count = len(cfg.operation_ids)

    # Mutate file
    raw = yaml.safe_load(yaml_path.read_text())
    raw["operations"]["new.op"] = {"model": "openai/gpt-4o-mini"}
    yaml_path.write_text(yaml.dump(raw))

    cfg.reload()
    assert "new.op" in cfg.operation_ids
    assert len(cfg.operation_ids) == initial_count + 1
