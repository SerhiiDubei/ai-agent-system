"""PII sanitizer — Presidio + landing-page regex — N1.

Key insight from N1 research:
  Business contact info ON the page is SIGNAL, not PII to scrub.
  Phone numbers and emails on a lead-gen LP are the product.
  Only redact PII in: form values, query strings, console logs.

PRESERVE_ON_PAGE allowlist controls which entity types are kept
when sanitizing page-visible text (on_page=True).

Per N1 anti-pattern #4: DO NOT scrub business phone/email from page copy.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# Tel/mailto href patterns
_TEL_HREF = re.compile(r'href=["\']tel:([^"\']+)["\']', re.IGNORECASE)
_MAIL_HREF = re.compile(r'href=["\']mailto:([^"\']+)["\']', re.IGNORECASE)
_SSN_LIKE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# US toll-free prefixes — keep these (they're business numbers)
_TOLL_FREE = {"800", "833", "844", "855", "866", "877", "888"}
_GENERIC_EMAILS = {"info@", "sales@", "contact@", "support@", "hello@", "team@"}

# Entity types to KEEP in on-page text (they are content, not personal PII)
PRESERVE_ON_PAGE = {"PHONE_NUMBER", "EMAIL_ADDRESS", "URL", "DOMAIN_NAME"}

# Lazy-loaded Presidio engines
_analyzer = None
_anonymizer = None


def _get_engines():
    global _analyzer, _anonymizer
    if _analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine  # type: ignore[import]
            from presidio_anonymizer import AnonymizerEngine  # type: ignore[import]
            _analyzer = AnalyzerEngine()
            _anonymizer = AnonymizerEngine()
        except ImportError:
            log.warning("presidio not installed; falling back to regex-only PII sanitizer")
    return _analyzer, _anonymizer


def sanitize_text(text: str, *, on_page: bool = True) -> str:
    """Sanitize text using Presidio NER.

    on_page=True → keep business contact info (phone/email visible on LP).
    on_page=False → redact everything (for form values, query strings).
    """
    if not text:
        return text

    analyzer, anonymizer = _get_engines()

    if analyzer is None:
        # Presidio not installed — apply only regex-based cleanup
        return _regex_sanitize(text)

    try:
        results = analyzer.analyze(text=text, language="en")
        if on_page:
            results = [r for r in results if r.entity_type not in PRESERVE_ON_PAGE]
        if not results:
            return text
        return anonymizer.anonymize(text=text, analyzer_results=results).text
    except Exception as exc:
        log.warning("presidio sanitize failed: %s", exc)
        return _regex_sanitize(text)


def sanitize_html_keep_structure(html: str) -> str:
    """Sanitize HTML while preserving tag structure.

    - Keeps toll-free business numbers in tel: hrefs
    - Keeps generic business emails (info@, sales@, ...)
    - Redacts SSN-like patterns
    """
    if not html:
        return html

    def _scrub_tel(m: re.Match) -> str:
        num = m.group(1)
        digits = re.sub(r"\D", "", num)
        prefix = digits[-10:-7] if len(digits) >= 10 else digits[:3]
        if prefix in _TOLL_FREE:
            return m.group(0)   # keep toll-free business line
        return 'href="tel:[REDACTED]"'

    def _scrub_mail(m: re.Match) -> str:
        addr = m.group(1).lower()
        if any(addr.startswith(p) for p in _GENERIC_EMAILS):
            return m.group(0)   # keep generic business email
        return 'href="mailto:[REDACTED]"'

    html = _TEL_HREF.sub(_scrub_tel, html)
    html = _MAIL_HREF.sub(_scrub_mail, html)
    html = _SSN_LIKE.sub("[REDACTED_SSN]", html)
    return html


def _regex_sanitize(text: str) -> str:
    """Minimal regex fallback when Presidio is not installed."""
    text = _SSN_LIKE.sub("[REDACTED_SSN]", text)
    return text
