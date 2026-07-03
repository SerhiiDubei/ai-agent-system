"""Helpers for rendering CurrentPerformance + budget into agent prompts.

Phase 5d.1 — when operator provides real analytics data, agents need
clean LLM-friendly rendering that:
  1. Skips None fields (don't pollute prompt with "monthly_impressions: None")
  2. Groups fields by semantic block (acquisition / engagement / conversion / money / funnel)
  3. Renders funnel_steps as a table, not nested JSON
  4. Returns empty string if no data at all
"""

from __future__ import annotations

from ai_agent_system.marketing.brief import (
    CurrentPerformance,
    OperatingConstraints,
)


def _kv_line(label: str, value, suffix: str = "") -> str:
    """One key-value line, only if value is not None."""
    if value is None:
        return ""
    return f"  {label}: {value}{suffix}\n"


def render_budget_block(constraints: OperatingConstraints | None) -> str:
    """Render budget-only fields. Returns empty string if no budget data."""
    if not constraints:
        return ""

    has_budget = any([
        constraints.total_program_budget_usd,
        constraints.target_cpa_usd,
        constraints.current_cpa_usd,
    ])
    if not has_budget:
        return ""

    lines = ["\n\nBUDGET CONSTRAINTS (use for ROI math, not just traffic math):\n"]
    if constraints.total_program_budget_usd:
        lines.append(f"  total_program_budget_usd: ${constraints.total_program_budget_usd:,.2f}\n")
    if constraints.target_cpa_usd:
        lines.append(f"  target_cpa_usd: ${constraints.target_cpa_usd:,.2f}\n")
    if constraints.current_cpa_usd:
        lines.append(f"  current_cpa_usd: ${constraints.current_cpa_usd:,.2f}\n")

    if constraints.target_cpa_usd and constraints.current_cpa_usd:
        delta = constraints.current_cpa_usd - constraints.target_cpa_usd
        gap_pct = (delta / constraints.target_cpa_usd) * 100
        lines.append(
            f"  CPA gap: current is ${delta:+,.2f} vs target "
            f"({gap_pct:+.1f}% over)\n"
        )

    return "".join(lines)


def render_performance_block(perf: CurrentPerformance | None) -> str:
    """Render CurrentPerformance into a multi-section prompt block.

    Skips empty sections entirely. Returns empty string if no perf data.
    """
    if not perf:
        return ""

    sections: list[str] = []

    # Acquisition
    acq = "".join([
        _kv_line("monthly_impressions", f"{perf.monthly_impressions:,}" if perf.monthly_impressions else None),
        _kv_line("monthly_clicks", f"{perf.monthly_clicks:,}" if perf.monthly_clicks else None),
        _kv_line("ctr_pct", perf.ctr_pct, "%"),
        _kv_line("cpc_usd", f"${perf.cpc_usd:.2f}" if perf.cpc_usd else None),
        _kv_line("cpm_usd", f"${perf.cpm_usd:.2f}" if perf.cpm_usd else None),
    ])
    if acq:
        sections.append("ACQUISITION (ad-side):\n" + acq)

    # Engagement
    eng = "".join([
        _kv_line("bounce_rate_pct", perf.bounce_rate_pct, "%"),
        _kv_line("median_time_on_page_seconds", perf.median_time_on_page_seconds, "s"),
        _kv_line("scroll_depth_50_pct", perf.scroll_depth_50_pct, "%"),
        _kv_line("scroll_depth_75_pct", perf.scroll_depth_75_pct, "%"),
    ])
    if eng:
        sections.append("ENGAGEMENT:\n" + eng)

    # Conversion
    conv = "".join([
        _kv_line("overall_conversion_rate_pct", perf.overall_conversion_rate_pct, "%"),
        _kv_line("mobile_conversion_rate_pct", perf.mobile_conversion_rate_pct, "%"),
        _kv_line("desktop_conversion_rate_pct", perf.desktop_conversion_rate_pct, "%"),
        _kv_line("monthly_conversions", f"{perf.monthly_conversions:,}" if perf.monthly_conversions else None),
    ])
    if conv:
        sections.append("CONVERSION:\n" + conv)

    # Form-specific
    form = "".join([
        _kv_line("form_start_rate_pct", perf.form_start_rate_pct, "%"),
        _kv_line("form_completion_rate_pct", perf.form_completion_rate_pct, "%"),
    ])
    if form:
        sections.append("FORM-SPECIFIC:\n" + form)
        # Diagnostic insight (deterministic — give the LLM the math)
        if perf.form_start_rate_pct and perf.form_completion_rate_pct:
            page_loss = 100 - perf.form_start_rate_pct
            form_loss = 100 - perf.form_completion_rate_pct
            sections[-1] += (
                f"  ⤷ DIAGNOSTIC: {page_loss:.1f}% of LP visitors don't engage form; "
                f"of those who start, {form_loss:.1f}% abandon mid-form. "
                f"Bigger loss is at the {'PAGE level' if page_loss > form_loss else 'FORM level'}.\n"
            )

    # Money / unit economics
    money = "".join([
        _kv_line("cpl_usd", f"${perf.cpl_usd:.2f}" if perf.cpl_usd else None),
        _kv_line("roas", f"{perf.roas:.2f}x" if perf.roas else None),
        _kv_line("aov_usd", f"${perf.aov_usd:.2f}" if perf.aov_usd else None),
        _kv_line("ltv_usd", f"${perf.ltv_usd:.2f}" if perf.ltv_usd else None),
    ])
    if money:
        sections.append("MONEY / UNIT ECONOMICS:\n" + money)

    # Funnel steps (rendered as table)
    if perf.funnel_steps:
        funnel_lines = ["FUNNEL DROP-OFF (per step):\n"]
        funnel_lines.append("  | Step                | Entering | Continuing | Rate    | Median time |\n")
        funnel_lines.append("  |---------------------|---------:|-----------:|--------:|------------:|\n")
        for s in perf.funnel_steps:
            time_str = f"{s.median_time_seconds}s" if s.median_time_seconds else "—"
            funnel_lines.append(
                f"  | {s.name:<19} | {s.visitors_entering:>8,} | "
                f"{s.visitors_continuing:>10,} | {s.completion_rate_pct:>6.1f}% | "
                f"{time_str:>11} |\n"
            )
        if perf.biggest_dropoff_step_name:
            funnel_lines.append(
                f"  ⤷ OPERATOR FLAGGED biggest drop-off: {perf.biggest_dropoff_step_name!r}\n"
            )
        sections.append("".join(funnel_lines))

    # Operator notes (free text)
    if perf.operator_notes:
        sections.append(f"OPERATOR NOTES:\n  {perf.operator_notes}\n")

    if not sections:
        return ""

    return "\n\nCURRENT PERFORMANCE METRICS (real data from operator's analytics):\n" + "\n".join(sections)
