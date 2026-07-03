"""Pydantic models for log events.

A LogEvent is the atomic unit written to disk (one JSONL line).
The structure deliberately mirrors the 3-level hierarchy:

    Run → Agent Invocation → LLM Call

Each LogEvent carries identifiers for all 3 levels so downstream tools
can group, filter, and reconstruct full traces from any starting point.

Why JSONL (not JSON or DB)?
  - Append-only: crash-safe, no re-write of file
  - Tail-able: `tail -f run.jsonl | jq` for live inspection
  - Greppable: any field can be filtered with jq/ripgrep
  - Cheap: no schema evolution headache
"""

from __future__ import annotations

from datetime import datetime, UTC
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    """ISO-8601 UTC timestamp with microsecond precision."""
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _uuid7_like() -> str:
    """Short readable ID. Real uuid4 hex, first 12 chars."""
    return uuid4().hex[:12]


# ── Event taxonomy ────────────────────────────────────────────────────────────
# These are the only event types the system emits. Adding a new one means
# updating the inspect_run.py renderer too.

class EventType(str, Enum):
    # Run lifecycle
    RUN_START = "run_start"
    RUN_COMPLETE = "run_complete"
    RUN_ABORT = "run_abort"

    # Agent invocation lifecycle
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"

    # LLM-call lifecycle (one per attempt — retries emit multiple)
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_COMPLETE = "llm_call_complete"
    LLM_CALL_ERROR = "llm_call_error"

    # Validation
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"

    # Free-form note (debug, intermediate state, manual annotation)
    NOTE = "note"


# ── LLM call record ──────────────────────────────────────────────────────────
# Snapshot of one specific HTTP call to a model provider. We capture BOTH
# the prompt (so we can replay) AND the response (so we can inspect).

class LLMCallRecord(BaseModel):
    """Everything needed to reproduce / debug one LLM call."""

    model: str = Field(..., description="OpenRouter model id, e.g. anthropic/claude-sonnet-4.6")
    temperature: float | None = None
    max_tokens: int | None = None

    # Inputs (what we sent)
    system_prompt: str | None = None
    user_prompt: str | None = None
    messages: list[dict[str, Any]] | None = Field(
        None, description="Full messages array if more complex than system+user"
    )

    # Outputs (what came back)
    raw_response: str | None = Field(None, description="Raw model text/JSON before parsing")

    # Counters
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None

    # Error (if call failed)
    error: str | None = None
    error_type: str | None = None  # e.g. "BadRequestError", "TimeoutError"

    attempt_number: int = 1


# ── Agent invocation record ──────────────────────────────────────────────────

class AgentInvocationRecord(BaseModel):
    """Per-agent summary: which agent, what input, what output, how many LLM calls."""

    agent_name: str = Field(..., description="e.g. customer_insights, voice_message")
    config_used: dict[str, Any] = Field(default_factory=dict, description="The agent config from YAML")

    # Input that triggered the invocation
    input_summary: str | None = Field(None, description="Short string summary of input")
    input_full: dict[str, Any] | None = Field(None, description="Full input payload")

    # Output (after retries)
    output_summary: str | None = None
    output_full: dict[str, Any] | None = None

    # Outcome
    succeeded: bool = False
    total_llm_calls: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0

    # Why it failed (if it did)
    final_error: str | None = None


# ── Top-level log event (one JSONL line on disk) ─────────────────────────────

class LogEvent(BaseModel):
    """One line in <run_id>.jsonl. Has identifiers for all 3 hierarchy levels."""

    # Hierarchy IDs
    run_id: str = Field(..., description="Top-level request UUID")
    agent_invocation_id: str | None = Field(
        None, description="Set when event happens during an agent run"
    )
    llm_call_id: str | None = Field(
        None, description="Set for events tied to a specific HTTP call"
    )

    # Event metadata
    event_id: str = Field(default_factory=_uuid7_like)
    event_type: EventType
    ts: str = Field(default_factory=_utcnow_iso, description="ISO UTC")

    # Optional context
    agent_name: str | None = None
    message: str | None = Field(None, description="Human-readable one-liner")

    # Payload — varies by event_type. Schema documented per-type in agent_logger.py
    payload: dict[str, Any] = Field(default_factory=dict)

    # Tags for filtering ("test_run", "production", "debug", custom user tags)
    tags: list[str] = Field(default_factory=list)
