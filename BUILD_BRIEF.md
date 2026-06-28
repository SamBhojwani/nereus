# Nereus — Build Brief for Claude Code

Paste this into the repo (e.g. as `CLAUDE.md` or `BUILD_BRIEF.md`) and point Claude Code at it. It tells you what's decided, what the architecture is, and what to build first. The companion file `media-platform-build-plan.md` has the full phase-by-phase reasoning; this is the working spec.

---

## What Nereus is

A topic-search media platform. The user enters a topic; Nereus pulls **live** content from multiple sources, classifies each piece as **factual vs. opinionated** using an AI model that is **actually evaluated** (precision/recall/F1), and renders everything as faithful platform cards. Deployed at a public link. No accounts in v1.

The name: *Nereus*, the Greek sea-god who could not tell a lie — apt for a fact-vs-opinion product.

---

## Locked decisions (do NOT relitigate these — they were deliberated and settled)

- **Sources (exactly 3):** a news source (NewsData.io primary), **Reddit** (opinion-rich), **YouTube** (video). No Twitter/Instagram (paywalled APIs; would force fake data that contradicts the "verifiable sources" principle).
- **AI core:** fact-vs-opinion classifier — **LLM-prompted**, **article-level**, **binary**. Must be **evaluated** on a hand-labelled test set. This is the project's differentiator; it is not optional.
- **No accounts / no auth in v1.** Session or client-side filters only.
- **Frontend:** React (Vite). **Backend:** FastAPI returning plain JSON. **Strict boundary** — all logic in the backend, frontend is a thin renderer. This keeps a future mobile app a drop-in.
- **Free tier only.** Caching is architecture, not an afterthought.
- **RAG + vector DB are deferred to Phase 4.** The code already leaves a clean socket (`retrieve()`) for them — do not build RAG in Phase 1.

---

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | FastAPI (Python 3.11+) | skeleton provided |
| LLM | Gemini free tier (primary), Groq (fallback) | behind `LLMClient` — swappable |
| News | NewsData.io (deployed), Google News RSS (unlimited backstop) | **NOT** NewsAPI.org for deploy — it's localhost/dev-only |
| Reddit | official Reddit API (OAuth, free non-commercial) | ~100 q/min |
| YouTube | YouTube Data API v3 | search = 100 units of 10k/day → ~100 searches/day, **cache hard** |
| Frontend | React + Vite | thin client |
| Embeddings (Phase 4) | sentence-transformers, run locally | free, no API quota |
| Vector DB (Phase 4) | pgvector (Supabase) or Qdrant Cloud free | |
| Hosting | frontend: Vercel/Netlify · backend: Render free / HF Spaces | Render free cold-starts; fine for low traffic |

---

## Architecture — the contracts (already scaffolded in `nereus-backend/`)

The skeleton encodes the decisions. Respect these seams; they are why later phases are drop-ins, not rewrites.

- **`app/models.py` — `ContentItem`**: the ONE normalized shape every source maps into and every stage consumes. Add sources or swap the classifier without touching it.
- **`app/sources/base.py` — `SourceProvider`**: every source implements `async fetch(query, limit) -> list[ContentItem]`. `app/sources/news.py` is a working example of the pattern.
- **`app/llm/base.py` — `LLMClient`**: the only seam to the model. Gemini→Groq→paid = one new subclass.
- **`app/classifier/base.py` — `Classifier`**: the fact-vs-opinion contract. LLM-prompted now; a fine-tuned model later satisfies the same interface. `classify_many()` is where to **batch** calls to save quota.
- **`app/pipeline/retrieve.py` — `retrieve()`**: the named retrieval step and the key RAG socket. v1 fans out to sources; Phase 4 swaps its *internals* for vector search with the signature unchanged.
- **`app/main.py`**: FastAPI app, `/health` `/search` `/feed`, the clean JSON boundary. Concrete sources/classifier are wired here and ONLY here.

---

## BUILD THIS NOW — Phase 1 (backend spine, one source end-to-end)

**Goal:** `/search?q=...` returns live, classified news as JSON.

1. **Implement `GeminiClient(LLMClient)`** in `app/llm/gemini.py` — reads `GEMINI_API_KEY`, implements `complete()`.
2. **Implement `LLMClassifier(Classifier)`** in `app/classifier/llm.py` — prompts the LLM to return `{stance, confidence, rationale}` for `item.text_for_classification()`. Keep the rationale (needed for Phase 2 error analysis and the UI "why").
   - Override `classify_many()` to **batch** several items per LLM call — this is the main free-tier lever.
3. **Wire the classifier into `app/main.py`** (uncomment the marked lines): `items = await classifier.classify_many(items)` in `/search` and `/feed`.
4. **Add a caching layer** keyed by query so repeat searches don't re-hit the news API or the LLM. In-memory + TTL is fine for v1.
5. **Get a NewsData.io key**, fill `.env`, confirm `/search?q=elections` returns real classified items.

**Acceptance:** hitting `/search?q=<topic>` returns live news items, each with a `classification` of `factual` or `opinion` plus confidence and rationale. `/health` shows the news source live.

---

## Then, in order

- **Phase 2 — Evaluate the classifier (do NOT skip).** Hand-label ~150–200 items pulled from real `/search` output. Compute precision/recall/F1 + confusion matrix. Write a short results note with 3–5 failure examples and *why*. This is the line that makes the project stand out. Put numbers in the README.
- **Phase 3 — Reddit + YouTube providers** (same `SourceProvider` pattern) + **React frontend** (faithful article/Reddit/YouTube cards, search, source + fact/opinion filters) + **deploy**. This is the complete v1 — stoppable here.
- **Phase 4+ — RAG + vector DB** (swap `retrieve()` internals; add semantic dedup), then scheduled ingestion (GitHub Actions cron), then accounts, fine-tuned classifier (compare F1 to the Phase-2 baseline), source-level political lean.

---

## Free-tier landmines (design around these from day one)

- NewsAPI.org = dev/localhost only → use NewsData.io / GNews / RSS for anything deployed.
- YouTube search burns 100 units of a 10k/day budget → ~100 searches/day → **cache or it 403s mid-demo**.
- LLM free tiers ≈ 1,000–1,500 req/day and models get rotated → keep `LLMClient` swappable, never hardcode a model name.
- Render free tier cold-starts after idle → acceptable for low traffic; expect a slow first request.
- Phase 4 embeddings: run locally (sentence-transformers), don't pay for an embedding API.

---

## Working style for Claude Code

- Build Phase 1 fully and get it **running** before touching Phase 2+. A working spine beats a broad half-build.
- Deploy early (even a trivial version) so deployment is never a last-day surprise.
- Keep concrete implementations wired only in `main.py`. Everything else depends on the interfaces.
- When time is tight, narrow *within* a phase (e.g. 2 sources instead of 3) rather than skipping Phase 2's evaluation.
