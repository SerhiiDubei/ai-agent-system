"""DOM element extraction for Set-of-Mark (SoM) prompting — N2.

Parses HTML with selectolax (Lexbor backend) and returns a flat list of
DomMark objects.  Each mark gets a sequential 1-based ID matching the
order the LLM will see them in the JSON prompt.

Extraction priority (important for the LLM's mark-ID reference):
  1. Forms — highest signal for lead_form role
  2. H1/H2/H3 headings — hero_headline / hero_subheadline
  3. Buttons and submit inputs — primary_cta / secondary_cta candidates
  4. CTA-like anchor links — links with conversion-intent words
  5. Images with alt text — hero_image / before_after candidates
  6. Trust / social-proof blocks — heuristic class-name sniff

Marks are capped at MAX_MARKS to avoid overwhelming the vision LLM on
dense landing pages (anti-pattern #3 from N2 research).
"""

from __future__ import annotations

import re
from html import unescape
from typing import Optional

from selectolax.lexbor import LexborHTMLParser

from ai_agent_system.semantic.models import DomMark

MAX_MARKS = 80

# Words that strongly signal CTA intent in link / button text
_CTA_RE = re.compile(
    r"\b(get|request|start|book|schedule|call|contact|free|quote|estimate|apply"
    r"|sign|download|try|buy|order|claim|check|find|learn|see|join|register"
    r"|compare|discover|explore)\b",
    re.IGNORECASE,
)

# Class / id patterns that signal trust / social-proof blocks
_TRUST_RE = re.compile(
    r"trust|testimonial|review|rating|badge|certif|guarantee|award"
    r"|social.?proof|before.?after|bbb|accredit|partner|logo",
    re.IGNORECASE,
)

_SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "svg", "path", "meta", "link", "head", "template"}
)


def _visible_text(node, max_chars: int = 200) -> str:
    raw = node.text(strip=True, deep=True, separator=" ")
    return unescape(raw)[:max_chars].strip() if raw else ""


def _class_hint(node, max_tokens: int = 3) -> str:
    cls = node.attributes.get("class") or ""
    tokens = [t for t in cls.split() if len(t) > 2][:max_tokens]
    return " ".join(tokens)[:80]


def _make_mark(mark_id: int, tag: str, node, *, href: str = "", text: str = "") -> DomMark:
    return DomMark(
        mark_id=mark_id,
        tag=tag,
        text=text or _visible_text(node),
        role_attr=node.attributes.get("role", ""),
        href=href[:200],
        class_hint=_class_hint(node),
    )


def extract_dom_marks(html: str, max_marks: int = MAX_MARKS) -> list[DomMark]:
    """Parse ``html`` and return up to ``max_marks`` DomMark objects.

    Returns an empty list if html is falsy — callers must handle the
    degraded case (LLM classifies from screenshot alone).
    """
    if not html:
        return []

    parser = LexborHTMLParser(html)
    marks: list[DomMark] = []
    seen: set[int] = set()

    def add(tag: str, node, *, href: str = "", text: str = "") -> bool:
        if len(marks) >= max_marks:
            return False
        nid = id(node)
        if nid in seen:
            return False
        t = text or _visible_text(node)
        if not t and tag not in ("img", "form"):
            return False
        seen.add(nid)
        marks.append(_make_mark(len(marks) + 1, tag, node, href=href, text=t))
        return True

    # 1. Forms — always first so mark_ids cluster near the top
    for node in parser.css("form"):
        add("form", node, text=_visible_text(node, max_chars=120))

    # 2. Headings
    for sel in ("h1", "h2", "h3"):
        for node in parser.css(sel):
            add(sel, node)

    # 3. Buttons / submit inputs
    for node in parser.css("button, input[type='submit'], input[type='button']"):
        val = node.attributes.get("value", "")
        add(node.tag, node, text=val or _visible_text(node))

    # 4. CTA-like anchor links
    for node in parser.css("a[href]"):
        href = node.attributes.get("href", "")
        t = _visible_text(node)
        if t and _CTA_RE.search(t):
            add("a", node, href=href, text=t)

    # 5. Images with alt text (skip tiny / data-URI)
    for node in parser.css("img"):
        src = node.attributes.get("src", "")
        if not src or src.startswith("data:"):
            continue
        alt = node.attributes.get("alt", "")
        add("img", node, href=src, text=alt)

    # 6. Trust / social-proof blocks by class/id heuristic
    for node in parser.css("section, div, aside, article"):
        cls = node.attributes.get("class", "")
        nid_attr = node.attributes.get("id", "")
        if _TRUST_RE.search(cls) or _TRUST_RE.search(nid_attr):
            add(node.tag, node)

    return marks
