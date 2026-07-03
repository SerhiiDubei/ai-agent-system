# Agents That Live Their Own Lives — Vision Document

> User insight (paraphrased from Phase 5 design conversation):
> "Eventually agents need to be carved out completely. They live their own lives.
> Every day they go look for new info and self-enrich, accumulating knowledge.
> They are experts in CERTAIN areas — meaning they have a few tags that hang
> together well — not mono-functional, not all-functional."

This document captures the longer-term vision for how the agent system should
evolve beyond Phase 5's static knowledge files toward truly autonomous,
self-enriching expert agents.

---

## What we have today (Phase 5)

✓ Each agent is a SYSTEM (folder of files), not a single prompt
✓ Knowledge files are organized by frameworks + market_segments + golden_sets
✓ Routing selects relevant knowledge per brief
✓ Persistent state per (agent, client) accumulates across runs
✓ Specialization tags declared in AGENT.md

This is the foundation. The agents are "specialists with a folder of references."

## What the user envisions next

### 1. Autonomous knowledge enrichment (daily)

Each agent runs a daily background job that:
- Searches the web / RSS / arxiv / industry blogs for new info in its specialization tags
- Filters for HIGH-SIGNAL content (avoiding noise)
- Drafts a candidate knowledge update (new framework? new market_segment example? new golden_set?)
- Submits the candidate for human review (or auto-merges with confidence threshold)
- Logs WHAT it learned and WHY it considered the source authoritative

Implementation sketch:
```
agents/<expert>/auto_enrich/
  config.yml              ← search queries, sources, schedule
  pending_updates/        ← drafts awaiting review
  applied_updates/        ← approved + merged updates
  rejection_log/          ← drafts rejected with reason
```

### 2. Multi-agent self-enrichment (cross-pollination)

When Agent A discovers something Agent B should know, A files a "knowledge transfer note" that B reads on its next run. e.g. Customer Insights notices "B2B SaaS audience is increasingly procurement-gated post-2023" — Voice & Message and Hypothesis Generator should know this.

### 3. Knowledge versioning + provenance

Every claim in a knowledge file has provenance: (a) source URL or paper, (b) when added, (c) which agent's auto-enrichment added it, (d) confidence score. Stale claims auto-flag for review.

### 4. Specialization tag taxonomy + auto-routing

Tags become a queryable index. When a new task arrives, the system can ask: "which agent has the specialization tags most relevant to this task?" — and route automatically.

Example tag taxonomy (DAG, not flat):
```
research/
  audience/
    personas
    JTBD
    voice_of_customer
  pages/
    preservation_analysis
    trust_anatomy
copy/
  headlines
  hooks
  value_proposition
strategy/
  channel_planning
  audience_segmentation
  test_program_management
analysis/
  hypothesis_validation
  decision_synthesis
```

Tags hang together by parent path. No agent should claim tags from MORE THAN
3 disjoint subtrees (that's the user's "not all-functional" rule).

### 5. Human-in-loop discipline (initial phase)

User said: "перший час буду дивитись на всі рішення і давати свій фідбек."

So the autonomous enrichment must NOT auto-merge. Workflow:
- Agent drafts update → goes to `pending_updates/`
- User reviews via a dashboard view (in viz/)
- User approves → merge to `knowledge/` + log to `applied_updates/`
- User rejects → log to `rejection_log/` with reason (which becomes training signal)

Over time, confidence thresholds can be raised so simple updates auto-merge while novel claims still require human review.

---

## Implementation sequence (suggested, not committed)

### Phase 5j — Specialization tag taxonomy + auto-routing
- Define DAG of tags in `agents/_tag_taxonomy.yml`
- Validate every agent's tags against taxonomy
- Build a `route_task_to_agent(task_description) → agent_name` utility

### Phase 5k — Knowledge provenance metadata
- Add `_provenance.json` next to each knowledge file: `{added_at, source, confidence, last_reviewed}`
- Build `knowledge_lineage_audit.py` script to flag stale claims

### Phase 5l — Daily auto-enrichment (per agent)
- `auto_enrich/config.yml` per agent declaring search queries
- `scripts/daily_enrich.py` runs all agents' auto_enrich
- Drafts go to `pending_updates/`
- Cron task at 6am daily

### Phase 5m — Human review dashboard
- Extend `viz/` with `/pending` route showing all `pending_updates/` across agents
- Approve/reject buttons trigger merge or rejection_log

### Phase 5n — Cross-agent knowledge transfer
- Standard "knowledge transfer note" format
- Agents check incoming notes at run start

---

## Why this ordering

5j first because routing tags must be stable before auto-enrichment knows where to put new info.

5k next because we can't auto-enrich without provenance discipline (otherwise stale junk accumulates).

5l-5n are the actual autonomous behaviors, gated by human review during the initial phase.

---

## What we're NOT doing in Phase 5 itself

- No actual auto-enrichment yet (would need WebSearch quota + scheduled jobs + human-review UI)
- No tag taxonomy validation yet (specialization_tags are still informal)
- No provenance metadata yet (knowledge files are just markdown)

Phase 5 (current) = solid foundation: agent-as-system + persistent state + specialization tags declared. Everything above builds on this.

---

## Open questions for user input on next session

1. Tag taxonomy: do we adopt the DAG sketch above, or evolve from informal tags?
2. Auto-enrichment cadence: daily? weekly? per-agent?
3. Auto-enrichment confidence threshold for auto-merge vs review?
4. Search sources to whitelist for each agent's auto-enrichment?
5. Cross-agent knowledge transfer mechanism: push (A files note for B) or pull (B queries A's recent learnings)?

These are deferred to a future session. Phase 5 prototype proves the architecture; future phases activate the autonomy.
