# User-provided Research — Modular AI System for Landing Page Intelligence Snapshot

> Дослідження від Komatozische, надане після завершення наших 10 паралельних research agents.
> Зберігається як reference. Ключові доповнення інтегровані в `00_RESEARCH_SUMMARY.md`.

---

## Суть (за словами автора)

> Канонічним джерелом правди мають бути браузерні артефакти: DOM після виконання JavaScript, скріншоти, layout-координати, network-ланцюжок, інвентар assets, map форм і нормалізовані текстові блоки. Уже поверх цього шару мають працювати LLM/VLM-аналітика, гіпотези для A/B, UX review і multimodal reasoning.

Філософія: **deterministic-first, agentic-second.**

---

## Ключові доповнення до нашого підходу

### 1. Playwright як kernel vs Firecrawl як wrapper — ВАЖЛИВЕ tension

**Наш N1 research сказав:** Firecrawl як primary (швидше, готова markdown + screenshots).
**User research сказав:** Playwright як kernel (більше control, reproducibility), Firecrawl як sidecar/benchmark.

**Resolution для нас:**
- **MVP старт: Firecrawl** (швидко, ready-to-use, обмежує scope) — узгоджено з D-decisions
- **Browser Loader як abstract interface** — `BrowserClient` protocol з implementations: `FirecrawlClient` (default), `PlaywrightClient` (escape hatch коли Firecrawl обмежує)
- **Якщо у Sprint N2/N3 побачимо що Firecrawl недостатньо детальний** для DOM-to-pixel mapping чи network capture — перемикаємось на direct Playwright

### 2. Node-level reproducibility contract — GOLD

Концепція яка значно покращує наш approach:

```json
{
  "node_run_id": "nr_01HXYZ",
  "node_key": "visual_layout_extractor",
  "node_version": "0.3.0",
  "reproducibility": {
    "input_hash": "sha256:...",
    "code_version": "git:9f31b17",
    "tool_versions": {
      "playwright": "1.59.x",
      "firecrawl": "4.23.0",
      "chromium": "..."
    }
  },
  "validation": {
    "passed": true,
    "checks": [
      { "key": "bbox_in_bounds", "passed": true },
      { "key": "node_map_non_empty", "passed": true }
    ]
  }
}
```

**Чому це важливо:** selective re-run, audit trail, debug коли щось зламалось через update tool. Інтегруємо в Sprint 1 як частину DB schema.

### 3. Three-class storage split (вже робимо, але формалізуємо)

| Class | What | Where |
|---|---|---|
| **Immutable artifacts** | raw HTML, screenshots, network logs, DOMSnapshot, AX tree | Object storage (S3/MinIO/local FS) з versioning + sha256 |
| **Normalized entities** | sections, headings, buttons, forms, assets, tech_stack | Postgres JSONB |
| **Embeddings** | semantic chunks для RAG | pgvector |

### 4. Multi-tool content extraction — НЕ покладатись на один інструмент

Замість тільки Firecrawl markdown — combo:
- **Trafilatura** — main text + metadata
- **Readability** — article-like body extraction
- **extruct** — JSON-LD / Open Graph / microdata / RDFa
- **Unstructured** — element-level HTML partitioning для LLM-friendly chunks
- **Playwright locators** — role-based, ARIA snapshots для structural elements

Це suggests: Browser Loader повертає **raw artifacts** → ContentExtractor node прогоняє через всі ці інструменти → один normalized output.

### 5. Asset extractor — використовувати browser APIs, НЕ тільки HTML

```javascript
// Через Playwright evaluate() — критично для responsive images
img.currentSrc          // фактичний URL вибраного responsive image
img.naturalWidth        // intrinsic dimensions
img.naturalHeight
getComputedStyle(el).backgroundImage  // CSS background images
@font-face rules        // fonts
preload links
```

Плюс **probe-image-size** для cheap remote dimension checks без повного завантаження.

### 6. Form extractor — network capture обов'язковий

> submit endpoint може жити не лише в `<form action>`, а й у submit/image input через `formAction`; видимий submit control може бути не в DOM-піддереві форми; частина lead-gen форм взагалі submit'иться JS/xhr'ом

Тому Form Extractor повинен:
- Читати form.elements + action + formAction
- Capture network events на submit (як визначити endpoint якщо JS-submitted)
- Track multi-step state machine (для quiz funnels)

### 7. Tech detection — merge engine, НЕ один детектор

Comin: Wappalyzer Next + wappalyzergo + ZAP add-on + custom rules:
- Script URLs
- Response headers
- JS globals
- Cookies
- DOM markers
- Network domains

Confidence merger consolidує signals з усіх джерел.

### 8. Two-mode vision (для N2 Semantic Role Mapping)

- **Screen-level:** full-page screenshot → section-level observations
- **Asset-level:** crop hero, logo, product shot, testimonials, pricing cards via DOM bbox map → focused VLM analysis

OSS on-prem candidates коли треба: **Qwen2.5-VL** (multimodal reasoning + OCR), **Molmo2** (open VLM + pointing/grounding), **LLaVA-NeXT** (general baseline).

### 9. Quality validation per node (concrete checks)

Не тільки overall snapshot quality_score. Per-node:
- `bbox_in_bounds` — bbox не виходять за screenshot
- `node_map_non_empty` — DOM-to-pixel map має entries
- `dom_form_count == layout_form_count` — DOM extractor і layout map узгоджуються
- `expected_network_evidence_present` — assets з DOM мають network responses
- `tech_detector_consensus` — multiple detectors agree
- `idempotent_rerun` — repeat job_id дає той самий input_hash з прийнятною дельтою

### 10. Two-plane production architecture (для пізніше)

User research recommends для production:
- **Crawler plane** — Node/TypeScript з Playwright + Crawlee
- **Analysis plane** — Python (Pydantic, AI, data tooling)
- **Orchestration** — Temporal для durable retries
- **Observability** — OpenTelemetry + OpenLineage

**Для нас MVP:** Python-only моноліт OK. Plane separation — Phase 2 коли scale потребує.

### 11. Tools to skip / deprioritize у MVP

User дослідження підтверджує:
- Не Airflow / Dagster / Temporal у MVP
- Не окремий vector cluster (pgvector OK)
- Не browser-use як core (тільки як agentic fallback)
- Не Firecrawl як ядро коли треба deterministic snapshot (для нас trade-off OK на старті)
- Не повний CV parser до того як DOM+layout map працює

---

## Що нічого не змінює

- LLM gateway (N10) — наш approach singular OpenRouter без LiteLLM узгоджується
- Knowledge System (N3) — pgvector + hybrid search підтверджується
- Multi-agent (N5) — LangGraph + Pydantic AI — узгоджується
- Decision Engine (N6) — наша 30-line формула + explainable breakdown — підтверджується
- Cost discipline — узгоджується

---

## Action items на основі цієї research

### Інтегрувати у Sprint 1 (N10 LLM Gateway)
- Нічого спеціального, узгоджено

### Інтегрувати у Sprint N1 (Browser & Snapshot)
- Browser Loader як **abstract interface** з Firecrawl як default impl + planned Playwright impl
- **Three-class storage** explicit у DB schema
- **Node reproducibility contract** як частина snapshot manifest
- **Multi-tool content extraction** — не покладатись тільки на Firecrawl markdown
- **Per-node quality checks** — список concrete checks

### Інтегрувати у Sprint N2 (Semantic Role Mapping)
- **Two-mode vision** (screen-level + asset-level)
- Лишити OSS VLM (Qwen2.5-VL/Molmo2/LLaVA-NeXT) як future option якщо OpenRouter cost issue

### Запам'ятати для production phase
- Two-plane architecture (Crawler plane Node/TS + Analysis plane Python)
- Temporal для durable orchestration
- OpenTelemetry + OpenLineage

---

## Citation
Всі рекомендації залишаються в силі. Цей файл — пам'ятка для integration у sprint planning.
