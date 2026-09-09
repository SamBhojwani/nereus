# Nereus — Long-Term Technical Strategy & Product Blueprint

*Prepared 2026-07-09 · against v1.0 as deployed (repo `5354a6e`) · author: acting CTO/advisor session*

---

## Part 0 — Understanding (read before the roadmap)

### What Nereus is today

Topic in → three live sources (NewsData.io, Reddit RSS→OAuth, YouTube Data v3) → one
normalized `ContentItem` → LLM fact-vs-opinion classifier (Groq `llama-3.1-8b-instant`,
batched + concurrent) → TTL cache with stale-while-revalidate → FastAPI JSON → thin React
client with an editorial UI. Deployed free: Netlify + HF Docker Space, kept warm by a
GitHub Actions cron. **The differentiator is not the classifier — it's that the classifier
is *measured***: 195 hand-labelled items, accuracy 0.821 / macro-F1 0.792, a public
MODEL_CARD with a confusion matrix and an honest "where it breaks" analysis.

### The design philosophy I infer (and will respect)

1. **Seams over frameworks.** `SourceProvider` / `LLMClient` / `Classifier` / `retrieve()`
   — every later phase is a drop-in, not a rewrite. (BUILD_BRIEF calls these "locked".)
2. **Evaluation over vibes.** No AI claim ships without a number against a gold set.
   The 70b→8b swap was decided by re-running the eval, not by preference.
3. **Free-tier constraints as architecture.** Caching, batching, graceful degradation
   ("Unrated" instead of errors), fail-fast on daily quotas — these are features born
   from constraints, and they generalize to cost discipline at any scale.
4. **Honesty as UX.** The UI dropped the fake-precise confidence %, explains the method,
   shows per-item reasoning. "A signal, not a verdict."
5. **Consult before pivots.** Direction changes are proposed, not committed unilaterally.

### Assumptions I'm making explicit

- Primary goal for the next 6–12 months remains **learning + placement portfolio value**;
  commercialization is optional upside, not a commitment.
- Solo, part-time development (student schedule); "1 unit" below ≈ one focused weekend.
- The "no accounts in v1" and "3 sources" locks apply to *v1*, not forever — BUILD_BRIEF
  itself schedules accounts and lean-analysis for Phase 4+.
- English-first stays true for now, though the strongest long-term wedge may be Indic
  (see Stretch).

### The one strategic insight everything else hangs on

Today Nereus is a **pull system**: classification happens at query time and the result
*evaporates* when the cache expires. Every re-fetch re-pays Groq tokens to re-learn the
same fact about the same article. The single most important evolution — cheap to start,
transformative over time — is to **persist every classification**, then gradually invert
to a **push system** (scheduled ingestion → classify once → serve many).

That inversion turns Nereus from "a search box that classifies" into **a growing,
queryable corpus of classified media** — and the corpus is what makes every ambitious
future possible: outlet profiles, trends over time, alerts, a public API, and above all
**training data for your own fine-tuned classifier**. The corpus is the moat. Nothing on
this roadmap matters more than starting to accumulate it.

---

## Part 1 — Competitive reality check

First, a challenge to the framing: ChatGPT / Claude / Gemini / Cursor / Manus / Devin /
OpenHands / Windsurf are **not Nereus's competitive set** — they're general assistants and
coding agents. Comparing against them produces flattering but useless conclusions. The
real neighbors are media-understanding products:

| Product | What it does | Where Nereus differs |
|---|---|---|
| **Ground News** | Outlet-level left/center/right ratings; coverage-comparison UI; subscription | Ratings are **static and outlet-level**. Nereus classifies **each item**, with reasoning shown, and can measure discourse *type* (reported vs. argued) — orthogonal to political lean |
| **AllSides** | Human-panel bias ratings, media-literacy mission | Same: outlet-level, manual, slow-moving. Nereus is per-item, automatic, measurable |
| **Otherweb** | ML "nutrition labels" for news quality | Closest conceptual neighbor. Nereus's edge: published evaluation (they publish none) and per-item rationale |
| **NewsGuard** | Journalist-scored outlet credibility, licensed B2B | Expensive human process, outlet-level. A machine per-item layer is complementary, not competitive |
| **Perplexity Discover** | AI news digest with citations | Summarizes; doesn't characterize discourse. No epistemics |
| **Artifact (†2024)** | AI news app by Instagram's founders — shut down | **The cautionary tale**: pure consumer news aggregation dies even with famous founders. Lesson: differentiate on analysis, and keep a B2B path open |

**Positioning that wins:** *Nereus does not tell you what is true. It tells you what kind
of discourse you're reading — measured, per item, with its reasoning shown.* Truth
adjudication (fact-checking) is a liability trap, an unsolved problem, and a crowded
nonprofit space. Discourse-type classification is tractable, measurable, and almost
nobody does it per-item. Hold this line at every scale.

**Gaps nobody owns:** per-item epistemics with published accuracy; discourse-type trends
over time ("opinion share of climate coverage this month"); story-level fact/opinion
ratios; non-English (especially Indic) media analysis; an affordable API for "is this
content reported or argued?" (brand safety, edtech, research).

---

## Part 2 — Three development paths

The paths share one spine (persist → corpus → own model → ingestion) and diverge on
infrastructure and ambition. **Recommendation: A now, bridge to B at v2.0, treat C as a
funded-only blueprint.** A→B is a ~$10–20/month decision you can make in an afternoon;
B→C is a life decision that needs users first.

### Path A — Completely Free (learning / portfolio maximum)

- **LLM:** Groq free tier now → **your own fine-tuned DistilBERT/DeBERTa-v3-small**
  (trained free on Colab/Kaggle, served on the existing HF CPU Space) as the primary
  classifier, LLM only as low-confidence fallback. Zero marginal cost, no token budget,
  and *"I distilled an LLM pipeline into my own evaluated model"* is a top-1% student
  portfolio line.
- **Persistence:** HF Spaces disks are ephemeral → use **Neon or Supabase free Postgres**
  (still $0) for the corpus; SQLite only for local dev.
- **Embeddings/RAG:** `sentence-transformers` MiniLM locally + **pgvector** on the free
  Postgres. No embedding APIs.
- **Ingestion:** GitHub Actions cron (already proven with keep-warm) fetching followed
  topics on schedule — a free worker queue in disguise.
- **Ceiling:** quotas (NewsData/YouTube), one small container, no accounts with real
  privacy obligations. Fine — the ceiling is high enough for v1.1→v2.0 entirely.
- **Optimizes:** engineering depth (fine-tuning, distillation, routing, eval discipline),
  zero burn, everything reproducible by a reviewer.

### Path B — Low Budget (~$10–40/month, best UX per rupee)

Everything in A, plus:
- **Hosting:** one small VPS (Hetzner ~€4) or Fly.io for the backend — kills the HF
  routing latency (~1.4s from India) and the sleep problem outright; custom domain (~$12/yr).
- **LLM:** Groq paid dev tier / OpenRouter for the fallback path — pennies at your volume,
  removes the daily-cap "Unrated" degradation forever.
- **Accounts + digests:** Supabase free auth + **Resend** (100 emails/day free) for
  followed-topic digests — the retention feature.
- **Observability:** Sentry free + PostHog free (or self-hosted Plausible) — see real
  users, real errors.
- **Optimizes:** reliability, retention features, a product that feels commercial.

### Path C — Serious Startup (funded blueprint — do not build speculatively)

The architecture below (Part 5) describes the destination; the business shape:
- **Two products, one corpus:** consumer app (differentiated news reading) + **B2B API**
  ("discourse-type classification as a service": brand safety, edtech media-literacy
  platforms, comms/PR monitoring, research). Artifact's death says consumer-only is
  fragile; NewsGuard's business says B2B licensing of media intelligence pays.
- **Enterprise table stakes:** SSO/SAML, RBAC, audit logs, SOC 2 Type II path, DPAs,
  usage-based billing (Stripe), 99.9% SLO with error budgets, status page.
- **Team to start:** 2 founders (product+ML), +2 engineers (platform, full-stack),
  +1 design; infra $1.5–4k/mo at seed scale.
- **Moats to build deliberately:** the labeled corpus (millions of items × your taxonomy),
  per-outlet longitudinal profiles nobody can backfill, eval benchmarks you publish
  (become the standard others cite).

---

## Part 3 — Version roadmap

Complexity: 1–10. Units: focused weekends, solo. Every version ends deployed.

### v1.0 — current (shipped)
Three sources, evaluated classifier (F1 0.792), editorial UI, SWR cache, startup warm,
keep-warm cron, rate limiting, CORS/URL hardening, 35 tests, live on Netlify + HF.

---

### v1.1 — "Stop forgetting" (foundation)
- **Goal:** persistence + engineering hygiene. The corpus starts here.
- **Major features:** classification store (every item + stance + rationale + model-version
  written to free Postgres, keyed by stable item id); instant first paint (localStorage
  snapshot of the last feed shown while fresh loads).
- **Technical:** GitHub Actions **CI** (pytest + frontend build on every push — you have
  35 tests and no CI, which is the single cheapest credibility win); **auto-deploy to the
  HF Space from GitHub** (kills the manual rsync drift between repo and Space — real
  tech-debt item); structured logging + Sentry free tier.
- **Architecture change:** new `Store` seam (`app/store/`) — same interface discipline as
  the other seams; cache checks store before re-classifying an already-seen item
  (dedupe by id → immediate token savings).
- **AI:** none yet — but every classification from now on is training data.
- **Complexity 3 · ~2–3 units · Prereqs: none · Impact:** every later version becomes
  possible; token burn drops; repo reads professionally (CI badge, releases).

### v1.2 — "RAG lands" (fills the BUILD_BRIEF Phase-4 promise)
- **Goal:** semantic understanding of the corpus.
- **Major:** local MiniLM embeddings for every stored item; **semantic dedup** replacing
  the `difflib` title heuristic; **story clustering** — group items covering the same
  event, show "12 items · 7 factual · 5 opinion" per story; "related items" on cards.
- **Architecture:** `retrieve()` internals gain a vector path (pgvector) exactly as the
  seam intended; embedding worker runs in the ingestion path, not request path.
- **UI:** story-cluster cards (the fact/opinion *ratio per story* is a genuinely novel
  display — no competitor shows it).
- **Complexity 5 · ~3–4 units · Prereqs: v1.1 store · Impact:** visible product leap +
  the "RAG" résumé keyword backed by something real.

### v1.3 — "Own the model" (the flagship ML milestone)
- **Goal:** replace the rented classifier with yours, measured.
- **AI:** relabel a **mixed-source eval set v2** (~400 items incl. Reddit/YouTube; compute
  inter-annotator agreement with a friend labelling 100 overlap items — fixes the two
  honest caveats in MODEL_CARD). Fine-tune **DeBERTa-v3-small / DistilBERT** on
  accumulated corpus (LLM silver labels) + gold set; target macro-F1 ≥ 0.85. Add
  **calibration** (temperature scaling) so confidence means something again — potentially
  restoring an honest % to the UI. **Model routing:** local model first (fast, free),
  LLM fallback only when confidence < threshold; publish the routing win in MODEL_CARD v2
  (accuracy vs. cost vs. latency table).
- **Performance:** classification latency collapses (no LLM round-trip for ~80% of items);
  the Groq daily-cap failure mode nearly disappears.
- **Complexity 7 · ~4–6 units · Prereqs: v1.1 (corpus), v1.2 helpful · Impact:** the
  strongest possible AI-engineer portfolio arc: *prompted → evaluated → distilled →
  routed → re-evaluated*. This is the version that gets interviews.

### v2.0 — "From searching to following" (the product turn)
- **Goal:** retention — Nereus becomes something you return to.
- **Major:** followed topics; scheduled ingestion for them (GH Actions cron → later a
  real worker); **email digests** ("what's reported vs. argued about your topics this
  week"); story pages (cluster + timeline); optional accounts (Path B: Supabase auth;
  Path A: local-only profiles, no server auth).
- **Architecture inflection:** the **push model** starts — ingestion decoupled from
  requests; the API increasingly serves from the corpus.
- **UI:** PWA (manifest + service worker) → installable on phones, offline shell; "new
  since you last looked" markers. (Native mobile stays deferred; the strict JSON boundary
  keeps it a drop-in later, as designed.)
- **Complexity 6 · ~5–8 units · Prereqs: v1.1–1.2 · Impact:** first real retention loop;
  the demo stops being a toy.

### v2.5 — "The second axis" (lean, done carefully)
- **Goal:** the outlet-lean dimension you already sketched (the "6 outlets · Left 2 ·
  Center 3 · Right 1" mock from your icon reference).
- **AI:** outlet-level lean from public research datasets / careful methodology — **not**
  scraped AllSides ratings (licensing). Better: your own longitudinal signal — stance
  ratios, framing divergence via embeddings — published with methodology, per the honesty
  philosophy. Label outlets, not articles, at first.
- **UI:** coverage-comparison bar per story cluster (lean × discourse-type grid — Ground
  News shows lean; nobody shows the 2-D grid).
- **Complexity 6 · ~4 units · Prereqs: v1.2 clusters, corpus depth · Impact:** direct,
  visible differentiation from every competitor.

### v3.0 — "Platform" (corpus as a product)
- **Goal:** others build on Nereus.
- **Major:** public **API** (keys, per-key quotas, docs, OpenAPI) — `/classify` (text in,
  stance + calibrated confidence + rationale out) and `/topics/{t}/analysis`; **browser
  extension** (classify the article you're reading, on-page badge — the highest-leverage
  distribution hack available to a solo dev); **claim extraction v1** (LLM pulls discrete
  factual claims from opinion pieces; link claims to reporting in the corpus).
- **Architecture:** Postgres + pgvector as system of record; Redis for cache + rate
  limits (multi-instance safe); a real worker (Celery/ARQ) replacing cron-as-queue;
  versioned API (`/v1/`).
- **Complexity 8 · ~2–3 months part-time · Prereqs: v1.3 model (API economics don't work
  paying Groq per call), v2.0 ingestion · Impact:** B2B optionality opens; extension
  drives organic growth.

### v4.0 — "Company-grade" (only with Path C funding/users)
- Multi-tenant SaaS: orgs, RBAC, SSO; Stripe usage billing; SLOs + on-call; IaC
  (Terraform), containers on ECS/Fly/K8s; observability suite (OTel traces, Grafana/
  Datadog, log aggregation); ClickHouse for analytics workloads; compliance program
  (SOC 2 path, DPAs, retention policies); onboarding flows, admin console, status page.
- **Complexity 9–10 · team-scale · Prereqs: revenue signal · Impact:** sellable product.

### Ultimate vision — "The media understanding layer"
Every story decomposed in near-real-time into **claims, evidence, argument, and
provenance**, longitudinally, across languages — consumable as a consumer app, an API,
embeddable widgets, and published research. The epistemic map of the news. Nereus, the
god who cannot lie, as infrastructure.

---

## Part 4 — Prioritized feature table

| Feature | Why it matters | Diff | User | Portfolio | Startup | Est. | Depends on | When |
|---|---|:-:|:-:|:-:|:-:|---|---|---|
| Classification store (corpus) | Enables literally everything else | 3 | 4 | 7 | 10 | 1–2 wknd | — | **Now** |
| CI + HF auto-deploy | Credibility + kills deploy drift | 2 | 2 | 8 | 5 | 1 wknd | — | **Now** |
| Few-shot prompt v2 | Cheap F1 bump on known failure mode (reported speech) | 2 | 5 | 5 | 4 | days | eval harness | **Now** |
| Eval set v2 (mixed-source + IAA) | Fixes MODEL_CARD's honest caveats | 4 | 3 | 9 | 6 | 2 wknd | — | Now/next |
| localStorage instant first paint | Perceived load → ~0 | 2 | 7 | 3 | 4 | days | — | **Now** |
| Semantic dedup + embeddings | Kills near-dupe spam properly | 4 | 6 | 8 | 6 | 2 wknd | store | Next |
| Story clustering + ratio UI | Novel display nobody has | 6 | 8 | 8 | 8 | 3 wknd | embeddings | Next |
| Fine-tuned own classifier + routing | Cost→0, latency↓, flagship ML story | 7 | 6 | **10** | 9 | 4–6 wknd | corpus | Next |
| Topic follow + digests | Retention loop | 5 | 8 | 5 | 8 | 3–4 wknd | ingestion | v2.0 |
| PWA | Mobile reach without an app | 3 | 6 | 4 | 5 | 1 wknd | — | v2.0 |
| Outlet lean axis + 2-D grid | Direct competitor differentiation | 6 | 8 | 7 | 8 | 4 wknd | clusters | v2.5 |
| Outlet profiles (longitudinal) | Un-backfillable data asset | 5 | 7 | 7 | 9 | 3 wknd | corpus depth | v2.5+ |
| Browser extension | Distribution + daily utility | 5 | 8 | 7 | 8 | 3 wknd | API | v3.0 |
| Public API + keys | B2B door opener | 6 | 4 | 6 | 9 | 4 wknd | own model | v3.0 |
| Claim extraction | Step toward the vision | 8 | 7 | 8 | 8 | 6+ wknd | clusters, LLM budget | v3.0+ |
| Multilingual (Indic first) | Underserved market you're positioned for | 8 | 9* | 8 | 9 | months | own-model pipeline | Later |

\* for the Indian market specifically.

**Deliberately not building (challenge-your-checklist section):** chat interface (no
advantage vs. incumbents; wrong interaction for this product) · general agentic
workflows/multi-agent (that's your other project; here an "agent" is just the ingestion
pipeline) · truth adjudication/fact-checking (liability, unsolved, off-positioning) ·
OCR/document intelligence/code execution (no user problem here) · marketplace/plugins
(ecosystem before users = theater) · native mobile before PWA proves demand · accounts
before v2.0 (BUILD_BRIEF was right) · voice (except podcast *transcription as a 4th
source* — parked in Stretch; compute-expensive but opinion-rich).

---

## Part 5 — Architecture evolution (and *why* each step)

| Layer | Now (fine!) | v1.x–v2.0 | v3.0 | v4.0 (funded) | Why it changes |
|---|---|---|---|---|---|
| Backend | FastAPI monolith | same + `Store` seam | same monolith, extracted workers | modular services only if team >4 | Monolith-first; seams already give you module boundaries. Microservices before a team is self-harm |
| Data | none (ephemeral cache) | free Postgres (Neon/Supabase) | Postgres = system of record | + read replicas, ClickHouse for analytics | The corpus inversion. Postgres because pgvector rides along free |
| Vector | — | pgvector | pgvector | dedicated (Qdrant) only past ~10M items | One database until scale forces two |
| Cache/limits | in-process dict (single instance!) | keep | **Redis** (multi-instance correctness) | Redis cluster | The in-process cache & limiter silently break at replica #2 — swap exactly then, not before |
| Queue/ingestion | GH Actions cron | cron-as-queue | Celery/ARQ + Redis broker | managed queue (SQS) + Temporal if workflows get long | Cron is a free queue until jobs need retries/fan-out |
| Model serving | Groq API | + own model in-process (CPU) | own model on small GPU/ONNX-CPU, LLM fallback | dedicated inference service, batching, autoscale | Routing = cost floor; own model = independence |
| Frontend | Vite SPA | + PWA | + extension | maybe Next.js if SEO for story pages matters | SEO is the only real reason to SSR |
| Hosting | Netlify + HF Space | + small VPS (Path B) | VPS/Fly + managed PG | ECS/K8s + Terraform + multi-region | Each step buys reliability you *currently* can't justify |
| CI/CD | none → **add now** | GH Actions: test+build+deploy both targets | + staging env, migrations gate | + canary, IaC pipelines | The two-repo manual rsync is the top drift risk today |
| Observability | logs in a tmp file | Sentry + structured logs | + metrics (Prometheus/Grafana Cloud free) | OTel traces, SLOs, on-call | Add each layer when someone would actually look at it |
| Auth/versioning | none / unversioned | anon-friendly, `/v1` prefix early | API keys + quotas | OIDC/SSO, RBAC, audit | Prefix the API `/v1` in v1.1 — free now, painful later |

---

## Part 6 — Technical debt register (ranked, with the plan)

1. **Two-repo deploy drift** (repo `backend/` vs. HF Space copy, manual rsync) — *the*
   footgun; one forgotten sync = prod running stale code. → Fix in v1.1 with a GH Action
   that pushes `backend/` to the Space on merge. ~an evening.
2. **No persistence** — classifications evaporate; tokens re-burned; no corpus. → v1.1.
3. **In-process cache + rate limiter** — correct only at exactly 1 instance; also cold on
   every deploy. → Documented constraint now; Redis at v3.0 (not before — cost/complexity
   unjustified at 1 replica).
4. **Eval set skew** — news-only, single annotator, 195 items; silently misrepresents
   Reddit/YouTube accuracy. → v1.3 eval-set v2 with IAA.
5. **No CI** — 35 tests that only run when remembered. → v1.1, trivial.
6. **Unversioned API** — `/search` not `/v1/search`; breaking changes will hurt the
   moment anyone else consumes it (extension, API users). → Add prefix + redirect in v1.1.
7. **No observability** — you can't see live errors or usage at all (the "is it slow?"
   question required manual curl forensics this week). → Sentry + structured logs, v1.1.
8. **Hardcoded prod API origin** in `index.html` preconnect + `SourceLogo` favicon
   third-party call — minor; document, revisit at custom-domain time.
9. **Frontend state all in `App.jsx`** — fine at this size; extract hooks when story
   pages land (v2.0), not before.
10. **Groq token budget as shared global** — one heavy visitor degrades everyone's
    classifications. Mitigated by caching/routing; solved properly by own model (v1.3).

Incremental rule: **every version retires at least one debt item** (v1.1 kills #1 #2 #5
#6 #7 in one sweep — that's why it's first).

---

## Part 7 — Stretch ideas (explicitly speculative — not roadmap commitments)

- **The claim graph.** Claims as first-class DB entities: extracted, deduplicated,
  linked across articles with *supports / disputes / repeats* edges. Query: "show me
  every distinct factual claim in this story and who reported vs. argued it." This is
  the ultimate-vision data structure, buildable incrementally after v3.0 claim extraction.
- **Counter-perspective engine ("steelman machine").** For any opinion piece: retrieve
  the strongest *reported facts* on the other side from the corpus — not "both sides"
  punditry, but opinion↔evidence pairing. Genuinely novel reading experience.
- **Narrative drift metrics.** Same story cluster, embedding-space divergence between
  outlets over time — a *quantitative* framing-difference signal. Publishable as a
  student research note; differentiating as a product feature.
- **Community labeling flywheel.** Users flag disagreement with a label → active-learning
  queue → periodic retrain → published F1 improvements. Your eval harness becomes a
  product feature and the corpus quality compounds. (Needs abuse controls.)
- **On-device classification.** Fine-tuned model quantized to WebGPU/transformers.js —
  the browser extension classifies *locally*: zero server cost, perfect privacy story.
- **LLM-debate adjudication study.** For low-confidence items, two models argue
  fact-vs-opinion, a judge adjudicates; measure against gold. Cheap, fun, publishable
  mini-paper that feeds the routing threshold.
- **Indic media map.** Fact/opinion + lean across Hindi/Marathi/Tamil/Telugu news — your
  feed already surfaces this content; the market is enormous and analytically unserved;
  you have native context. If Nereus ever becomes a company, this might be its actual
  wedge — competitors are structurally English-first.
- **Podcast ingestion.** Whisper-transcribed podcasts as a 4th `SourceProvider` —
  opinion-rich, un-analyzed medium. Compute-heavy; wait for own-model economics.
- **"Epistemic weather report."** A weekly auto-generated brief per topic: what became
  established fact, what's still argued, what changed — the agentic workflow that
  actually fits this product (and rhymes with your multi-agent research assistant).

---

## Part 8 — Operating principles going forward

1. **Corpus first.** When in doubt, choose the option that grows or exploits the corpus.
2. **Every model change re-runs the eval.** No exceptions; publish the number either way.
3. **Signal, not verdict.** Classify discourse; never adjudicate truth.
4. **Monolith + seams until it hurts.** Complexity is bought with real traffic only.
5. **Free until users force spending; spend where users feel it** (latency, reliability,
   digests) — never on speculative scale.
6. **Ship deployed or it didn't happen** — the standing rule that got v1 live stays.
