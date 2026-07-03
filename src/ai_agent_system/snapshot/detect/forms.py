"""Form extractor using selectolax (Lexbor backend) — N1.

Per N1 research: selectolax is 5-30× faster than BeautifulSoup.
DO NOT use BeautifulSoup for this — too slow at scale.
"""

from __future__ import annotations

import logging

from selectolax.lexbor import LexborHTMLParser  # type: ignore[import]

from ai_agent_system.snapshot.models import DetectedForm, FormField

log = logging.getLogger(__name__)

_SKIP_TYPES = {"hidden", "submit", "button", "reset", "image"}


def extract_forms(html: str, base_url: str) -> list[DetectedForm]:
    """Extract all forms from raw HTML.

    Args:
        html: Raw HTML string.
        base_url: Page URL used as default form action fallback.

    Returns:
        List of DetectedForm, skipping hidden/submit inputs.
    """
    if not html:
        return []

    try:
        tree = LexborHTMLParser(html)
    except Exception as exc:
        log.warning("form extractor: HTML parse error: %s", exc)
        return []

    forms: list[DetectedForm] = []

    for form_el in tree.css("form"):
        action = form_el.attributes.get("action") or base_url
        method = (form_el.attributes.get("method") or "POST").upper()

        fields: list[FormField] = []
        for inp in form_el.css("input, select, textarea"):
            inp_type = (inp.attributes.get("type") or "text").lower()
            if inp_type in _SKIP_TYPES:
                continue

            name = inp.attributes.get("name") or inp.attributes.get("id") or ""
            if not name:
                continue

            # Try to find a linked label
            inp_id = inp.attributes.get("id", "")
            label_text: str | None = None
            if inp_id:
                label_el = form_el.css_first(f'label[for="{inp_id}"]')
                if label_el:
                    label_text = label_el.text(strip=True) or None

            fields.append(
                FormField(
                    name=name,
                    type=inp_type,
                    label=label_text,
                    required="required" in inp.attributes,
                    placeholder=inp.attributes.get("placeholder"),
                )
            )

        submit_el = form_el.css_first('button[type="submit"], input[type="submit"], button:not([type])')
        submit_text = submit_el.text(strip=True) if submit_el else None

        forms.append(
            DetectedForm(
                action=action,
                method=method,
                fields=fields,
                submit_text=submit_text or None,
            )
        )

    return forms
