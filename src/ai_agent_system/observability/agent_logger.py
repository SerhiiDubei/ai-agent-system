"""AgentLogger — centralized logger for all agent activity.

Usage pattern (from inside an agent):

    from ai_agent_system.observability import get_agent_logger

    logger = get_agent_logger()
    run = logger.start_run(label="homeiq.io draft")    # → returns RunLogger

    # Inside an agent invocation
    inv = run.start_agent("customer_insights", input_full={"brief": ...})
    inv.log_llm_call(LLMCallRecord(model=..., system_prompt=..., raw_response=..., ...))
    inv.complete(output_full={...}, succeeded=True)

    run.complete()

What hits disk:
    logs/agent_runs/2026-04-28/<run_id>.jsonl
        — one JSONL line per LogEvent
        — append-only, crash-safe
        — no rewrites, no locking issues across agents
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_agent_system.observability.models import (
    AgentInvocationRecord,
    EventType,
    LLMCallRecord,
    LogEvent,
)

log = logging.getLogger(__name__)


# ── Global singleton (one per process) ────────────────────────────────────────

_singleton: "AgentLogger | None" = None
_singleton_lock = threading.Lock()


def get_agent_logger(log_root: Path | None = None) -> "AgentLogger":
    """Return process-wide singleton. Lazy-init on first call."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                if log_root is None:
                    # Default: project_root/logs/agent_runs
                    log_root = Path(__file__).resolve().parents[3] / "logs" / "agent_runs"
                _singleton = AgentLogger(log_root)
    return _singleton


# ── Top-level logger ──────────────────────────────────────────────────────────

class AgentLogger:
    """Process-wide logger. Creates one RunLogger per request."""

    def __init__(self, log_root: Path) -> None:
        self.log_root = log_root
        self.log_root.mkdir(parents=True, exist_ok=True)

    def start_run(
        self,
        *,
        label: str | None = None,
        run_id: str | None = None,
        tags: list[str] | None = None,
    ) -> "RunLogger":
        """Begin a new run. Creates the JSONL file and emits RUN_START."""
        rid = run_id or uuid4().hex[:12]
        day = date.today().isoformat()
        run_dir = self.log_root / day
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / f"{rid}.jsonl"

        rl = RunLogger(run_id=rid, file_path=path, label=label, tags=tags or [])
        rl._emit(
            EventType.RUN_START,
            message=f"Run started: {label or rid}",
            payload={"label": label, "tags": tags or []},
        )
        return rl


# ── Per-run logger ────────────────────────────────────────────────────────────

class RunLogger:
    """One instance per run. Hands out AgentInvocationLogger objects."""

    def __init__(
        self,
        *,
        run_id: str,
        file_path: Path,
        label: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.file_path = file_path
        self.label = label
        self.tags = tags or []
        self._lock = threading.Lock()
        self._t0 = time.monotonic()

    # Public API ──────────────────────────────────────────────────────────────

    def start_agent(
        self,
        agent_name: str,
        *,
        input_full: dict[str, Any] | None = None,
        config_used: dict[str, Any] | None = None,
    ) -> "AgentInvocationLogger":
        """Begin an agent invocation. Each gets a unique agent_invocation_id."""
        ail = AgentInvocationLogger(
            run=self,
            agent_name=agent_name,
            input_full=input_full,
            config_used=config_used or {},
        )
        self._emit(
            EventType.AGENT_START,
            agent_name=agent_name,
            agent_invocation_id=ail.invocation_id,
            message=f"Agent {agent_name} started",
            payload={"input": input_full, "config": config_used or {}},
        )
        return ail

    def note(self, message: str, payload: dict[str, Any] | None = None) -> None:
        """Free-form annotation (debug, intermediate state)."""
        self._emit(
            EventType.NOTE,
            message=message,
            payload=payload or {},
        )

    def complete(self, payload: dict[str, Any] | None = None) -> None:
        elapsed_ms = int((time.monotonic() - self._t0) * 1000)
        self._emit(
            EventType.RUN_COMPLETE,
            message=f"Run complete in {elapsed_ms} ms",
            payload={"total_latency_ms": elapsed_ms, **(payload or {})},
        )

    def abort(self, reason: str, payload: dict[str, Any] | None = None) -> None:
        self._emit(
            EventType.RUN_ABORT,
            message=f"Run aborted: {reason}",
            payload={"reason": reason, **(payload or {})},
        )

    # Internal ────────────────────────────────────────────────────────────────

    def _emit(
        self,
        event_type: EventType,
        *,
        agent_name: str | None = None,
        agent_invocation_id: str | None = None,
        llm_call_id: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        evt = LogEvent(
            run_id=self.run_id,
            event_type=event_type,
            agent_name=agent_name,
            agent_invocation_id=agent_invocation_id,
            llm_call_id=llm_call_id,
            message=message,
            payload=payload or {},
            tags=self.tags,
        )
        line = evt.model_dump_json()
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


# ── Per-agent-invocation logger ───────────────────────────────────────────────

class AgentInvocationLogger:
    """One instance per agent.run() call. Tracks LLM calls + final outcome."""

    def __init__(
        self,
        *,
        run: RunLogger,
        agent_name: str,
        input_full: dict[str, Any] | None = None,
        config_used: dict[str, Any] | None = None,
    ) -> None:
        self.run = run
        self.agent_name = agent_name
        self.invocation_id = uuid4().hex[:12]
        self._t0 = time.monotonic()
        self._llm_calls: list[LLMCallRecord] = []
        self._input_full = input_full
        self._config_used = config_used or {}

    # Public API ──────────────────────────────────────────────────────────────

    def log_llm_call(self, record: LLMCallRecord) -> str:
        """Log one HTTP call (could be retry attempt). Returns llm_call_id."""
        call_id = uuid4().hex[:12]
        self._llm_calls.append(record)
        evt_type = (
            EventType.LLM_CALL_ERROR if record.error
            else EventType.LLM_CALL_COMPLETE
        )
        self.run._emit(
            evt_type,
            agent_name=self.agent_name,
            agent_invocation_id=self.invocation_id,
            llm_call_id=call_id,
            message=(
                f"LLM call {record.model} attempt={record.attempt_number} "
                f"latency={record.latency_ms}ms cost=${record.cost_usd or 0:.4f}"
                + (f" ERROR: {record.error_type}" if record.error else "")
            ),
            payload=record.model_dump(),
        )
        return call_id

    def log_validation(
        self,
        *,
        passed: bool,
        errors: list[dict] | None = None,
        message: str | None = None,
    ) -> None:
        self.run._emit(
            EventType.VALIDATION_PASSED if passed else EventType.VALIDATION_FAILED,
            agent_name=self.agent_name,
            agent_invocation_id=self.invocation_id,
            message=message or ("Validation passed" if passed else "Validation failed"),
            payload={"errors": errors or []},
        )

    def complete(
        self,
        *,
        succeeded: bool,
        output_full: dict[str, Any] | None = None,
        output_summary: str | None = None,
        final_error: str | None = None,
    ) -> AgentInvocationRecord:
        """Mark agent done. Aggregates totals from LLM calls."""
        elapsed_ms = int((time.monotonic() - self._t0) * 1000)
        total_cost = sum((c.cost_usd or 0.0) for c in self._llm_calls)

        record = AgentInvocationRecord(
            agent_name=self.agent_name,
            config_used=self._config_used,
            input_full=self._input_full,
            output_full=output_full,
            output_summary=output_summary,
            succeeded=succeeded,
            total_llm_calls=len(self._llm_calls),
            total_cost_usd=round(total_cost, 6),
            total_latency_ms=elapsed_ms,
            final_error=final_error,
        )
        self.run._emit(
            EventType.AGENT_COMPLETE if succeeded else EventType.AGENT_ERROR,
            agent_name=self.agent_name,
            agent_invocation_id=self.invocation_id,
            message=(
                f"Agent {self.agent_name} {'succeeded' if succeeded else 'FAILED'} "
                f"in {elapsed_ms}ms / {len(self._llm_calls)} calls / ${total_cost:.4f}"
            ),
            payload=record.model_dump(),
        )
        return record
