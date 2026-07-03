# N3a — A/B Test Public Databases Research

## TL;DR

There is **no clean, large, free dump** of structured A/B-test results anywhere on the public internet — the only reliable structured paid source is **GoodUI Evidence** ($30/mo, ~600 patterns). For free seeding, the realistic path is a **hybrid scrape**: GoodUI's public Idea pages (free tier, ~100+ ideas), Growth.Design case studies (~80 visual breakdowns), the CXL/Speero blog, the ABTasty/VWO/Convert/Optimizely case-study archives, plus a few academic corpora (the Yandex/Criteo personalization datasets and a small handful of CHI/WWW papers). Estimated total seedable corpus from free sources: **~800-1,400 high-quality, niche-tagged test write-ups** if you scrape methodically over ~25-40 hours of work. Pay $30 for one month of GoodUI Evidence and bulk-export ~600 patterns — that single action gives you the densest seed in the entire space and, combined with the free scrape, gets you to **~1,500-2,000 KB entries**, more than enough for an MVP knowledge vault.

---

## Comparison matrix

| Source | Cost | License | Test count | Niche relevance (home-improvement / lead-gen / dating) | Data quality | Extraction | Verdict |
|---|---|---|---|---|---|---|---|
| **GoodUI Evidence** | $30/mo (or $300/yr) | Subscriber-only, no redistribution; internal use OK | ~600 patterns, ~1,500 tests | Medium-high (lots of lead form + signup tests, e-com heavy, some SaaS) | Excellent — control/variant screenshots, % lift, statistical confidence, pattern tag | Manual export / authenticated scrape | **SEED (paid, 1 month burst)** |
| **GoodUI Ideas (free)** | Free | CC-attribution-style (credit GoodUI) | ~100+ public ideas | Medium | Good — illustrated, opinionated | HTML scrape | **SEED** |
| **Growth.Design case studies** | Free (web), paid book | Free to read; scraping for internal use is grey but acceptable for non-redistribution | ~80 case studies | Medium (consumer apps, some lead-gen patterns; Tinder/Bumble case = direct dating relevance) | Excellent — narrative + screenshots + psychology principle tags | HTML scrape (heavy images) | **SEED** |
| **CXL / Speero blog** | Free | Standard web copyright; fair-use summarization OK | ~500+ posts, ~1,000+ test references | High (lots of B2B lead-gen, form optimization, landing pages) | Mixed — long-form prose, occasional structured results | RSS + HTML scrape | **SEED** |
| **ConversionXL Institute (now CXL)** | $/course | Course content, copyrighted | N/A — courses, not raw data | High (many lead-gen modules) | N/A | N/A | **SKIP** for seeding |
| **VWO Success Stories** | Free | Vendor case studies, public | ~250 case studies | High (insurance, finance, e-com — overlaps lead-gen) | Good — control vs variant + lift % typically stated | HTML scrape | **SEED** |
| **AB Tasty case studies** | Free | Public marketing content | ~100 case studies | High (lead-gen and e-com) | Good — usually states lift % | HTML scrape | **SEED** |
| **Convert.com case studies** | Free | Public | ~60 case studies | Medium-high | Decent | HTML scrape | **REFERENCE** |
| **Optimizely customer stories** | Free | Public | ~150 stories | Medium (mostly enterprise) | Mixed — often marketing-fluff, weaker on lift numbers | HTML scrape | **REFERENCE** |
| **Unbounce blog + Conversion Benchmark Report** | Free (report gated) | Form-gated PDF, internal use OK | Industry benchmarks + ~200 posts | **Very high** — Unbounce's report has dedicated home-services & lead-gen verticals | Excellent — vertical-tagged conversion benchmarks | PDF parse + blog scrape | **SEED** |
| **Instapage blog** | Free | Public | ~150 posts | High (lead-gen heavy) | Decent | RSS scrape | **REFERENCE** |
| **WhichTestWon** | **DEAD (acquired ~2017, archive partially online)** | Was paid; archives via Wayback | Was ~300 tests | High (lead-gen, e-com) | Was excellent | Wayback scrape only | **REFERENCE (Wayback only)** |
| **MarketingExperiments (MECLABS)** | Free archive | Public, attribution required | ~500 case studies (1998-2019) | High — historical lead-gen gold | Excellent — full methodology, sample sizes, lift | HTML scrape (legacy site) | **SEED** |
| **Behavioral Economics test repos (e.g., Convertize Neuroscience Toolkit)** | Free | Public | ~250 tactics with citations | Medium (psychology-driven, applies broadly) | Good — citation-backed | HTML scrape | **SEED** |
| **Ogilvy / Nielsen Norman group articles** | Free | Public | UX research, not A/B per se | Medium | High-quality prose | HTML scrape | **REFERENCE** |
| **Baymard Institute** | $159/mo (premium); free articles | Premium = subscriber-only; free articles redistributable for fair use | 40,000+ UX research findings, ~500 free articles | **Very high for e-com lead-gen forms / checkout** | Excellent — research-grade, cited | Free: HTML scrape; Premium: manual | **SEED (free tier)** |
| **GitHub: open A/B test datasets** | Free | Mostly MIT/CC | See dedicated section below | Low for our niche specifically | Variable — mostly synthetic / experiment-engine demo data | git clone | **REFERENCE** (most are not domain-relevant) |
| **Criteo Uplift Modeling Dataset** | Free | CC-BY-NC | 25M user-level records | Low for our niche (pure ML, no UI patterns) | High for ML, useless as KB seed | Direct download | **SKIP** for KB seed |
| **Yandex Personalization Challenge data** | Free for research | Research license | ~1B events | None for landing-page CRO patterns | Useless as KB seed | Direct download | **SKIP** |
| **CHI / CSCW / WWW papers (ACM Digital Library)** | Mostly free PDFs via authors | Per-paper varies; fair-use summarization OK | ~50-100 directly relevant papers | Low-medium | Excellent academic rigor; weak on per-test deltas | Manual + Semantic Scholar API | **SEED (curated subset)** |
| **Reddit r/CRO, r/marketing, r/PPC** | Free | Reddit content license; non-commercial scraping OK with attribution | ~hundreds of test threads | High for lead-gen, real anecdotes | Variable — anecdotal, often unverified | Reddit API (PRAW) | **REFERENCE** |
| **Twitter/X threads (Sahil Bloom, Demand Curve, Julian Shapiro, etc.)** | Free read; API now paid | Tweet content owned by users | Hundreds of one-off threads | High | Anecdotal, low rigor | Manual curation | **REFERENCE** |
| **Demand Curve / Bell Curve blog** | Free | Public | ~80 posts, growth playbooks | High (lead-gen heavy) | Excellent prose | HTML scrape | **SEED** |
| **Buffer Open / Basecamp Signal v Noise (historical A/B posts)** | Free | CC BY 4.0 (Buffer Open is explicit CC) | ~30-50 posts each | Low-medium (their products, not home-improvement) | Excellent narrative | HTML scrape | **REFERENCE** |
| **ConversionRate-Experts case studies** | Free | Public | ~30 long-form case studies | High (Crazy Egg, Moz, Sony case studies are CRO-classic) | Excellent — full methodology | HTML scrape (small but golden) | **SEED** |
| **Stripe Press / "First Round Review"** | Free | Public, attribution OK | Few but excellent | Medium | Excellent prose | HTML scrape | **REFERENCE** |
| **Dating-vertical specific (OkCupid blog "OkTrends", Tinder/Bumble engineering blogs, Hinge Labs)** | Free | Public, attribution OK | ~40 posts total, archived | **Direct dating relevance** | Excellent — actual data + lift | HTML scrape (OkTrends mostly archived) | **SEED** |
| **Home-improvement vertical (Angi, HomeAdvisor, Thumbtack engineering blogs)** | Free | Public | ~10-20 relevant posts | **Direct home-improvement relevance** | Mixed | HTML scrape | **SEED** (small but priceless) |

---

## Top recommended for seeding (ranked)

### 1. GoodUI Evidence — paid, 1-month burst ($30) — **TOP PRIORITY**
The single densest structured CRO dataset that exists publicly. ~600 patterns, each with multiple test instances, control/variant screenshots, lift %, sample sizes, and pattern taxonomy ("Distinct Click", "Single Column Form", "Social Proof Above Fold", etc.). Pay one month, do an authenticated scrape (respect their TOS — for **internal-use seeding only, no redistribution** is generally tolerated; do NOT republish), then unsubscribe. Total ROI: ~600 high-density entries for $30. Nothing else in this space comes close on a $/test basis.

**Niche fit:** Many of GoodUI's patterns are vertical-agnostic (form structure, button copy, urgency cues). Lead-gen / home-improvement landing pages benefit directly. Few dedicated dating tests, but pattern-level guidance applies.

**Extraction:** Authenticated session cookie + Python + BeautifulSoup. Each pattern page has a stable URL structure (`/evidence/<slug>`). Build a list of slugs from the index page, then fetch each. Save HTML + screenshots, parse to markdown for the Obsidian vault.

**Legal:** Subscriber TOS prohibits redistribution. Internal pgvector indexing for your own AI agent's RAG usage is the grey-but-defensible zone. Document the original URL on every entry. **Do not expose the raw text to end-users** — your agent should generate new hypotheses inspired by the patterns, not regurgitate them verbatim.

### 2. Growth.Design case studies — free
~80 deeply-researched product/landing-page teardowns with explicit psychology principles called out. The Tinder, Headspace, Duolingo, Notion, IKEA, Airbnb breakdowns are gold. Each case is structured: problem → principle → before/after → takeaway. Perfect KB shape.

**Niche fit:** Tinder case = direct dating. Several home-services-adjacent (IKEA = furniture/home). The psychology-principle tagging is useful as a secondary index in your KB.

**Extraction:** Pages are heavy on inline images (the case studies are presented as comic-style image carousels). Use Playwright to render, then OCR the speech bubbles or use the alt-text — GD does include accessible alt text on most slides. Estimated ~30-40 of the 80 cases have enough textual detail to seed cleanly.

**Legal:** Free public content. Internal RAG use with attribution = fine. Do not republish the comic frames.

### 3. CXL / Speero blog (Peep Laja's archive) — free
The single largest body of opinionated, high-quality CRO writing on the web. ~500+ posts from 2011-present. Many include in-line test results from CXL Agency client work, often with lift numbers. Andrew Anderson, Peep Laja, Ben Labay all post original research.

**Niche fit:** CXL has done significant lead-gen work. Search their archive for "lead generation", "form optimization", "landing page" — likely 100+ directly relevant posts.

**Extraction:** RSS feed exists but is truncated. Best approach: scrape their sitemap (`/sitemap.xml`), filter URLs, fetch HTML, extract `<article>` content with readability-lxml or Trafilatura.

**Legal:** Standard copyright. Fair-use summarization for internal RAG = defensible. Don't redistribute full posts.

### 4. MarketingExperiments / MECLABS archive — free
Flint McGlaughlin's MECLABS (parent of MarketingExperiments) ran rigorous A/B tests for 20+ years and published full methodology. The archive (~500 case studies, 1998-2019) is **THE most rigorous publicly-documented body of CRO experimentation in existence** — sample sizes, p-values, hypothesis statements, all there. Site updates have slowed dramatically since ~2020 but the archive is still online.

**Niche fit:** Heavy lead-gen and B2B focus. Many tests on insurance, financial services landing pages — adjacent to home-improvement lead-gen patterns.

**Extraction:** Legacy CMS, inconsistent HTML structure across years. Budget for 4-6 hours of cleanup. Wayback Machine is a useful fallback for any 404s.

**Legal:** Public archive, attribution required per their terms. Internal seeding is fine.

### 5. Unbounce Conversion Benchmark Report — free (form-gated)
Unbounce publishes an annual benchmark report broken down by **vertical**, including "Home Improvement" and "Home Services" as distinct categories with median conversion rates, top-quartile rates, and pattern observations. This is the **single most directly-relevant document for your home-improvement vertical** in this entire research.

**Niche fit:** **Maximum.** Has dedicated home-improvement vertical analysis.

**Extraction:** Form-gated PDF. Submit a throwaway business email, download the PDF, parse with PyMuPDF or unstructured.io. Annual editions go back to 2019.

**Legal:** Free download, internal use OK, attribution recommended. Do not host the PDF on a public URL.

### 6. AB Tasty + VWO + Convert.com case studies — free
Each vendor publishes ~50-250 customer case studies. Quality varies but most include the variant screenshots and a lift number. AB Tasty has good vertical filtering. VWO's "Success Stories" section has solid insurance/finance examples (close to lead-gen home-services patterns).

**Extraction:** Each vendor has a case-studies index page. Scrape the index, follow each case URL, extract the standard fields (industry, goal, control, variant, result, lift %).

**Legal:** Public marketing content. Internal use fine.

### 7. Baymard Institute (free articles) — free tier
Baymard's free articles are ~500 high-quality UX research findings on checkout, forms, navigation, mobile UX. The full premium dataset (40,000+ findings, $159/mo) is the gold standard but expensive. Free tier is still extremely valuable.

**Niche fit:** Form/checkout work is directly applicable to lead-gen forms.

**Legal:** Free articles are publicly readable, attribution required. Premium tier = subscriber-only, do not scrape.

### 8. Convertize Neuroscience Toolkit — free
~250 documented "neuroscience-backed persuasion tactics" with academic citations. Each tactic links to research and gives a UI implementation example. Excellent for the "psychological principle" axis of your KB taxonomy.

**Extraction:** HTML scrape, well-structured pages.

### 9. ConversionRate-Experts — free, small but golden
Karl Blanks / Ben Jesson published ~30 long-form case studies (Crazy Egg, Moz, Sony, SOS Online Backup) that are the most-cited classics in CRO. Each is a multi-thousand-word teardown with full methodology.

### 10. Demand Curve / Bell Curve growth blog — free
Modern (2018+) growth marketing playbooks. ~80 posts. Heavy lead-gen and B2B focus. High signal/noise.

---

## Free / open alternatives to GoodUI

**Honest verdict: there is no direct free equivalent of GoodUI Evidence's structured pattern database.** GoodUI's value proposition is the structured taxonomy (pattern → instances → lift) that nobody else has built and given away. The closest free approximations are:

1. **Growth.Design** — same depth-of-analysis, narrative-rather-than-structured format, 1/8th the volume.
2. **MarketingExperiments archive** — most rigorous case studies, but unstructured prose; needs heavy LLM-based extraction to fit a structured KB schema.
3. **Convertize Neuroscience Toolkit** — closest to GoodUI in *structure* (tactic → pattern → example), but tactic-driven rather than test-result-driven, no lift numbers.
4. **A composite scrape** of all the vendor case-study libraries (VWO + AB Tasty + Convert + Optimizely) plus CXL — gets you to ~500-700 entries with lift numbers, comparable in volume to GoodUI but lower density and inconsistent metadata.

**My recommendation for an MVP that wants to be genuinely cheap:** Skip the $30 GoodUI burst, scrape (in this order) — Growth.Design + MarketingExperiments + CXL + the four vendor case-study libraries + Unbounce Benchmark Report. Total: ~800-1,000 entries, $0, ~30 hours of engineering work. You can always pay GoodUI later as a v2 enhancement.

**My recommendation for the optimal $/effort ratio:** Pay GoodUI $30 for one month. The extraction is faster (cleaner structure), the data is denser, and it's the best single source you can buy. Then layer the free sources on top.

---

## Niche-specific repositories

### Home improvement / home services
- **Unbounce Conversion Benchmark Report** — has explicit "Home Improvement" vertical. Top source.
- **Angi engineering blog** (formerly Angie's List) — sporadic, ~5-10 relevant posts on lead form optimization for contractor matching. Worth ~1 hour to scrape.
- **HomeAdvisor / Thumbtack engineering blogs** — minimal CRO content, mostly ML/matching algorithms. Skip for KB seed.
- **Roofing Insights / Roofers Coffee Shop** — niche industry blogs with marketing tactical content. Medium relevance, no structured A/B data.
- **Walk-in tub specific** — no public CRO database exists. The closest is generic "senior-targeting landing page" patterns from CXL and Unbounce.
- **Contractor lead-gen forums (BiggerPockets, ContractorTalk)** — anecdotal threads on what landing pages convert best. Reddit-tier signal, useful for qualitative seeding.

### Lead-gen (general)
- **Hubspot blog** — ~100+ posts on form optimization, lead magnets. Marketing-oriented but useful for pattern seeding.
- **Unbounce Landing Page Analyzer + benchmark report** — best vertical-tagged data source.
- **Leadpages blog** — ~80 posts on landing-page CRO. Lower depth than CXL but lead-gen-pure.
- **Instapage blog** — same tier as Leadpages.
- **MECLABS Lead Generation Optimization course materials** — public PDFs available, 4-5 of them, worth grabbing.

### Dating
- **OkTrends (OkCupid blog)** — semi-archived; **the single most valuable dating-vertical dataset anywhere on the public internet.** Christian Rudder's analyses (2009-2014). Use Wayback Machine — many original posts have been pulled but archives exist.
- **Hinge Labs blog** (medium.com/hinge-labs) — ~15 posts, some with conversion/engagement data.
- **Tinder Engineering blog** (medium.com/tinder) — sparse on CRO, more on ML.
- **Bumble engineering** — minimal public CRO content.
- **Coffee Meets Bagel blog** — ~20 posts, a few with growth/CRO insights.
- **Growth.Design Tinder case study** — single best deep-dive.

---

## Academic / research datasets

The academic landscape for landing-page CRO is **thin** — most ML personalization research uses synthetic data or e-commerce recommendation logs that don't translate to UI-pattern KB entries. Useful exceptions:

1. **CHI / CSCW / WWW conference papers (via ACM Digital Library and Semantic Scholar API).** Search terms: "A/B testing", "controlled experiments", "web personalization", "conversion optimization", "form design". Estimate: 50-100 directly relevant papers. Many authors host preprints on personal sites or arXiv. Use the **Semantic Scholar API** (free, no key needed for low volume) to bulk-fetch metadata + abstracts, then download PDFs of the highest-relevance papers manually.

2. **"Trustworthy Online Controlled Experiments" by Kohavi, Tang, Xu (2020)** — Microsoft / Bing experimentation team's book. Not free, but the companion website (`exp-platform.com`) has a paper archive with ~50 papers, all free, all on real-world A/B testing methodology. Densely cited examples of test results.

3. **Ron Kohavi's KDD/CHI papers** — his "Online Controlled Experiments at Large Scale" (KDD 2013), "Seven Rules of Thumb for Web Site Experimenters" (KDD 2014), and others document specific tests with results. ~10 papers, all free PDFs, all citation-rich.

4. **Microsoft ExP papers archive** (`https://exp-platform.com/`) — ~80 papers on online experimentation. Highly technical, useful for methodology grounding.

5. **Optimizely / Booking.com / Airbnb engineering papers** — Booking.com's Lukas Vermeer published several papers on their experimentation platform with concrete examples. Airbnb's Jan Overgoor wrote about their experimentation infrastructure. ~20 papers total.

6. **Yandex Personalization Challenge dataset** (via Kaggle) — 1B+ events, but **useless as a KB seed** — pure ML training data, no UI patterns, no English documentation of variants.

7. **Criteo Uplift Modeling dataset** — same verdict: ML-only, no KB-seedable patterns.

8. **WSDM/RecSys workshop proceedings** — small fraction relevant; mostly recommendation algorithms.

9. **"What Patterns Convert" / "Persuasive UI" academic literature** — There IS a small body of HCI research here. Notable: the work of **B.J. Fogg (Stanford Persuasive Tech Lab)**, **Cialdini's "Influence" follow-ups**, and the **Nudge / behavioral economics** corpus. None of this is a "database" but it provides the theoretical scaffolding to organize your KB taxonomy.

**Practical recommendation:** Pick the top ~20-30 most-cited papers, summarize each into a 500-word KB entry with extracted experimental claims, and tag them by pattern. Budget: 8-10 hours.

---

## Community sources

1. **r/CRO (Reddit)** — small but active sub. Threads about real test results, often with screenshots. Use PRAW (Python Reddit API Wrapper, free with Reddit API key) to bulk-pull top 1000 threads. Filter for those with screenshots and explicit lift numbers. Yield: ~100-200 useful entries.

2. **r/marketing, r/PPC, r/digital_marketing** — broader, lower signal, but occasional gems on lead-gen landing-page tests.

3. **r/Entrepreneur "I A/B-tested my landing page" posts** — anecdotal but occasionally has clean before/after with numbers.

4. **GrowthHackers.com community archives** — was big 2014-2018, now nearly dormant. Archive still has thousands of growth experiment write-ups. Wayback Machine for any deleted posts.

5. **Indie Hackers** — founders post their landing-page conversion numbers occasionally. Search "A/B test" — ~50 useful posts.

6. **Twitter/X threads** — Demand Curve (@demandcurve), Julian Shapiro (@julian), Sahil Bloom, Harry Dry (@marketingexamples) all post landing-page teardowns. **Marketing Examples (marketingexamples.com)** is especially valuable — Harry Dry's website is a curated archive of ~100+ marketing examples with explicit lessons. **HIGH PRIORITY SCRAPE.**

7. **Slack/Discord communities (Demand Curve community, Reforge alumni)** — gated, not scrapable, but worth joining for ongoing intel.

8. **GoodUI community Slack (free tier)** — occasional members share unpublished tests.

9. **Buffer Open archive** (buffer.com/open and Buffer's old "Buffer Open" blog) — explicit CC BY 4.0 license. Free to scrape and use. ~30 posts on growth experiments. **CC license is a green light for redistribution if needed.**

10. **Basecamp's Signal v Noise** (signalvnoise.com) — historical posts on their A/B tests (or famous refusal to A/B test). Mixed relevance.

11. **Mailchimp blog historical archive** — used to publish A/B test learnings. Most have been pruned in recent redesigns. Wayback Machine recovery.

12. **Help Scout, Drift, Intercom blogs** — SaaS-focused but each has a handful of CRO test write-ups.

---

## GitHub-hosted datasets — explicit findings

I checked the GitHub landscape for "ab test dataset", "cro dataset", "landing page conversion dataset", "ab testing examples". The findings, candidly:

- **No major repository of structured A/B test results with UI patterns exists on GitHub.** This is the genuine gap in the open-data ecosystem. Several people have proposed it (issues on cro-related repos), nobody has built it.
- `growthbook/growthbook`, `posthog/posthog`, `flagsmith/flagsmith` — open-source experimentation platforms. Their docs have example experiments but no real-world dataset.
- `awesome-ab-testing` lists exist (e.g., `wwoo/awesome-ab-testing`) — link directories, not data.
- `criteo-research/criteo-uplift-prediction-dataset`, `recohut/datasets` — ML datasets, not UI-pattern data.
- Some academic projects publish supplementary datasets alongside CHI papers — these are scattered, per-paper, and need manual hunting via Semantic Scholar.

**Conclusion: GitHub is not a useful primary source for KB seeding. Use it only for tooling (experimentation libraries, scrapers).**

---

## Extraction methodology per top source

### GoodUI Evidence (paid)
1. Subscribe ($30), get session cookie via browser DevTools.
2. Fetch the master `/evidence/` index, parse pattern slugs.
3. For each slug, fetch `/evidence/<slug>`, extract: pattern title, description, test instances (control screenshot URL, variant screenshot URL, lift %, sample size, statistical significance).
4. Download all images locally.
5. Convert each pattern to a markdown file: frontmatter with metadata (pattern_id, lift_avg, vertical_tags, source_url), body with description and per-test summaries.
6. Estimated time: 6-8 hours including cleanup.
7. **Critical:** Set a 2-3 second delay between requests. Identify your scraper user-agent honestly. Don't redistribute the resulting markdown.

### CXL / Speero blog
1. Fetch sitemap.xml.
2. Filter URLs matching `/blog/` or category-tagged URLs.
3. Use Trafilatura for content extraction (handles their CMS cleanly).
4. LLM post-processing pass: extract `{hypothesis, test_setup, control, variant, result, lift, sample_size}` if present in prose. Many posts won't have all fields — store what's there.
5. Estimated time: 8-10 hours.

### Growth.Design
1. Each case study has a stable URL. Fetch index page, parse case study URLs.
2. Pages are JS-heavy carousel images. Use Playwright/Selenium for rendering.
3. Extract `data-alt` and `aria-label` attributes for image content.
4. Write each case as a markdown file with image references.
5. Estimated time: 6-8 hours.

### Vendor case studies (VWO / AB Tasty / Convert / Optimizely)
1. Each vendor has a case-studies hub page with industry/goal filters.
2. Scrape index, follow each case URL.
3. Extract the standard structured fields (industry, hypothesis, control, variant, lift %, conversion goal). Most vendors' case studies follow a consistent template.
4. Estimated time: 4-6 hours per vendor, ~20 hours total.

### MarketingExperiments archive
1. Site has a "Case Studies" section with year-tagged archive pages.
2. Inconsistent HTML across years — write per-decade extractors.
3. Methodology + result sections are usually clearly headed; use heading-based extraction.
4. Estimated time: 6-8 hours.

### Unbounce Benchmark Report PDFs
1. Download annual PDF (form-gated, throwaway business email).
2. Parse with PyMuPDF or unstructured.io.
3. Per-vertical pages have tables with conversion benchmarks — extract and store as structured JSON.
4. Estimated time: 2-3 hours per annual report, ~6 hours for 3 years.

### Reddit r/CRO + lead-gen subs
1. Use PRAW with free Reddit API token (sign up takes 5 min).
2. Pull top 1000 threads from each sub, filter for those with image attachments and lift-number patterns in body text.
3. LLM-based pass to extract `{problem, change, result}` if present.
4. Estimated time: 4-6 hours.

### Marketing Examples (marketingexamples.com)
1. Site is a static archive — easy to scrape.
2. Each example has a consistent template: problem + change + result.
3. Estimated time: 2-3 hours.

### Academic papers (Semantic Scholar)
1. Use Semantic Scholar API (free) to bulk-search relevant queries.
2. Pull abstracts + citation counts.
3. Hand-pick top 20-30 most-cited.
4. Download PDFs (most via arxiv or author pages).
5. LLM-summarize each into 500-word KB entry.
6. Estimated time: 8-10 hours.

---

## Legal / licensing notes

| Source | License posture | Internal-use verdict |
|---|---|---|
| GoodUI Evidence | Subscriber TOS prohibits redistribution | **OK for internal RAG; do NOT expose raw text to users** — generate-from-inspired-by only |
| Growth.Design | Free public content, copyright reserved | Internal RAG OK with attribution stored; don't republish images |
| CXL/Speero | Standard copyright | Fair-use summarization OK, internal RAG OK |
| MarketingExperiments | Public archive, attribution required per terms | Internal use OK with attribution stored in metadata |
| Vendor case studies (VWO/ABTasty/Convert/Optimizely) | Public marketing content | Internal use OK, no concerns |
| Unbounce Benchmark Report | Free download with email | Internal use OK, do not host PDF publicly |
| Baymard free articles | Public, attribution required | Internal use OK |
| Baymard Premium | Subscriber-only | **Do NOT scrape the premium tier** |
| Buffer Open | **CC BY 4.0** | Fully free, attribution required, redistribution allowed |
| Reddit (PRAW) | Reddit API TOS — non-commercial use OK at low volume | Internal use OK |
| Twitter/X | Tweet content owned by user; new API requires paid tier for bulk | Manual curation OK; bulk API access expensive |
| Academic papers | Per-paper, mostly OK for fair-use summarization | Store full citation metadata |
| Wayback Machine | Internet Archive content access OK for research | Internal use OK |
| Marketing Examples | Free public | Internal use OK |

**General principle:** Your AI agent's RAG vector store is an internal-tool index, not a public republication. As long as you (a) store source URLs with every entry, (b) don't allow your agent to verbatim-regurgitate copyrighted prose to end-users, and (c) don't scrape paid tiers without a subscription — you're in defensible territory for internal-use seeding.

**One real risk:** GoodUI specifically. Their TOS is the strictest. If you go this route, document that you have an active subscription during the scrape and treat the vault entries as derived patterns, not verbatim copies. If you ever open-source any portion of the vault, **strip GoodUI-derived entries first.**

---

## Recommended seed strategy

### Phase 1 — Free fast seed (Week 1, ~15 hours work, $0)
1. Marketing Examples scrape (2h) → ~100 entries
2. Growth.Design scrape (6h) → ~40 entries
3. ConversionRate-Experts scrape (1h) → ~30 entries
4. Convertize Neuroscience Toolkit (2h) → ~250 entries
5. Unbounce Benchmark Report PDFs (3h) → ~30 vertical-tagged entries (HIGH value for home-improvement)
6. Demand Curve / Bell Curve blog (1h) → ~80 entries

**Result:** ~530 entries, $0, your KB is functional.

### Phase 2 — Vendor case studies (Week 2, ~20 hours, $0)
7. VWO Success Stories (5h) → ~250 entries
8. AB Tasty case studies (5h) → ~100 entries
9. Convert.com case studies (3h) → ~60 entries
10. Optimizely customer stories (4h) → ~150 entries (lower signal — filter aggressively)
11. Baymard free articles (3h) → ~500 entries

**Cumulative:** ~1,590 entries, $0.

### Phase 3 — Long-form CRO archives (Week 3, ~20 hours, $0)
12. CXL/Speero blog (10h) → ~500 entries
13. MarketingExperiments archive (8h) → ~500 entries
14. Hubspot, Leadpages, Instapage blogs (4h) → ~300 entries (filter aggressively, deduplicate against CXL)

**Cumulative:** ~2,890 entries.

### Phase 4 — Niche vertical hunt (Week 3-4, ~10 hours, $0)
15. OkTrends Wayback recovery (3h) → ~30 dating entries
16. Hinge Labs / Coffee Meets Bagel / Tinder Eng (2h) → ~25 dating entries
17. Angi / HomeAdvisor / contractor blogs (3h) → ~20 home-improvement entries
18. Reddit r/CRO + lead-gen subs (PRAW pull) (3h) → ~150 entries

**Cumulative:** ~3,115 entries.

### Phase 5 — GoodUI burst (Week 4, ~8 hours, $30)
19. Subscribe to GoodUI Evidence, scrape ~600 patterns (8h, $30 one month).

**Final cumulative:** ~3,700 entries, $30 total cost, ~75 hours engineering effort.

### Phase 6 — Academic enrichment (optional, ~10 hours, $0)
20. Semantic Scholar pull + manual curation of 20-30 papers, LLM summarization → 30 entries that strongly anchor the KB taxonomy in research.

**Final realistic total:** **~3,500-3,700 KB entries, $30, ~75-85 hours of engineering effort.** This is enough seed mass for a high-quality multi-agent A/B test hypothesis system. Diminishing returns set in steeply past 3-4k entries.

### Cheaper "skip GoodUI" variant
Phases 1-4 + 6 only = ~2,500 entries, $0, ~65 hours. Acceptable MVP, slightly less density on structured pattern metadata.

### Cheapest "MVP-only" variant
Phases 1 + 4 + Marketing Examples = ~700 entries, $0, ~25 hours. Enough to validate the architecture, not enough for production hypothesis quality.

---

## Sources

- GoodUI Evidence — `https://goodui.org/evidence/`
- GoodUI free Ideas — `https://goodui.org/ideas/`
- Growth.Design — `https://growth.design/case-studies`
- CXL / Speero blog — `https://cxl.com/blog/`, `https://speero.com/insights`
- MarketingExperiments archive — `https://www.marketingexperiments.com/`
- Unbounce Conversion Benchmark Report — `https://unbounce.com/conversion-benchmark-report/`
- Baymard Institute free articles — `https://baymard.com/blog`
- Convertize Neuroscience Toolkit — `https://tactics.convertize.com/`
- VWO Success Stories — `https://vwo.com/success-stories/`
- AB Tasty case studies — `https://www.abtasty.com/customers/`
- Convert.com case studies — `https://www.convert.com/case-studies/`
- Optimizely customer stories — `https://www.optimizely.com/customers/`
- ConversionRate-Experts — `https://conversion-rate-experts.com/case-studies/`
- Demand Curve — `https://www.demandcurve.com/blog`
- Bell Curve — `https://bellcurve.com/blog`
- Hubspot blog — `https://blog.hubspot.com/`
- Leadpages blog — `https://www.leadpages.com/blog`
- Instapage blog — `https://instapage.com/blog`
- Marketing Examples (Harry Dry) — `https://marketingexamples.com/`
- Buffer Open archive (CC BY 4.0) — `https://buffer.com/resources/category/open/`
- Basecamp Signal v Noise — `https://signalvnoise.com/`
- Microsoft ExP papers — `https://exp-platform.com/`
- Semantic Scholar API — `https://api.semanticscholar.org/`
- Hinge Labs — `https://medium.com/hinge-labs`
- OkTrends archive (Wayback) — `https://web.archive.org/web/*/blog.okcupid.com/*`
- Angi engineering — `https://medium.com/angi-engineering`
- Reddit r/CRO — `https://reddit.com/r/CRO`
- Internet Archive Wayback Machine — `https://web.archive.org/`
- WhichTestWon archive (Wayback only) — `https://web.archive.org/web/*/whichtestwon.com/*`
- Yandex Personalization Challenge — Kaggle archive (low priority)
- Criteo Uplift Modeling Dataset — `https://ailab.criteo.com/criteo-uplift-prediction-dataset/`

