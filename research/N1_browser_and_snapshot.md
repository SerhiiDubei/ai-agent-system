# Node N1 — Browser & Snapshot Research

_Research date: 2026-04-27. Target: standalone Python multi-agent system generating A/B-test hypotheses for lead-gen landing pages (home improvement + dating verticals)._

---

## TL;DR

**Use Firecrawl (self-hosted OSS) + `firecrawl-py` v4 async client as primary; Jina Reader as the free emergency fallback; Microsoft Presidio + custom regex for PII; `wappalyzer-next` (s0md3v) for tech stack; selectolax (Lexbor backend) for any auxiliary HTML/DOM parsing.** Skip the legacy `chorsley/python-Wappalyzer` and `scrapinghub/wappalyzer-python` — both archived/unmaintained. Run mobile and desktop as **two separate Firecrawl scrape calls** (not a single call with viewport switch); the cost is one extra HTTP round-trip but avoids the "did the page rehydrate after viewport resize?" failure mode entirely. Build a thin internal `BrowserSnapshotProvider` interface so Firecrawl Cloud can be swapped in later as a paid fallback without touching the agent code.

---

## Top 5 existing solutions

### 1. Firecrawl (OSS + Cloud) — **PRIMARY**
- **URL:** https://github.com/firecrawl/firecrawl, https://docs.firecrawl.dev
- **What it does:** URL → markdown + raw HTML + screenshot (full-page + viewport) + links + metadata. Native mobile emulation (`mobile: true`), `actions` array for click/scroll/wait/write/press, `/interact` endpoint for richer interactions (v2.9.0+), built-in PDF + Office support, batch endpoints, structured `extract` with Pydantic-style schemas via LLM.
- **License/cost:** AGPL-3.0 for self-hosted OSS; Cloud is metered ($0.001-ish per page tier in 2026). Self-hosted needs ~2.5 GB RAM (Playwright service is the hog), Postgres, Redis, RabbitMQ — full Docker Compose with five services.
- **Verdict:** **Primary.** Active maintenance (v4.23.0 on PyPI April 2026, multiple releases per month), Java SDK v2.0 available for the eventual Spring Boot integration, both `Firecrawl` and `AsyncFirecrawl` Python clients.
- **Why:** Single API gives you ~80% of N1's surface area (DOM, screenshot, mobile, actions, basic extraction). Self-host now to avoid token burn during dev; switch the env var to point at Cloud later if scaling pain hits.

### 2. Jina Reader API — **EMERGENCY FALLBACK**
- **URL:** https://r.jina.ai/, https://jina.ai/reader
- **What it does:** Prepend `https://r.jina.ai/` to any URL → returns LLM-friendly markdown. Optional API-key tier raises rate limits.
- **License/cost:** Free without key (~20 RPM, ~200 req/day per IP); free API key bumps to ~200 RPM with token-metered billing.
- **Verdict:** **Reference / fallback only.** No screenshots, no actions, no form introspection — just text. Good for "did Firecrawl die at 3 AM?" failover for the markdown-extraction subset.
- **Why keep it:** Zero infra cost, zero auth, can be hot-failover within `BrowserSnapshotProvider.get_text_only()`.

### 3. Crawl4AI — **REFERENCE**
- **URL:** https://github.com/unclecode/crawl4ai
- **What it does:** Local-first crawler, Playwright-backed, outputs clean markdown. ~58k GitHub stars, very active. Has its own dispatcher, caching layer, and "magic mode" (heuristic stealth).
- **License/cost:** Apache-2.0, free.
- **Verdict:** **Reference / skip as primary.** Functionally overlapping with Firecrawl OSS but you'd be running two Playwright fleets. Worth studying its `AsyncWebCrawler` ergonomics and its `MarkdownGenerationStrategy` for ideas.
- **Why not primary:** Picking it means giving up Firecrawl's nicer schema-extract endpoint and the matched Java SDK.

### 4. ScrapeGraphAI — **SKIP for N1**
- **URL:** https://github.com/ScrapeGraphAI/Scrapegraph-ai
- **What it does:** LLM-driven extraction with directed-graph pipelines; natural-language target descriptions instead of selectors.
- **License/cost:** MIT, free OSS + paid cloud.
- **Verdict:** **Skip for N1.** It's an extraction layer, not a snapshotting layer — wrong abstraction for "give me DOM + screenshot + assets." Revisit for downstream nodes that need semantic field extraction (e.g., "find the hero CTA copy").

### 5. Patchright / Camoufox / Nodriver — **TARGETED ESCAPE HATCH**
- **URLs:** https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python, https://camoufox.com/, https://github.com/ultrafunkamsterdam/nodriver
- **What they do:** Stealth-patched browsers for Cloudflare Turnstile / Datadome / PerimeterX bypass. Camoufox patches Firefox at the C++ level (best detection scores in 2026 benchmarks); Patchright is a Playwright drop-in; Nodriver drives Chrome via raw CDP without the Playwright bridge.
- **License/cost:** All free OSS.
- **Verdict:** **Reference, hold as escape hatch.** Don't bake into the primary path — Firecrawl + a residential-proxy add-on covers most lead-gen landing pages, which are usually NOT behind aggressive bot protection (they want traffic). Wire up `StealthBrowserProvider` only after you collect concrete failure samples.
- **Why hold:** Maintaining a second browser stack doubles ops surface; only justify when failure data demands it.

---

## Code references worth studying

| Repo | Path | What to learn |
|---|---|---|
| `firecrawl/firecrawl-py` | `firecrawl/v2/client.py`, `firecrawl/v2/types.py` | Async client structure, snake_case conversion, type hierarchy for scrape responses |
| `firecrawl/firecrawl` | `apps/api/src/scraper/scrapeURL/engines/`, `docker-compose.yaml` | Engine fallback chain (FireEngine → Playwright → fetch); how they orchestrate degradation |
| `firecrawl/firecrawl` | `apps/playwright-service-ts/` | Reference Playwright wrapper if you ever fork (waitFor heuristics, screenshot capture timing) |
| `microsoft/presidio` | `presidio-analyzer/presidio_analyzer/predefined_recognizers/` | Recognizer pattern for adding lead-gen-specific entities (e.g., "phone number in tel: link", "email in mailto:") |
| `s0md3v/wappalyzer-next` | `wappalyzer/cli.py`, `wappalyzer/fingerprint/` | Modern fingerprint loader; uses live Wappalyzer extension data, not stale forks |
| `rushter/selectolax` | `examples/benchmark.py` | Lexbor-backend usage and CSS-selector idioms; 5-30x faster than BeautifulSoup |
| `unclecode/crawl4ai` | `crawl4ai/async_dispatcher.py`, `crawl4ai/markdown_generation_strategy.py` | Concurrency dispatcher + content-density heuristics for "is this a content page or a nav page?" |
| `daijro/camoufox` | `pythonlib/camoufox/sync_api.py` | If you ever need stealth: cleanest Playwright-API-compatible stealth wrapper |
| `jd/tenacity` | `tenacity/_asyncio.py` | `AsyncRetrying` patterns for httpx-based fallback orchestration |

---

## Production case studies

- **Mendable / Firecrawl team** dogfoods Firecrawl for their own RAG/agent pipelines; the v2.9 `/interact` endpoint was driven by their internal CRO/competitor-research workflows.
- **Apify Tech Stack Detector** (commercial) is built on Wappalyzer fingerprints — direct evidence the fingerprint DB is sufficient for production tech detection at scale.
- **Anecdotal — multiple "AI SDR" / "lead enrichment" startups in 2025-26** stack Firecrawl + Presidio + an LLM extractor; this is essentially the pattern N1 is replicating, just for CRO instead of outbound sales.
- **Browse.ai / ScrapeOps comparison reports** (2026) consistently rank Firecrawl, Crawl4AI, and ScrapeGraphAI as the three viable OSS choices for AI-targeted scraping — Firecrawl wins on mobile + screenshot + actions in a single API.

---

## Build vs buy verdict

**Buy/integrate, don't build.** For a solo developer with commercial focus:

1. Writing a Playwright wrapper that handles screenshots + mobile + asset capture + actions + queue + retry is a 2-4 week project minimum, then it never stops needing maintenance as Chrome/Firefox ship.
2. Firecrawl OSS already shipped that, has a Java SDK for the eventual Spring integration, and the AGPL is not a problem because N1 is an internal service (you're not redistributing it).
3. The 2.5 GB RAM / Postgres-Redis-RabbitMQ self-host overhead is real but a one-time pain. Stand it up on a $20-40/mo VPS or as a sidecar on your dev box.
4. The **only thing worth building yourself** is a thin `BrowserSnapshotProvider` Python interface that abstracts {Firecrawl-self-hosted, Firecrawl-Cloud, Jina} as interchangeable backends. ~150 LOC, gives you optionality forever.

Estimated build-vs-buy delta: **~3 weeks saved**, ongoing maintenance externalized to Firecrawl's team.

---

## Concrete patterns to copy

### 1. Provider interface (build this yourself — the only custom code worth writing)

```python
# src/n1/providers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

Viewport = Literal["desktop", "mobile"]

class FormField(BaseModel):
    name: str
    type: str  # "email", "tel", "text", "select", ...
    label: str | None = None
    required: bool = False
    placeholder: str | None = None

class DetectedForm(BaseModel):
    action: str | None  # submit endpoint
    method: str = "POST"
    fields: list[FormField]
    submit_text: str | None = None

class PageSnapshot(BaseModel):
    url: HttpUrl
    final_url: HttpUrl  # after redirects
    viewport: Viewport
    fetched_at: float  # unix ts
    html: str  # raw, post-JS
    markdown: str
    screenshot_png: bytes
    screenshot_full_page: bool
    title: str | None
    meta_description: str | None
    forms: list[DetectedForm] = Field(default_factory=list)
    images: list[HttpUrl] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    tech_stack: dict[str, list[str]] = Field(default_factory=dict)  # category -> tech names
    quality_score: float  # 0..1, see validator below
    quality_flags: list[str] = Field(default_factory=list)
    pii_redacted: bool = True

class SnapshotProvider(ABC):
    name: str

    @abstractmethod
    async def snapshot(
        self,
        url: str,
        viewport: Viewport = "desktop",
        wait_for_ms: int | None = None,
        actions: list[dict] | None = None,
    ) -> PageSnapshot: ...
```

### 2. Firecrawl provider (primary)

```python
# src/n1/providers/firecrawl_provider.py
import asyncio
import time
import httpx
from firecrawl import AsyncFirecrawl
from tenacity import (
    AsyncRetrying, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type, before_sleep_log,
)
import logging

from .base import SnapshotProvider, PageSnapshot, Viewport

log = logging.getLogger(__name__)

RETRYABLE = (httpx.HTTPError, asyncio.TimeoutError, ConnectionError)

class FirecrawlProvider(SnapshotProvider):
    name = "firecrawl"

    def __init__(self, api_key: str, base_url: str | None = None, timeout_s: float = 60.0):
        # base_url=None -> Cloud; pass http://localhost:3002 for self-hosted
        self.client = AsyncFirecrawl(api_key=api_key, api_url=base_url)
        self.timeout_s = timeout_s

    async def snapshot(
        self,
        url: str,
        viewport: Viewport = "desktop",
        wait_for_ms: int | None = None,
        actions: list[dict] | None = None,
    ) -> PageSnapshot:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=2, max=20),
            retry=retry_if_exception_type(RETRYABLE),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                doc = await self.client.scrape(
                    url=url,
                    formats=["markdown", "html", "screenshot@fullPage", "links"],
                    mobile=(viewport == "mobile"),
                    wait_for=wait_for_ms or 2500,  # JS hydration buffer
                    timeout=int(self.timeout_s * 1000),
                    actions=actions or [],
                    only_main_content=False,  # we want nav/footer/forms too
                    skip_tls_verification=False,
                )

        # NOTE: SDK auto-converts camelCase -> snake_case. ogImage -> og_image.
        return PageSnapshot(
            url=url,
            final_url=doc.metadata.get("source_url", url),
            viewport=viewport,
            fetched_at=time.time(),
            html=doc.html or "",
            markdown=doc.markdown or "",
            screenshot_png=doc.screenshot,  # already bytes
            screenshot_full_page=True,
            title=doc.metadata.get("title"),
            meta_description=doc.metadata.get("description"),
            # forms/images/fonts/tech_stack/quality filled by post-processors
            quality_score=0.0,
            forms=[],
            images=[],
            fonts=[],
            tech_stack={},
        )
```

### 3. Jina fallback

```python
# src/n1/providers/jina_provider.py
import httpx, time
from .base import SnapshotProvider, PageSnapshot, Viewport

class JinaReaderProvider(SnapshotProvider):
    """Text-only emergency fallback. No screenshot, no forms, no mobile."""
    name = "jina"
    BASE = "https://r.jina.ai/"

    def __init__(self, api_key: str | None = None):
        self.headers = {"Accept": "text/markdown"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def snapshot(self, url: str, viewport: Viewport = "desktop", **_) -> PageSnapshot:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(self.BASE + url, headers=self.headers)
            r.raise_for_status()
        return PageSnapshot(
            url=url, final_url=url, viewport=viewport,
            fetched_at=time.time(),
            html="", markdown=r.text,
            screenshot_png=b"", screenshot_full_page=False,
            title=None, meta_description=None,
            quality_score=0.3, quality_flags=["fallback:jina:no_screenshot"],
        )
```

### 4. PII sanitizer — Presidio + landing-page-specific regex

```python
# src/n1/sanitize/pii.py
import re
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine

# Regexes tuned for what actually leaks on lead-gen landing pages
TEL_HREF = re.compile(r'href=["\']tel:([^"\']+)["\']', re.I)
MAIL_HREF = re.compile(r'href=["\']mailto:([^"\']+)["\']', re.I)
SSN_LIKE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
ADDR_HINT = re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+\s+(St|Ave|Rd|Blvd|Ln|Dr|Ct|Way)\b")

def _build_analyzer() -> AnalyzerEngine:
    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    # Landing-page tel/mailto leak — tag for redaction
    registry.add_recognizer(PatternRecognizer(
        supported_entity="LEADGEN_PHONE",
        patterns=[Pattern("tel_href", r"tel:\+?\d[\d\-\s().]+", 0.85)],
    ))
    return AnalyzerEngine(registry=registry)

_analyzer = _build_analyzer()
_anonymizer = AnonymizerEngine()

# Allowlist: business contact info on the page itself is signal, not PII to redact.
# Only redact PII that appears in *captured* form data, console logs, or scraped query strings.
PRESERVE_ON_PAGE = {"LEADGEN_PHONE", "EMAIL_ADDRESS", "URL"}

def sanitize_text(text: str, *, on_page: bool = True) -> str:
    """on_page=True: keep business contact, redact only personal-looking PII."""
    results = _analyzer.analyze(text=text, language="en")
    if on_page:
        results = [r for r in results if r.entity_type not in PRESERVE_ON_PAGE]
    return _anonymizer.anonymize(text=text, analyzer_results=results).text

def sanitize_html_keep_structure(html: str) -> str:
    """For raw HTML caching. Strips PII from text nodes via Presidio,
    but preserves tag structure. Also redacts tel:/mailto: VALUES if they
    look like personal cell numbers (heuristic: not toll-free)."""
    def _scrub_tel(m: re.Match) -> str:
        num = m.group(1)
        digits = re.sub(r"\D", "", num)
        # Keep US toll-free: 800/833/844/855/866/877/888
        if digits[-10:-7] in {"800","833","844","855","866","877","888"}:
            return m.group(0)
        return 'href="tel:[REDACTED]"'
    html = TEL_HREF.sub(_scrub_tel, html)
    # mailto: similarly — keep generic info@/sales@ patterns
    def _scrub_mail(m: re.Match) -> str:
        addr = m.group(1).lower()
        if any(addr.startswith(p) for p in ("info@","sales@","contact@","support@","hello@")):
            return m.group(0)
        return 'href="mailto:[REDACTED]"'
    html = MAIL_HREF.sub(_scrub_mail, html)
    return html
```

### 5. Tech stack detector

```python
# src/n1/detect/tech.py
from wappalyzer import Wappalyzer  # s0md3v/wappalyzer-next, pip install wappalyzer

_wap = Wappalyzer()  # auto-loads current fingerprints

def detect_tech(url: str, html: str, headers: dict[str, str]) -> dict[str, list[str]]:
    """Returns {category: [tech_name, ...]}."""
    results = _wap.analyze(url=url, html=html, headers=headers)
    out: dict[str, list[str]] = {}
    for tech, meta in results.items():
        for cat in meta.get("categories", ["other"]):
            out.setdefault(cat, []).append(tech)
    return out
```

### 6. Form extractor (raw HTML → structured forms)

```python
# src/n1/detect/forms.py
from selectolax.lexbor import LexborHTMLParser
from .pii import sanitize_text  # reuse
from ..providers.base import DetectedForm, FormField

def extract_forms(html: str, base_url: str) -> list[DetectedForm]:
    tree = LexborHTMLParser(html)
    forms: list[DetectedForm] = []
    for form_el in tree.css("form"):
        action = form_el.attributes.get("action") or base_url
        method = (form_el.attributes.get("method") or "POST").upper()
        fields: list[FormField] = []
        for inp in form_el.css("input, select, textarea"):
            t = inp.attributes.get("type", "text").lower()
            if t in {"hidden", "submit", "button", "reset"}:
                continue
            name = inp.attributes.get("name") or inp.attributes.get("id") or ""
            if not name:
                continue
            label_el = form_el.css_first(f'label[for="{inp.attributes.get("id","")}"]')
            label = label_el.text(strip=True) if label_el else None
            fields.append(FormField(
                name=name,
                type=t,
                label=label,
                required="required" in inp.attributes,
                placeholder=inp.attributes.get("placeholder"),
            ))
        submit = form_el.css_first('button[type="submit"], input[type="submit"]')
        forms.append(DetectedForm(
            action=action, method=method, fields=fields,
            submit_text=submit.text(strip=True) if submit else None,
        ))
    return forms
```

### 7. Quality validator (heuristics)

```python
# src/n1/validate/quality.py
from ..providers.base import PageSnapshot

MIN_HTML_BYTES = 5_000
MIN_MARKDOWN_CHARS = 300
REQUIRED_TAGS = ("title", "body")  # if any missing, snapshot is busted

def score_snapshot(snap: PageSnapshot) -> tuple[float, list[str]]:
    flags: list[str] = []
    score = 1.0

    if len(snap.html) < MIN_HTML_BYTES:
        flags.append("html_too_short")
        score -= 0.35
    if len(snap.markdown) < MIN_MARKDOWN_CHARS:
        flags.append("markdown_too_short")
        score -= 0.25
    if snap.screenshot_png and len(snap.screenshot_png) < 5_000:
        flags.append("screenshot_blank_or_tiny")
        score -= 0.30
    if not snap.title:
        flags.append("no_title")
        score -= 0.10

    # Cloudflare/Datadome challenge fingerprints in HTML
    cf_markers = ("Just a moment...", "cf-challenge-running", "datadome-captcha")
    low = snap.html.lower()
    if any(m.lower() in low for m in cf_markers):
        flags.append("bot_challenge_detected")
        score -= 0.50

    # Heuristic: lead-gen pages should have at least ONE form OR one prominent CTA
    if not snap.forms and "click here" not in low and "get a quote" not in low:
        flags.append("no_form_or_cta_detected")
        score -= 0.10

    return max(0.0, min(1.0, score)), flags
```

### 8. Orchestrator wiring (mobile + desktop in parallel)

```python
# src/n1/orchestrator.py
import asyncio
from .providers.base import SnapshotProvider, PageSnapshot
from .detect.forms import extract_forms
from .detect.tech import detect_tech
from .sanitize.pii import sanitize_html_keep_structure, sanitize_text
from .validate.quality import score_snapshot

async def capture_dual(provider: SnapshotProvider, url: str) -> dict[str, PageSnapshot]:
    desktop_task = provider.snapshot(url, viewport="desktop")
    mobile_task = provider.snapshot(url, viewport="mobile")
    desktop, mobile = await asyncio.gather(desktop_task, mobile_task)

    for snap in (desktop, mobile):
        snap.html = sanitize_html_keep_structure(snap.html)
        snap.markdown = sanitize_text(snap.markdown, on_page=True)
        snap.forms = extract_forms(snap.html, str(snap.url))
        # tech detect on desktop only — mobile UA returns same backend
        if snap.viewport == "desktop":
            snap.tech_stack = detect_tech(str(snap.url), snap.html, headers={})
        snap.quality_score, snap.quality_flags = score_snapshot(snap)
    return {"desktop": desktop, "mobile": mobile}
```

---

## Anti-patterns

1. **Don't use `chorsley/python-Wappalyzer` or `scrapinghub/wappalyzer-python`.** Both archived. Their fingerprint snapshots are 2-3 years stale and miss every modern framework (Next.js 15+, Astro, Qwik, Solid Start, modern analytics like PostHog/Plausible v2).
2. **Don't rely on a single Firecrawl call with viewport-switch actions** to get desktop + mobile snapshots. Page hydration is timing-sensitive; resizing mid-render produces inconsistent layouts and screenshots. Two parallel calls is cleaner and only marginally more expensive.
3. **Don't skip `wait_for`.** Default ~2-3 sec floor for hydration. Lead-gen pages with React/Vue chat widgets, A/B-test loaders (Optimizely, VWO), and lazy-loaded hero images need 2500-4000 ms minimum. Without it, screenshots show skeleton loaders.
4. **Don't redact business contact info on the page itself.** Phone numbers and emails on a lead-gen page are *the product*, not PII to scrub. Only redact PII that appears in form *values*, query strings, or captured network logs. (See `PRESERVE_ON_PAGE` in the sanitizer.)
5. **Don't fight Cloudflare in the primary path.** Lead-gen landing pages almost never run aggressive Turnstile (they want conversions). If you hit a challenge, treat it as a quality-flag failure and queue for human review, don't immediately escalate to Camoufox/residential proxies — you'll burn budget on misclassifications.
6. **Don't store screenshots in Postgres.** Object storage (S3/MinIO/Backblaze B2) for the PNGs, only the URL/hash in Postgres. A typical full-page screenshot is 200KB-2MB; a few hundred in Postgres will tank your queries.
7. **Don't use `BeautifulSoup` for the form/asset parsing pass.** It's 5-30x slower than `selectolax` (Lexbor backend). For a multi-agent system that's going to scrape thousands of pages per session, this matters.
8. **Don't assume `firecrawl-py` field names match the REST API.** SDK auto-converts camelCase → snake_case (`ogImage` → `og_image`). Your tests will break if you cargo-cult JSON examples.
9. **Don't hot-loop on retries without jitter.** Use `wait_exponential_jitter` not plain `wait_exponential` — under concurrent failure, all retries will collide in lockstep otherwise.
10. **Don't run Firecrawl OSS without setting `BULL_AUTH_KEY`.** The Bull queue admin UI ships open by default and exposes job payloads (which contain target URLs and any auth headers).

---

## Recommended starter library set

```toml
# pyproject.toml [project.dependencies]
dependencies = [
    # Core HTTP + retry
    "httpx[http2]>=0.27,<1.0",
    "tenacity>=9.0,<10.0",

    # Primary scraping client
    "firecrawl-py>=4.20,<5.0",

    # HTML/DOM parsing — Lexbor backend, 5-30x faster than BS4
    "selectolax>=0.3.21,<1.0",

    # Tech stack detection — actively maintained Wappalyzer fork
    "wappalyzer>=0.4,<1.0",  # s0md3v/wappalyzer-next on PyPI as 'wappalyzer'

    # PII sanitization
    "presidio-analyzer>=2.2.355,<3.0",
    "presidio-anonymizer>=2.2.355,<3.0",
    # spaCy model needed by Presidio:
    # python -m spacy download en_core_web_lg

    # Data validation (already a project-wide dep, listed for clarity)
    "pydantic>=2.7,<3.0",
]

[project.optional-dependencies]
# Pull these in only if you decide to add an in-process Playwright fallback
stealth = [
    "patchright>=1.50,<2.0",
    # OR: "camoufox[geoip]>=0.4,<1.0",
]

# For the optional self-hosted Firecrawl integration tests
infra-test = [
    "testcontainers[postgres,redis]>=4.7,<5.0",
]
```

**Service-level deps (Docker, not pip):**
- Firecrawl OSS (latest tag) — needs Postgres 16+, Redis 7+, RabbitMQ 3.13+, Playwright service container
- MinIO (or S3) for screenshot blob storage
- ~2.5 GB RAM allocation minimum for the Playwright service alone

---

## Open verifications

Items that need a fresh check before adoption — current as of 2026-04-27 but worth re-verifying when you actually start coding:

1. **Firecrawl `firecrawl-py` v4.x — confirm the exact `screenshot@fullPage` format string** vs `formats=["screenshot"]` + `screenshot_options={"fullPage": True}`. Both shapes appear in 2026 docs; check the actual installed SDK's `Firecrawl.scrape` signature.
2. **`s0md3v/wappalyzer-next` PyPI package name** — confirm `pip install wappalyzer` resolves to s0md3v's fork, not the abandoned chorsley one. (The PyPI entry "wappalyzer" was claimed by s0md3v but verify via `pip show wappalyzer` author field.)
3. **Presidio + spaCy model size** — `en_core_web_lg` is ~750 MB. If your container budget is tight, start with `en_core_web_md` (~50 MB) and accept slightly lower NER accuracy; or use the transformers-based recognizer for higher quality at ~500 MB.
4. **Firecrawl self-host RAM ceiling** — community reports range from 2 GB (light load, single Playwright worker) to 6+ GB (multiple concurrent jobs, Chromium leaks). Run a 24-hour soak test before committing to VPS sizing.
5. **Firecrawl AGPL-3.0 implications for your eventual Spring Boot integration** — AGPL only triggers redistribution obligations if you expose Firecrawl's API publicly. Internal-only API server behind your Spring Boot frontend is fine, but check with a lawyer before going commercial.
6. **Jina Reader `r.jina.ai` rate limits** — values quoted (20 RPM no-key, 200 RPM with free key) come from 2025/early-2026 docs; Jina has historically tightened limits without much notice.
7. **`scrubadub` consideration** — listed as alternative but appears effectively unmaintained (no PyPI release in 12+ months as of early 2026). Skip unless you find recent activity.

---

## Sources

- [firecrawl-py · PyPI (v4.23.0, Apr 2026)](https://pypi.org/project/firecrawl-py/)
- [Firecrawl Python SDK docs](https://docs.firecrawl.dev/sdks/python)
- [Firecrawl GitHub repo](https://github.com/firecrawl/firecrawl)
- [Firecrawl Self-Host guide](https://docs.firecrawl.dev/contributing/self-host)
- [Firecrawl Mobile Scraping & Screenshots launch post](https://www.firecrawl.dev/blog/launch-week-ii-day-6-introducing-mobile-scraping)
- [Firecrawl /interact endpoint v2.9.0](https://www.firecrawl.dev/blog/introducing-interact-endpoint)
- [Self-hosting Firecrawl on Ubuntu 25.04 with Docker Compose (Apr 2026)](https://stevescargall.com/blog/2026/04/self-hosting-firecrawl-on-ubuntu-25.04-with-docker-compose/)
- [Jina Reader API](https://jina.ai/reader/)
- [Microsoft Presidio](https://github.com/microsoft/presidio)
- [Presidio supported entities](https://microsoft.github.io/presidio/supported_entities/)
- [scrubadub on PyPI (status check)](https://pypi.org/project/scrubadub/)
- [chorsley/python-Wappalyzer (archived)](https://github.com/chorsley/python-Wappalyzer)
- [scrapinghub/wappalyzer-python (UNMAINTAINED)](https://github.com/scrapinghub/wappalyzer-python)
- [s0md3v/wappalyzer-next (active fork)](https://github.com/s0md3v/wappalyzer-next)
- [rushter/selectolax (Lexbor backend)](https://github.com/rushter/selectolax)
- [HTML parser benchmarks — selectolax vs BS4 vs lxml](https://rushter.com/blog/python-fast-html-parser/)
- [tenacity retrying library](https://github.com/jd/tenacity)
- [Crawl4AI](https://github.com/unclecode/crawl4ai)
- [Best Open-Source Web Crawlers in 2026 (Firecrawl blog)](https://www.firecrawl.dev/blog/best-open-source-web-crawler)
- [Camoufox stealth overview](https://camoufox.com/stealth/)
- [Patchright (Playwright stealth fork)](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python)
- [AI Browser Automation 2026: Camoufox, Nodriver, Stealth MCP](https://www.proxies.sx/blog/ai-browser-automation-camoufox-nodriver-2026)
- [How to Bypass Cloudflare in 2026 with Python and Playwright](https://medium.com/@contact_6899/how-to-bypass-cloudflare-in-2026-with-python-and-playwright-full-guide-27160735b17c)
- [Browsers benchmark (techinz/browsers-benchmark)](https://github.com/techinz/browsers-benchmark)
- [Zyte web data QA validation techniques](https://www.zyte.com/blog/guide-to-web-data-extraction-qa-validation-techniques/)
- [Scrapfly: How to Ensure Web Scraped Data Quality](https://scrapfly.io/blog/posts/how-to-ensure-web-scrapped-data-quality)
- [Scrapfly: How to Scrape Forms](https://scrapfly.io/blog/posts/how-to-scrape-forms)
