"""Persistent Expert State (Phase 5g) — file-based v1.

Each agent has a `state/<client_id>/` subfolder where it accumulates
findings across runs for the same client. This is the foundation for
"experts that live their own lives" (the user's vision):
  - Read latest state at run start (so the agent has memory)
  - Write current run's outputs at run end
  - Append to learnings.md so a human can read accumulated insights

State layout (per agent, per client):
  agents/<expert>/state/<client_id>/
    current_state.json          ← latest output (overwritten each run)
    versions/<ts>_v<n>.json     ← history (append-only)
    learnings.md                ← accumulated human-readable insights

For Phase 5g v1: file-based. For production scale: migrate to Postgres
table `expert_state(expert, client_id, payload, version, ts)`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

AGENTS_ROOT = Path(__file__).resolve().parents[4] / "agents"


def state_dir(agent_name: str, client_id: str) -> Path:
    """Return the state directory path for (agent, client). Create if missing."""
    safe_client = "".join(c for c in client_id if c.isalnum() or c in "_-")[:64]
    if not safe_client:
        safe_client = "default"
    p = AGENTS_ROOT / agent_name / "state" / safe_client
    p.mkdir(parents=True, exist_ok=True)
    (p / "versions").mkdir(exist_ok=True)
    return p


def load_current_state(agent_name: str, client_id: str | None) -> dict | None:
    """Read the latest persistent state for this (agent, client).

    Returns None gracefully if no state exists yet OR client_id not provided.
    """
    if not client_id:
        return None
    p = state_dir(agent_name, client_id) / "current_state.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Failed to load state %s: %s", p, e)
        return None


def save_current_state(
    agent_name: str,
    client_id: str | None,
    payload: dict,
    *,
    version_note: str | None = None,
) -> Path | None:
    """Write current state + versioned snapshot.

    Returns the file path written, or None if client_id is missing.
    """
    if not client_id:
        return None

    base = state_dir(agent_name, client_id)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")

    # Compute version number
    versions_dir = base / "versions"
    existing = sorted(versions_dir.glob("*.json"))
    next_v = len(existing) + 1

    # Wrap payload with metadata
    wrapped = {
        "_meta": {
            "agent_name": agent_name,
            "client_id": client_id,
            "version": next_v,
            "saved_at": ts,
            "note": version_note,
        },
        "data": payload,
    }

    # Write current_state (overwrite)
    current = base / "current_state.json"
    current.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # Write versioned snapshot
    versioned = versions_dir / f"{ts}_v{next_v}.json"
    versioned.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    log.info("Saved state: %s (v%d)", current, next_v)
    return current


def append_learning(
    agent_name: str,
    client_id: str | None,
    learning: str,
    *,
    source_run_id: str | None = None,
) -> Path | None:
    """Append a human-readable learning note to learnings.md.

    Returns the file path written, or None if client_id is missing.
    """
    if not client_id:
        return None

    base = state_dir(agent_name, client_id)
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    src = f" (run: `{source_run_id}`)" if source_run_id else ""

    block = f"\n## {ts}{src}\n\n{learning.strip()}\n"

    learnings = base / "learnings.md"
    if not learnings.exists():
        header = (
            f"# Accumulated Learnings — {agent_name} for client `{client_id}`\n\n"
            f"This file is append-only. Each entry is a learning the agent captured "
            f"from a specific run. Read top-to-bottom for chronological context.\n"
        )
        learnings.write_text(header, encoding="utf-8")

    with learnings.open("a", encoding="utf-8") as f:
        f.write(block)

    log.info("Appended learning to %s", learnings)
    return learnings


def render_state_for_prompt(state: dict | None, *, max_chars: int = 3000) -> str:
    """Format persistent state for injection into agent prompts.

    Returns empty string if no state. Truncates if too large.
    """
    if not state:
        return ""

    meta = state.get("_meta", {})
    data = state.get("data", {})

    summary = (
        f"PRIOR STATE (from previous run for this client):\n"
        f"  Agent: {meta.get('agent_name', '?')}\n"
        f"  Client: {meta.get('client_id', '?')}\n"
        f"  Version: {meta.get('version', '?')}\n"
        f"  Saved: {meta.get('saved_at', '?')}\n"
        f"  Note: {meta.get('note', '(none)')}\n\n"
        f"  Previous output:\n"
        f"  ```json\n"
        f"  {json.dumps(data, indent=2, ensure_ascii=False, default=str)[:max_chars]}\n"
        f"  ```\n"
    )
    return summary
