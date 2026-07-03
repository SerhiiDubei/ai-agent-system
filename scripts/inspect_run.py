#!/usr/bin/env python
"""
Inspect a single agent run from its JSONL log.

Usage:
    python scripts/inspect_run.py <run_id>           # auto-find by id
    python scripts/inspect_run.py path/to/file.jsonl # explicit file
    python scripts/inspect_run.py --latest           # most recent run
    python scripts/inspect_run.py --list             # list runs from today

Output: human-readable timeline of events with hierarchy indentation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG_ROOT = ROOT / "logs" / "agent_runs"

# ── ANSI colors (simple, no extra deps) ───────────────────────────────────────

C = {
    "reset":    "\033[0m",
    "bold":     "\033[1m",
    "dim":      "\033[2m",
    "red":      "\033[31m",
    "green":    "\033[32m",
    "yellow":   "\033[33m",
    "blue":     "\033[34m",
    "magenta":  "\033[35m",
    "cyan":     "\033[36m",
    "gray":     "\033[90m",
}


def color(text: str, c: str) -> str:
    return f"{C[c]}{text}{C['reset']}"


# ── Discovery ─────────────────────────────────────────────────────────────────

def find_run_file(run_id_or_path: str) -> Path:
    p = Path(run_id_or_path)
    if p.exists():
        return p
    # Search by id within today's runs first, then all dates
    for day_dir in sorted(LOG_ROOT.iterdir(), reverse=True):
        if day_dir.is_dir():
            cand = day_dir / f"{run_id_or_path}.jsonl"
            if cand.exists():
                return cand
    raise FileNotFoundError(f"No run file found for: {run_id_or_path}")


def list_runs(day: str | None = None) -> list[Path]:
    target_day = day or date.today().isoformat()
    day_dir = LOG_ROOT / target_day
    if not day_dir.exists():
        return []
    return sorted(day_dir.glob("*.jsonl"))


def latest_run() -> Path | None:
    files = list_runs()
    if not files:
        # Try yesterday too
        for day_dir in sorted(LOG_ROOT.iterdir(), reverse=True):
            if day_dir.is_dir():
                files = sorted(day_dir.glob("*.jsonl"))
                if files:
                    break
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


# ── Event renderer ────────────────────────────────────────────────────────────

EVENT_ICONS = {
    "run_start":         color("▶ ", "green"),
    "run_complete":      color("■ ", "green"),
    "run_abort":         color("⚠ ", "red"),
    "agent_start":       color("  ↳ ", "cyan"),
    "agent_complete":    color("  ✓ ", "green"),
    "agent_error":       color("  ✗ ", "red"),
    "llm_call_start":    color("    → ", "blue"),
    "llm_call_complete": color("    ← ", "blue"),
    "llm_call_error":    color("    ✗ ", "red"),
    "validation_passed": color("    ✓ ", "green"),
    "validation_failed": color("    ✗ ", "red"),
    "note":              color("    · ", "gray"),
}


def render_event(evt: dict, *, full: bool) -> str:
    et = evt["event_type"]
    icon = EVENT_ICONS.get(et, "  ? ")
    ts = evt["ts"][11:23]  # HH:MM:SS.uuuuuu
    msg = evt.get("message") or ""

    line = f"{icon}{color(ts, 'dim')}  {msg}"

    if not full:
        return line

    # In full mode, dump the payload below the message
    payload = evt.get("payload") or {}
    if not payload:
        return line

    # Pretty payload display, indented
    body = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    indented = "\n".join(f"        {l}" for l in body.splitlines())
    return f"{line}\n{color(indented, 'gray')}"


def render_run(path: Path, *, full: bool) -> None:
    print(color(f"\n=== Run file: {path} ===", "bold"))

    events: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError as e:
                print(color(f"  [line {line_num}] malformed JSON: {e}", "red"))

    if not events:
        print(color("  (no events)", "yellow"))
        return

    # Quick stats
    by_type: dict[str, int] = {}
    total_cost = 0.0
    for e in events:
        by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1
        if e["event_type"] == "llm_call_complete":
            total_cost += (e.get("payload") or {}).get("cost_usd", 0) or 0

    stats = " · ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
    print(color(f"  Stats: {stats} · total_cost=${total_cost:.4f}\n", "cyan"))

    for evt in events:
        print(render_event(evt, full=full))


def render_list() -> None:
    files = list_runs()
    if not files:
        print(color("No runs today.", "yellow"))
        return

    print(color(f"\n=== {len(files)} runs today ===", "bold"))
    for f in files:
        # Peek at first line to grab label
        try:
            first = json.loads(f.open("r", encoding="utf-8").readline())
            label = (first.get("payload") or {}).get("label") or "(no label)"
        except Exception:
            label = "(read error)"
        run_id = f.stem
        print(f"  {color(run_id, 'cyan')}  {label}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("target", nargs="?", help="run_id or path to .jsonl file")
    p.add_argument("--latest", action="store_true", help="show most recent run")
    p.add_argument("--list",   action="store_true", help="list today's runs")
    p.add_argument("--full",   action="store_true", help="include full payloads")
    args = p.parse_args()

    if args.list:
        render_list()
        return 0

    if args.latest:
        f = latest_run()
        if not f:
            print(color("No runs found.", "yellow"))
            return 1
        render_run(f, full=args.full)
        return 0

    if not args.target:
        p.print_help()
        return 1

    f = find_run_file(args.target)
    render_run(f, full=args.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
