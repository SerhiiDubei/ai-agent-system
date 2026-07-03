"""Loader for agent-as-system — assembles knowledge files into a runtime prompt.

The loader is responsible for:
  1. Reading the agent's static files (AGENT.md, beliefs.md, workflow.md,
     persona_filling_guide.md, anti_patterns.md, voc_mining.md)
  2. Reading the agent's segment_routing.yml
  3. Selecting the right market_segment + frameworks + golden_sets based on
     the brief's niche / keyword signals
  4. Loading the selected knowledge files
  5. Assembling all of the above into a single rich system_prompt string

The runtime then passes this assembled system_prompt + a small user_prompt
(with the brief itself) to the LLM. This is fundamentally different from
v1 (single hardcoded character_card.md) — it's modular, niche-adaptive,
and trivially editable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

AGENTS_ROOT = Path(__file__).resolve().parents[4] / "agents"


# ── Routing decision dataclass ────────────────────────────────────────────────

@dataclass
class RoutingDecision:
    """What knowledge files were selected for this brief."""
    matched_via: str                    # "niche_exact" | "keyword" | "catch_all"
    matched_token: str                  # the niche key or keyword that matched
    segment: str | None                 # market_segments/<segment>.md (or None)
    frameworks: list[str] = field(default_factory=list)
    golden_sets: list[str] = field(default_factory=list)


# ── Loaded agent system dataclass ─────────────────────────────────────────────

@dataclass
class AgentSystem:
    """Everything assembled for one agent run on one brief."""
    agent_name: str
    routing: RoutingDecision
    system_prompt: str                  # the assembled prompt to pass to LLM
    files_loaded: list[str]             # paths of loaded files (for logging)


# ── Routing logic ─────────────────────────────────────────────────────────────

def select_routing(
    *,
    agent_name: str,
    niche: str | None,
    brief_text: str,
) -> RoutingDecision:
    """Pick segment + frameworks + golden_sets for this brief.

    Order:
      1. Exact niche match in segment_routing.yml.niches
      2. Keyword match against brief_text or niche string
      3. Catch-all
    Default frameworks always added.
    """
    routing_path = AGENTS_ROOT / agent_name / "segment_routing.yml"
    routing_cfg = yaml.safe_load(routing_path.read_text(encoding="utf-8"))

    niche_lower = (niche or "").lower().strip()
    text_lower = (brief_text or "").lower()
    default_frameworks = list(routing_cfg.get("default_frameworks", []))

    # 1. Exact niche match
    niches_table = routing_cfg.get("niches", {})
    if niche_lower in niches_table:
        entry = niches_table[niche_lower]
        return RoutingDecision(
            matched_via="niche_exact",
            matched_token=niche_lower,
            segment=entry.get("segment"),
            frameworks=default_frameworks + list(entry.get("frameworks_extra", [])),
            golden_sets=list(entry.get("golden_sets", [])),
        )

    # 2. Keyword match
    keyword_signals = routing_cfg.get("keyword_signals", {})
    for segment_name, kw_list in keyword_signals.items():
        for kw in kw_list:
            if kw.lower() in text_lower or kw.lower() in niche_lower:
                # Pick the first niche under this segment as the entry seed,
                # OR fall back to whatever the segment-level config gives us
                seed_entry = next(
                    (e for k, e in niches_table.items() if e.get("segment") == segment_name),
                    {},
                )
                return RoutingDecision(
                    matched_via="keyword",
                    matched_token=f"{segment_name}:{kw}",
                    segment=segment_name,
                    frameworks=default_frameworks + list(seed_entry.get("frameworks_extra", [])),
                    golden_sets=list(seed_entry.get("golden_sets", [])),
                )

    # 3. Catch-all
    catch = routing_cfg.get("catch_all", {})
    return RoutingDecision(
        matched_via="catch_all",
        matched_token="(no match)",
        segment=catch.get("segment"),
        frameworks=default_frameworks + list(catch.get("frameworks_extra", [])),
        golden_sets=list(catch.get("golden_sets", [])),
    )


# ── File reading helpers ──────────────────────────────────────────────────────

def _read_file(path: Path) -> str:
    if not path.exists():
        log.warning("missing knowledge file: %s", path)
        return f"[FILE NOT FOUND: {path.name}]"
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("failed to read JSON %s: %s", path, e)
        return None


# ── Main loader ───────────────────────────────────────────────────────────────

def load_agent_system(
    *,
    agent_name: str,
    niche: str | None,
    brief_text: str,
) -> AgentSystem:
    """Assemble the full agent system prompt for this brief.

    Returns an AgentSystem with:
      - routing decision (which segment + frameworks + goldens were chosen)
      - assembled system_prompt (multi-section markdown)
      - files_loaded (audit trail for the logger)
    """
    agent_dir = AGENTS_ROOT / agent_name
    if not agent_dir.exists():
        raise FileNotFoundError(f"Agent system not found: {agent_dir}")

    routing = select_routing(
        agent_name=agent_name, niche=niche, brief_text=brief_text,
    )

    files_loaded: list[str] = []
    sections: list[str] = []

    # ── ALWAYS-LOADED CORE FILES ─────────────────────────────────────────────
    # We auto-discover which optional files exist to support different agent
    # types (CI has persona_filling_guide; Page-Works has output_schema; etc.)
    core_candidates = [
        ("AGENT.md",                     "AGENT IDENTITY"),
        ("beliefs.md",                   "WHAT I BELIEVE"),
        ("workflow.md",                  "MY WORKFLOW"),
        ("knowledge/voc_mining.md",      "VOICE-OF-CUSTOMER MINING PROTOCOL"),
        ("persona_filling_guide.md",     "OUTPUT FILLING GUIDE"),
        ("output_schema.md",             "OUTPUT SCHEMA REFERENCE"),
        ("anti_patterns.md",             "ANTI-PATTERNS I REFUSE"),
    ]
    for rel_path, header in core_candidates:
        path = agent_dir / rel_path
        if path.exists():
            sections.append(f"# === {header} ===\n# (file: {rel_path})\n\n{_read_file(path)}")
            files_loaded.append(str(rel_path))

    # ── CONDITIONAL: market segment / working page patterns ─────────────────
    # Different agents organize their segment knowledge differently:
    #   - customer_insights uses knowledge/market_segments/<seg>.md
    #   - page_works_analyzer uses knowledge/working_page_patterns/<seg>.md
    # We try both — whichever exists wins.
    if routing.segment:
        candidates = [
            ("knowledge/market_segments",      "MARKET SEGMENT"),
            ("knowledge/working_page_patterns", "WORKING PAGE PATTERN"),
        ]
        for sub_dir, header_label in candidates:
            seg_path = agent_dir / sub_dir / f"{routing.segment}.md"
            if seg_path.exists():
                sections.append(
                    f"# === {header_label} (selected: {routing.segment}) ===\n"
                    f"# (file: {sub_dir}/{routing.segment}.md)\n"
                    f"# Routing: matched_via={routing.matched_via} token={routing.matched_token!r}\n\n"
                    f"{_read_file(seg_path)}"
                )
                files_loaded.append(f"{sub_dir}/{routing.segment}.md")
                break

    # ── CONDITIONAL: frameworks (deduplicated) ───────────────────────────────
    seen_frameworks: set[str] = set()
    for fw in routing.frameworks:
        if fw in seen_frameworks:
            continue
        seen_frameworks.add(fw)
        fw_path = agent_dir / "knowledge" / "frameworks" / f"{fw}.md"
        sections.append(
            f"# === FRAMEWORK: {fw} ===\n"
            f"# (file: knowledge/frameworks/{fw}.md)\n\n"
            f"{_read_file(fw_path)}"
        )
        files_loaded.append(f"knowledge/frameworks/{fw}.md")

    # ── CONDITIONAL: golden_sets (few-shot examples) ─────────────────────────
    if routing.golden_sets:
        sections.append(
            "# === GOLDEN SET EXAMPLES (few-shot reference) ===\n"
            "# These are real persona examples from production marketing teams.\n"
            "# Use them as quality bar and structural reference, NOT as templates\n"
            "# to copy. Adapt the style and depth to YOUR brief's niche.\n"
        )
        for gs_name in routing.golden_sets:
            gs_path = agent_dir / "golden_sets" / f"{gs_name}.json"
            data = _read_json(gs_path)
            if data is None:
                sections.append(f"  [missing golden set: {gs_name}]")
                continue
            # Render readable JSON snippet
            sections.append(
                f"\n## Golden set: {data.get('_meta', {}).get('title', gs_name)}\n"
                f"Industry: {data.get('_meta', {}).get('industry', '?')}\n"
                f"Why this is strong: {data.get('_meta', {}).get('why_strong', '')}\n\n"
                f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
            )
            files_loaded.append(f"golden_sets/{gs_name}.json")

    # ── Final assembled prompt ───────────────────────────────────────────────
    system_prompt = "\n\n---\n\n".join(sections)

    return AgentSystem(
        agent_name=agent_name,
        routing=routing,
        system_prompt=system_prompt,
        files_loaded=files_loaded,
    )
