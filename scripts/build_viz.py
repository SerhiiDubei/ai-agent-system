#!/usr/bin/env python
"""Generate viz/index.html — interactive HTML dashboard of system state.

Reads the actual project structure + latest log files and renders a single
self-contained HTML file (no server needed — open file:// in browser).

Run:
    python scripts/build_viz.py
    Then open: viz/index.html

What it shows:
  - Architecture diagram (Mermaid) of all nodes + connections
  - Phase progress timeline
  - Per-node detail cards: status, files, role, score
  - Latest pipeline run summary (cost, latency, agent breakdown)
  - Per-agent character card preview
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VIZ_DIR = ROOT / "viz"
LOG_ROOT = ROOT / "logs" / "agent_runs"
PROMPTS_ROOT = ROOT / "prompts"
CONFIG_PATH = ROOT / "configs" / "agents.yml"


# ── Node registry — single source of truth for what's in the system ─────────

NODES: list[dict] = [
    # Foundation layer
    {
        "id": "F1", "name": "Config", "layer": "foundation", "status": "complete",
        "score": 85, "role": "Centralized settings via Pydantic",
        "files": ["src/ai_agent_system/config.py"],
    },
    {
        "id": "F2", "name": "Auth", "layer": "foundation", "status": "complete",
        "score": 65, "role": "Internal API key auth",
        "files": ["src/ai_agent_system/auth.py"],
    },
    {
        "id": "F3", "name": "DB Layer", "layer": "foundation", "status": "complete",
        "score": 80, "role": "SQLAlchemy + Alembic + Postgres",
        "files": ["src/ai_agent_system/db/"],
    },
    {
        "id": "F4", "name": "API Gateway", "layer": "foundation", "status": "complete",
        "score": 75, "role": "FastAPI routers per module",
        "files": ["src/ai_agent_system/api/", "src/ai_agent_system/main.py"],
    },
    {
        "id": "F5", "name": "LLM Router", "layer": "foundation", "status": "complete",
        "score": 75, "role": "OpenRouter gateway + cost sink + kill switch + tracing",
        "files": ["src/ai_agent_system/llm/"],
    },

    # Pipeline layer
    {
        "id": "N1", "name": "Snapshot", "layer": "pipeline", "status": "complete",
        "score": 80, "role": "Firecrawl page capture (HTML+screenshots+markdown)",
        "files": ["src/ai_agent_system/snapshot/"],
    },
    {
        "id": "N2", "name": "Semantic Parser", "layer": "pipeline", "status": "complete",
        "score": 70, "role": "DOM mark extraction + element classification",
        "files": ["src/ai_agent_system/semantic/"],
    },
    {
        "id": "N3", "name": "Knowledge RAG", "layer": "pipeline", "status": "complete",
        "score": 85, "role": "Chunker, embedder, retriever, reranker, watcher",
        "files": ["src/ai_agent_system/knowledge/"],
    },

    # Phase 5f — Page-Works Analyzer (NEW expert, FIRST in pipeline)
    {
        "id": "PW", "name": "Page-Works Analyzer (Preservation)", "layer": "agents",
        "status": "complete", "score": 88,
        "role": "Domain-agnostic 'preservation archaeologist' — analyzes existing LP, identifies trust anatomy + load-shares + preservation_zones + warnings_for_downstream. Runs FIRST in pipeline (Wave 0).",
        "files": [
            "agents/page_works_analyzer/AGENT.md",
            "agents/page_works_analyzer/beliefs.md",
            "agents/page_works_analyzer/workflow.md",
            "agents/page_works_analyzer/anti_patterns.md",
            "agents/page_works_analyzer/knowledge/frameworks/*.md (3)",
            "agents/page_works_analyzer/knowledge/working_page_patterns/*.md (5)",
            "agents/page_works_analyzer/golden_sets/*.json (3)",
            "src/ai_agent_system/page_works/analyzer.py",
            "src/ai_agent_system/page_works/schemas.py",
        ],
        "v2_system": True,
        "model_tier": "economy_default",
        "page_aware": True,
    },
    # Agent layer (Phase 1+2 — N4 decomposed; CI promoted to v2 system in Phase 5b)
    {
        "id": "CI", "name": "Customer Insights v2 (agent-system)", "layer": "agents",
        "status": "complete", "score": 90,
        "role": "Domain-agnostic system with conditional knowledge loading: 10 frameworks + 5 market_segments + 6 golden_sets, niche-routed at runtime. PROVEN on walk-in tubs / SaaS / debt relief.",
        "files": [
            "agents/customer_insights/AGENT.md",
            "agents/customer_insights/beliefs.md",
            "agents/customer_insights/workflow.md",
            "agents/customer_insights/knowledge/frameworks/*.md (10)",
            "agents/customer_insights/knowledge/market_segments/*.md (5)",
            "agents/customer_insights/golden_sets/*.json (6)",
            "agents/customer_insights/segment_routing.yml",
            "src/ai_agent_system/marketing/agents_v2/system_loader.py",
            "src/ai_agent_system/marketing/agents_v2/customer_insights_v2.py",
        ],
        "model_tier": "economy_default",
        "v2_system": True,
    },
    {
        "id": "VM", "name": "Voice & Message Strategist", "layer": "agents",
        "status": "complete", "score": 75,
        "role": "Value prop + hooks + headline angles by awareness stage",
        "files": [
            "src/ai_agent_system/marketing/agents/voice_message.py",
            "prompts/voice_message/v1.md",
        ],
        "model_tier": "economy_default",
        "page_aware": True,
    },
    {
        "id": "MP", "name": "Media Planner", "layer": "agents",
        "status": "complete", "score": 75,
        "role": "Channel profile + temperature + creative grammar",
        "files": [
            "src/ai_agent_system/marketing/agents/media_planner.py",
            "prompts/media_planner/v1.md",
        ],
    },
    {
        "id": "AS", "name": "Audience Strategist", "layer": "agents",
        "status": "complete", "score": 75,
        "role": "Lookalike seeds + exclusion signals + audience profile",
        "files": [
            "src/ai_agent_system/marketing/agents/audience_strategist.py",
            "prompts/audience_strategist/v1.md",
        ],
    },
    {
        "id": "CA", "name": "Conversion Architect (CRO)", "layer": "agents",
        "status": "complete", "score": 80,
        "role": "User flow + ICE-scored test priorities + friction inventory",
        "files": [
            "src/ai_agent_system/marketing/agents/conversion_architect.py",
            "prompts/conversion_architect/v1.md",
        ],
        "page_aware": True,
    },
    {
        "id": "ASM", "name": "Assembler", "layer": "agents",
        "status": "complete", "score": 85,
        "role": "Combines 5 sub-outputs + smart auto-correction for cross-field",
        "files": ["src/ai_agent_system/marketing/assembler.py"],
    },

    # Phase 3 — Hypothesis Generator
    {
        "id": "HG", "name": "Hypothesis Generator", "layer": "agents",
        "status": "complete", "score": 75,
        "role": "Synthesizes 3-6 production-ready A/B test plans (Sonnet-4.6)",
        "files": [
            "src/ai_agent_system/hypotheses/generator.py",
            "prompts/hypothesis_generator/v1.md",
        ],
        "model_tier": "premium_override",
        "page_aware": True,
    },

    # Observability
    {
        "id": "O0", "name": "Agent Logger", "layer": "observability",
        "status": "complete", "score": 85,
        "role": "JSONL hierarchy: Run → Agent → LLM Call",
        "files": ["src/ai_agent_system/observability/"],
    },
    {
        "id": "O1", "name": "Inspect CLI", "layer": "observability",
        "status": "complete", "score": 80,
        "role": "Color-coded timeline reader for any run.jsonl",
        "files": ["scripts/inspect_run.py"],
    },
    {
        "id": "O2", "name": "Benchmark Scorer", "layer": "observability",
        "status": "partial", "score": 65,
        "role": "Heuristic scoring per operation (one-shot, not continuous)",
        "files": ["src/ai_agent_system/benchmark/"],
    },

    # Phase 4 — Hypothesis Judge
    {
        "id": "HJ", "name": "Hypothesis Judge", "layer": "agents",
        "status": "complete", "score": 80,
        "role": "Ship/iterate/kill verdicts + per-dimension scoring (gpt-4o-mini, ~13s)",
        "files": [
            "src/ai_agent_system/hypotheses/judge.py",
            "src/ai_agent_system/hypotheses/judge_schemas.py",
            "prompts/hypothesis_judge/v1.md",
        ],
        "model_tier": "economy_default",
    },

    # Phase 5h — Product Director (final synthesizer)
    {
        "id": "PD", "name": "Product Director (Senior CRO Program Director)", "layer": "agents",
        "status": "complete", "score": 90,
        "role": "Final decision synthesizer. Reads ALL expert outputs + operating_constraints + Page-Works preservation map → produces ranked ship/iterate/kill decision package with strategic_recommendation. Runs LAST (Wave 5).",
        "files": [
            "agents/product_director/AGENT.md",
            "agents/product_director/beliefs.md",
            "agents/product_director/workflow.md",
            "agents/product_director/anti_patterns.md",
            "agents/product_director/knowledge/frameworks/test_program_management.md",
            "agents/product_director/knowledge/decision_patterns/common_archetypes.md",
            "agents/product_director/golden_sets/decision_low_traffic_high_baseline.json",
            "src/ai_agent_system/product_director/director.py",
            "src/ai_agent_system/product_director/schemas.py",
        ],
        "v2_system": True,
        "model_tier": "economy_default",
    },

    # Not yet built
    {
        "id": "TP", "name": "Test Platform Integration", "layer": "platform",
        "status": "todo", "score": 0,
        "role": "Push test plans to VWO/Convert/Optimizely",
        "files": [],
    },
    {
        "id": "RT", "name": "Results Tracker", "layer": "platform",
        "status": "todo", "score": 0,
        "role": "Pull test results, compute lift, post-test reads",
        "files": [],
    },
]


PHASES = [
    {"id": 0, "name": "Observability infra", "status": "complete"},
    {"id": 1, "name": "Drafter decomposition (5 agents)", "status": "complete"},
    {"id": 2, "name": "Snapshot → Marketing connection", "status": "complete"},
    {"id": 3, "name": "Hypothesis Generator", "status": "complete"},
    {"id": 4, "name": "Hypothesis Judge", "status": "complete"},
    {"id": "5b", "name": "CI v2 agent-as-system", "status": "complete"},
    {"id": "5d", "name": "Operating constraints + test depth + MDE", "status": "complete"},
    {"id": "5f", "name": "Page-Works Analyzer (preservation)", "status": "complete"},
    {"id": "5g", "name": "Persistent expert state", "status": "complete"},
    {"id": "5h", "name": "Product Director (synthesizer)", "status": "complete"},
    {"id": "5c", "name": "Full agent-as-system rollout", "status": "pending"},
    {"id": "5j+", "name": "Daily auto-enrichment (vision)", "status": "pending"},
    {"id": 6, "name": "Test Platform Integration", "status": "pending"},
    {"id": 7, "name": "Results Tracker + Dashboard", "status": "pending"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_latest_run() -> dict | None:
    """Read the latest agent_runs/<date>/<run_id>.jsonl and summarize."""
    if not LOG_ROOT.exists():
        return None
    days = sorted([p for p in LOG_ROOT.iterdir() if p.is_dir()], reverse=True)
    for day in days:
        files = sorted(day.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files:
            try:
                events = []
                with f.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
                if not events:
                    continue
                first = events[0]
                # Aggregate
                total_cost = 0.0
                total_calls = 0
                agents_seen: dict[str, dict] = {}
                for e in events:
                    if e["event_type"] == "llm_call_complete":
                        total_calls += 1
                        cost = (e.get("payload") or {}).get("cost_usd", 0) or 0
                        total_cost += cost
                    if e["event_type"] == "agent_complete":
                        name = e.get("agent_name") or "?"
                        p = e.get("payload") or {}
                        agents_seen[name] = {
                            "succeeded": p.get("succeeded", False),
                            "latency_ms": p.get("total_latency_ms", 0),
                            "cost_usd": p.get("total_cost_usd", 0),
                            "summary": p.get("output_summary", ""),
                        }
                return {
                    "run_id": first.get("run_id", "?"),
                    "label": (first.get("payload") or {}).get("label", "?"),
                    "ts": first.get("ts", "?"),
                    "total_cost": round(total_cost, 4),
                    "total_calls": total_calls,
                    "agents": agents_seen,
                    "file": str(f.relative_to(ROOT)),
                }
            except Exception:
                continue
    return None


def char_card_summary(agent_name: str) -> dict | None:
    """Read first paragraph of WHO I AM from prompts/<agent>/v1.md."""
    path = PROMPTS_ROOT / agent_name / "v1.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # Word count
    words = len(text.split())
    # Find WHO I AM block
    who_block = ""
    in_who = False
    for line in text.splitlines():
        if line.startswith("## WHO I AM"):
            in_who = True
            continue
        if in_who:
            if line.startswith("## "):
                break
            who_block += line + "\n"
    return {
        "word_count": words,
        "who_excerpt": who_block.strip()[:500],
    }


# ── HTML rendering ────────────────────────────────────────────────────────────

STATUS_COLORS = {
    "complete": "#10b981",
    "partial":  "#f59e0b",
    "todo":     "#6b7280",
    "broken":   "#ef4444",
    "pending":  "#6b7280",
}

LAYER_LABELS = {
    "foundation":    "Foundation",
    "pipeline":      "Pipeline",
    "agents":        "Agents",
    "observability": "Observability",
    "platform":      "Platform",
}


def render_mermaid() -> str:
    """Build Mermaid graph definition for the architecture diagram."""
    lines = ["graph TB"]
    lines.append("    BRIEF[/&quot;Brief + Constraints + URL&quot;/]:::input")
    lines.append("    BRIEF --> N1[N1 Snapshot]:::pipeline")
    lines.append("    BRIEF --> N3[N3 Knowledge RAG]:::pipeline")
    lines.append("    N1 --> N2[N2 Semantic Parser]:::pipeline")
    lines.append("    N1 --> PC{{Page Context}}:::data")
    lines.append("    N2 --> PC")
    lines.append("")
    lines.append("    PC --> PW[PW Page-Works Analyzer]:::agent_v2")
    lines.append("    BRIEF --> PW")
    lines.append("    PW --> PRESV{{Preservation Map<br/>+ Warnings}}:::data")
    lines.append("")
    lines.append("    subgraph Drafter [N4 Decomposed Drafter — 5 agents]")
    lines.append("      direction TB")
    lines.append("      CI[Customer Insights v2]:::agent_v2")
    lines.append("      MP[Media Planner]:::agent_complete")
    lines.append("      CA[Conversion Architect]:::agent_page")
    lines.append("      VM[Voice and Message]:::agent_page")
    lines.append("      AS[Audience Strategist]:::agent_complete")
    lines.append("      ASM([Assembler]):::agent_complete")
    lines.append("      CI --> VM")
    lines.append("      CI --> AS")
    lines.append("      MP --> AS")
    lines.append("      CI --> ASM")
    lines.append("      VM --> ASM")
    lines.append("      MP --> ASM")
    lines.append("      AS --> ASM")
    lines.append("      CA --> ASM")
    lines.append("    end")
    lines.append("")
    lines.append("    BRIEF --> CI")
    lines.append("    BRIEF --> MP")
    lines.append("    BRIEF --> CA")
    lines.append("    N3 -.RAG chunks.-> CI")
    lines.append("    PC -.page data.-> CA")
    lines.append("    PC -.page data.-> VM")
    lines.append("    PRESV -.warnings.-> CI")
    lines.append("    PRESV -.warnings.-> CA")
    lines.append("    PRESV -.warnings.-> VM")
    lines.append("")
    lines.append("    ASM --> HG[N6 Hypothesis Generator]:::agent_premium")
    lines.append("    PC -.page data.-> HG")
    lines.append("    PRESV -.warnings.-> HG")
    lines.append("    HG --> HJ[N7 Hypothesis Judge]:::agent_complete")
    lines.append("    HJ --> PD[PD Product Director]:::agent_v2")
    lines.append("    PRESV -.preserve.-> PD")
    lines.append("    BRIEF -.constraints.-> PD")
    lines.append("    PD --> DEC{{Ship/Iterate/Kill<br/>Decision Package}}:::data")
    lines.append("    DEC --> TP[N8 Test Platform]:::todo")
    lines.append("    TP --> RT[N9 Results Tracker]:::todo")
    lines.append("")
    lines.append("    classDef input fill:#1e293b,stroke:#94a3b8,color:#fff")
    lines.append("    classDef pipeline fill:#065f46,stroke:#10b981,color:#fff")
    lines.append("    classDef data fill:#1e3a8a,stroke:#3b82f6,color:#fff")
    lines.append("    classDef agent_complete fill:#10b981,stroke:#059669,color:#fff")
    lines.append("    classDef agent_page fill:#0891b2,stroke:#0e7490,color:#fff")
    lines.append("    classDef agent_premium fill:#7c3aed,stroke:#5b21b6,color:#fff")
    lines.append("    classDef agent_v2 fill:#db2777,stroke:#9d174d,color:#fff,stroke-width:2px")
    lines.append("    classDef todo fill:#374151,stroke:#6b7280,color:#9ca3af,stroke-dasharray: 5 5")
    return "\n".join(lines)


def render_node_card(node: dict) -> str:
    color = STATUS_COLORS[node["status"]]
    files_html = "".join(
        f"<li><code>{escape(f)}</code></li>" for f in node.get("files", [])
    ) or "<li><em>not built</em></li>"

    badges = []
    if node.get("page_aware"):
        badges.append('<span class="badge badge-page">page-aware</span>')
    if node.get("model_tier") == "premium_override":
        badges.append('<span class="badge badge-premium">sonnet-4.6 forced</span>')
    if node.get("model_tier") == "economy_default":
        badges.append('<span class="badge badge-economy">tier-controlled</span>')

    char_card = ""
    if node["layer"] == "agents" and node["status"] == "complete":
        # Map node id to agent_name (for character card lookup)
        id_to_name = {
            "CI": "customer_insights",
            "VM": "voice_message",
            "MP": "media_planner",
            "AS": "audience_strategist",
            "CA": "conversion_architect",
            "HG": "hypothesis_generator",
            "HJ": "hypothesis_judge",
            "PW": "page_works_analyzer",
            "PD": "product_director",
        }
        agent_name = id_to_name.get(node["id"])
        if agent_name:
            cc = char_card_summary(agent_name)
            if cc:
                char_card = (
                    f'<div class="char-card-info">'
                    f'<strong>Character card:</strong> '
                    f'<code>prompts/{agent_name}/v1.md</code> '
                    f'<span class="word-count">{cc["word_count"]} words</span>'
                    f'<details><summary>WHO I AM excerpt</summary>'
                    f'<p class="who-excerpt">{escape(cc["who_excerpt"])}</p>'
                    f'</details>'
                    f'</div>'
                )

    return f"""
    <div class="node-card" data-status="{node['status']}" data-layer="{node['layer']}">
      <div class="node-header">
        <span class="status-dot" style="background:{color}"></span>
        <span class="node-id">{escape(node['id'])}</span>
        <h3>{escape(node['name'])}</h3>
        <span class="score" title="Quality score 0-100">{node['score']}</span>
      </div>
      <p class="role">{escape(node['role'])}</p>
      <div class="badges">{''.join(badges)}</div>
      <ul class="files">{files_html}</ul>
      {char_card}
    </div>
    """


def render_phase_timeline() -> str:
    items = []
    for p in PHASES:
        cls = "phase-done" if p["status"] == "complete" else "phase-pending"
        marker = "✓" if p["status"] == "complete" else "○"
        items.append(
            f'<li class="{cls}"><span class="marker">{marker}</span>'
            f'<span class="phase-num">Phase {p["id"]}</span>'
            f'<span class="phase-name">{escape(p["name"])}</span></li>'
        )
    return f'<ul class="phase-timeline">{"".join(items)}</ul>'


def render_latest_run(run: dict | None) -> str:
    if not run:
        return '<p class="empty">No runs found in logs/agent_runs/</p>'

    agent_rows = []
    for name, info in run["agents"].items():
        ok = "✓" if info["succeeded"] else "✗"
        ok_class = "ok" if info["succeeded"] else "fail"
        agent_rows.append(
            f'<tr class="{ok_class}">'
            f'<td>{ok}</td>'
            f'<td><code>{escape(name)}</code></td>'
            f'<td>{info["latency_ms"]:,} ms</td>'
            f'<td>${info["cost_usd"]:.4f}</td>'
            f'<td>{escape(info["summary"][:100])}</td>'
            f'</tr>'
        )

    return f"""
    <div class="run-summary">
      <p><strong>Run ID:</strong> <code>{escape(run["run_id"])}</code></p>
      <p><strong>Label:</strong> {escape(run["label"] or "-")}</p>
      <p><strong>Started:</strong> {escape(run["ts"])}</p>
      <p><strong>Total cost:</strong> ${run["total_cost"]:.4f}</p>
      <p><strong>LLM calls:</strong> {run["total_calls"]}</p>
      <p><strong>Log file:</strong> <code>{escape(run["file"])}</code></p>
      <p><strong>Inspect command:</strong>
        <code>python scripts/inspect_run.py {escape(run["run_id"])} --full</code>
      </p>
      <h3>Agents in this run</h3>
      <table class="agents-table">
        <thead><tr><th></th><th>Agent</th><th>Latency</th><th>Cost</th><th>Output</th></tr></thead>
        <tbody>{"".join(agent_rows)}</tbody>
      </table>
    </div>
    """


def render_html() -> str:
    latest = load_latest_run()
    mermaid = render_mermaid()

    # Group nodes by layer
    layers_html = []
    for layer_id, layer_label in LAYER_LABELS.items():
        nodes_in_layer = [n for n in NODES if n["layer"] == layer_id]
        if not nodes_in_layer:
            continue
        cards = "".join(render_node_card(n) for n in nodes_in_layer)
        layers_html.append(
            f'<section class="layer-section">'
            f'<h2 class="layer-title">{escape(layer_label)}</h2>'
            f'<div class="cards-grid">{cards}</div>'
            f'</section>'
        )

    # Aggregate stats
    total = len(NODES)
    complete = sum(1 for n in NODES if n["status"] == "complete")
    partial = sum(1 for n in NODES if n["status"] == "partial")
    todo = sum(1 for n in NODES if n["status"] == "todo")
    avg_score = round(sum(n["score"] for n in NODES if n["status"] != "todo") /
                      max(1, sum(1 for n in NODES if n["status"] != "todo")))

    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI Agent System — Architecture Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f172a; color: #e2e8f0;
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    padding: 32px;
    max-width: 1600px;
    margin: 0 auto;
  }}
  h1 {{ font-size: 28px; margin-bottom: 8px; color: #f1f5f9; }}
  h2 {{ font-size: 20px; margin: 32px 0 12px; color: #f8fafc; }}
  h3 {{ font-size: 15px; color: #f1f5f9; }}
  code {{
    background: #1e293b; padding: 2px 6px; border-radius: 3px;
    font-family: "SF Mono", Consolas, Monaco, monospace; font-size: 12px;
    color: #93c5fd;
  }}

  .header {{
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px;
  }}
  .header .meta {{ color: #94a3b8; font-size: 12px; }}

  .stats {{
    display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;
    margin: 24px 0;
  }}
  .stat {{
    background: #1e293b; border-radius: 8px; padding: 16px;
    border: 1px solid #334155;
  }}
  .stat .num {{ font-size: 28px; font-weight: bold; color: #f1f5f9; }}
  .stat .lbl {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; }}
  .stat.ok .num   {{ color: #10b981; }}
  .stat.warn .num {{ color: #f59e0b; }}
  .stat.todo .num {{ color: #6b7280; }}

  .mermaid-wrap {{
    background: #1e293b; border-radius: 8px; padding: 24px; margin: 24px 0;
    overflow-x: auto; border: 1px solid #334155;
  }}
  .mermaid {{ display: flex; justify-content: center; }}

  .phase-timeline {{
    list-style: none; display: flex; gap: 8px; flex-wrap: wrap;
    background: #1e293b; padding: 16px; border-radius: 8px;
    border: 1px solid #334155;
  }}
  .phase-timeline li {{
    display: flex; align-items: center; gap: 6px;
    padding: 8px 12px; background: #0f172a; border-radius: 6px;
    border: 1px solid #334155;
  }}
  .phase-done .marker {{ color: #10b981; font-weight: bold; }}
  .phase-done .phase-name {{ color: #e2e8f0; }}
  .phase-pending .marker {{ color: #6b7280; }}
  .phase-pending .phase-name {{ color: #94a3b8; }}
  .phase-num {{ font-size: 11px; color: #64748b; }}

  .layer-title {{ color: #93c5fd; }}
  .cards-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 12px;
  }}
  .node-card {{
    background: #1e293b; border-radius: 8px; padding: 16px;
    border: 1px solid #334155;
    transition: transform 0.1s, border-color 0.1s;
  }}
  .node-card:hover {{ transform: translateY(-2px); border-color: #475569; }}
  .node-card[data-status="todo"] {{ opacity: 0.6; border-style: dashed; }}

  .node-header {{
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
  }}
  .status-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .node-id {{
    font-family: monospace; background: #0f172a; padding: 2px 6px;
    border-radius: 3px; font-size: 11px; color: #94a3b8;
  }}
  .node-header h3 {{ flex: 1; margin: 0; }}
  .score {{
    background: #0f172a; padding: 2px 8px; border-radius: 12px;
    font-size: 11px; color: #cbd5e1; font-weight: bold;
  }}

  .role {{ color: #cbd5e1; font-size: 13px; margin-bottom: 8px; }}
  .badges {{ margin-bottom: 8px; }}
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 10px; text-transform: uppercase; font-weight: bold;
    margin-right: 4px;
  }}
  .badge-page {{ background: #0e7490; color: #fff; }}
  .badge-premium {{ background: #7c3aed; color: #fff; }}
  .badge-economy {{ background: #475569; color: #cbd5e1; }}

  .files {{ list-style: none; font-size: 11px; color: #94a3b8; }}
  .files li {{ margin: 2px 0; }}
  .files code {{ font-size: 11px; }}

  .char-card-info {{
    margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155;
    font-size: 12px;
  }}
  .word-count {{ color: #64748b; margin-left: 8px; font-size: 11px; }}
  .who-excerpt {{
    color: #cbd5e1; margin-top: 6px; padding: 8px;
    background: #0f172a; border-radius: 4px; font-style: italic;
    font-size: 11px; line-height: 1.4;
  }}
  details summary {{
    cursor: pointer; color: #93c5fd; font-size: 11px; margin-top: 4px;
  }}

  .run-summary {{
    background: #1e293b; padding: 16px; border-radius: 8px;
    border: 1px solid #334155;
  }}
  .run-summary p {{ margin: 4px 0; font-size: 13px; }}
  .agents-table {{
    width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 12px;
  }}
  .agents-table th, .agents-table td {{
    padding: 6px 8px; text-align: left; border-bottom: 1px solid #334155;
  }}
  .agents-table th {{ color: #94a3b8; font-weight: normal; font-size: 11px; }}
  .agents-table tr.fail {{ color: #fca5a5; }}
  .agents-table tr.ok td:first-child {{ color: #10b981; }}

  .empty {{ color: #64748b; font-style: italic; padding: 24px; text-align: center; }}

  details > summary {{ list-style: none; }}
  details > summary::-webkit-details-marker {{ display: none; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>AI Agent System — Architecture Dashboard</h1>
    <div class="meta">A/B test hypothesis generator for paid-traffic landing pages</div>
  </div>
  <div class="meta">Generated {now}</div>
</div>

<div class="stats">
  <div class="stat ok"><div class="num">{complete}</div><div class="lbl">Complete</div></div>
  <div class="stat warn"><div class="num">{partial}</div><div class="lbl">Partial</div></div>
  <div class="stat todo"><div class="num">{todo}</div><div class="lbl">Not built</div></div>
  <div class="stat"><div class="num">{avg_score}</div><div class="lbl">Avg Score</div></div>
  <div class="stat"><div class="num">{total}</div><div class="lbl">Total Nodes</div></div>
</div>

<h2>Phase Progress</h2>
{render_phase_timeline()}

<h2>System Architecture (data flow)</h2>
<div class="mermaid-wrap">
  <pre class="mermaid">
{mermaid}
  </pre>
</div>

<h2>Latest Pipeline Run</h2>
{render_latest_run(latest)}

{''.join(layers_html)}

<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {{
      darkMode: true,
      background: '#1e293b',
      primaryColor: '#0891b2',
      primaryTextColor: '#fff',
      primaryBorderColor: '#0e7490',
      lineColor: '#94a3b8',
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif'
    }}
  }});
</script>

</body>
</html>
"""


def main() -> int:
    VIZ_DIR.mkdir(exist_ok=True)
    html = render_html()
    out = VIZ_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"✓ Written {out}")
    print(f"  Open: file:///{out.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
