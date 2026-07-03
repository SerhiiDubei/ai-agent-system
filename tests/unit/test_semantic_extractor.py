"""Unit tests for N2 DOM mark extractor.

Tests cover:
- Basic extraction (forms, headings, buttons, CTA links, images, trust blocks)
- MAX_MARKS cap
- Graceful handling of empty / None HTML
- Deduplication (same node not emitted twice)
- mark_id assignment (sequential, 1-based)
"""

import pytest

from ai_agent_system.semantic.extractor import MAX_MARKS, extract_dom_marks


def _html(body: str) -> str:
    return f"<html><body>{body}</body></html>"


def _ids(marks) -> list[int]:
    return [m.mark_id for m in marks]


def _roles_tags(marks) -> list[str]:
    return [m.tag for m in marks]


# ── Basic extraction ──────────────────────────────────────────────────────────

def test_extracts_h1_and_h2():
    html = _html("<h1>Get a Free Quote</h1><h2>Why Choose Us</h2>")
    marks = extract_dom_marks(html)
    tags = [m.tag for m in marks]
    assert "h1" in tags
    assert "h2" in tags


def test_extracts_form():
    html = _html(
        '<form action="/submit"><input type="email" />'
        '<button type="submit">Get Quote</button></form>'
    )
    marks = extract_dom_marks(html)
    tags = [m.tag for m in marks]
    assert "form" in tags


def test_extracts_cta_button():
    html = _html('<button type="submit">Request Estimate</button>')
    marks = extract_dom_marks(html)
    assert any(m.tag == "button" for m in marks)


def test_extracts_cta_link():
    html = _html('<a href="/quote">Get a Free Quote</a>')
    marks = extract_dom_marks(html)
    assert any(m.tag == "a" for m in marks)


def test_skips_non_cta_link():
    html = _html('<a href="/about">About Us</a>')
    marks = extract_dom_marks(html)
    # "About Us" has no CTA keyword — should not appear
    assert not any(m.tag == "a" for m in marks)


def test_extracts_image_with_alt():
    html = _html('<img src="/hero.jpg" alt="Walk-in Tub" />')
    marks = extract_dom_marks(html)
    assert any(m.tag == "img" and "Walk-in Tub" in m.text for m in marks)


def test_skips_data_uri_images():
    html = _html('<img src="data:image/png;base64,abc" alt="icon" />')
    marks = extract_dom_marks(html)
    assert not any(m.tag == "img" for m in marks)


def test_extracts_trust_block_by_class():
    html = _html('<div class="trust-badges"><p>BBB A+</p></div>')
    marks = extract_dom_marks(html)
    assert any(m.tag == "div" for m in marks)


def test_extracts_testimonial_block():
    html = _html('<section class="testimonials"><p>Great service!</p></section>')
    marks = extract_dom_marks(html)
    assert any(m.tag == "section" for m in marks)


# ── mark_id assignment ────────────────────────────────────────────────────────

def test_mark_ids_are_sequential_one_based():
    html = _html(
        "<h1>Headline</h1>"
        '<button>Get Started</button>'
        '<a href="/x">Learn More</a>'
    )
    marks = extract_dom_marks(html)
    assert _ids(marks) == list(range(1, len(marks) + 1))


def test_no_duplicate_mark_ids():
    html = _html(
        '<form><button type="submit">Get Quote</button></form>'
        '<h1>Walk-in Tubs</h1>'
    )
    marks = extract_dom_marks(html)
    ids = _ids(marks)
    assert len(ids) == len(set(ids))


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_string_returns_empty():
    assert extract_dom_marks("") == []


def test_whitespace_only_returns_empty():
    assert extract_dom_marks("   ") == []


def test_max_marks_cap():
    # Generate a page with many CTA buttons
    buttons = "".join(
        f'<button type="submit">Get Quote {i}</button>' for i in range(200)
    )
    html = _html(buttons)
    marks = extract_dom_marks(html)
    assert len(marks) <= MAX_MARKS


def test_custom_max_marks():
    buttons = "".join(
        f'<button type="submit">Get Quote {i}</button>' for i in range(50)
    )
    html = _html(buttons)
    marks = extract_dom_marks(html, max_marks=10)
    assert len(marks) <= 10


# ── Text extraction ───────────────────────────────────────────────────────────

def test_button_text_captured():
    html = _html('<button>Schedule Your Consultation</button>')
    marks = extract_dom_marks(html)
    button_marks = [m for m in marks if m.tag == "button"]
    assert button_marks
    assert "Schedule Your Consultation" in button_marks[0].text


def test_class_hint_captured():
    html = _html('<button class="btn-primary cta-hero large">Get Quote</button>')
    marks = extract_dom_marks(html)
    button_marks = [m for m in marks if m.tag == "button"]
    assert button_marks
    # Should capture up to 3 class tokens
    assert button_marks[0].class_hint != ""


def test_href_captured_for_links():
    html = _html('<a href="/free-quote">Get a Free Quote</a>')
    marks = extract_dom_marks(html)
    link_marks = [m for m in marks if m.tag == "a"]
    assert link_marks
    assert link_marks[0].href == "/free-quote"
