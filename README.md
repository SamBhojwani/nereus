# Nereus

A topic-search media platform. Enter a topic; Nereus pulls **live** content from
multiple sources, classifies each piece as **factual vs. opinion** with an AI model
that is *actually evaluated* (precision/recall/F1), and renders everything as faithful
platform cards. No accounts in v1.

Named for *Nereus*, the Greek sea-god who could not tell a lie.

See [`BUILD_BRIEF.md`](BUILD_BRIEF.md) for the locked decisions, architecture seams, and
phase plan. The companion `media-platform-build-plan.md` (kept outside the repo) has the
full reasoning.

## Status

- **Phase 1 — backend spine ✅.** `/search?q=...` returns live, classified content as JSON.
  Source → normalized `ContentItem` → LLM fact/opinion classifier (batched) → cached JSON.
  Provider is swappable (`LLM_PROVIDER=gemini|groq`).
- **Phase 2 — classifier evaluation ✅.** Measured on 195 hand-labelled items from the
  pipeline's own output: **accuracy 0.821, macro-F1 0.792** on the operational model
  `llama-3.1-8b-instant` (see [`MODEL_CARD.md`](MODEL_CARD.md)). Harness + a local labelling
  tool live in [`backend/eval/`](backend/eval/).
- **Phase 3 — three sources + frontend ✅.** News (NewsData.io), Reddit (public RSS, auto-
  upgrades to the OAuth API when creds are set), and YouTube (Data API v3). React (Vite)
  frontend with an editorial UI, skeleton loading, and scroll-reveal cards.
- Phase 4+ (RAG retrieval behind the same `retrieve()` seam) — not started.

### Operational notes

- **The binding constraint is the LLM's free-tier token-per-day budget.** Groq's
  `llama-3.1-8b-instant` gives 500k/day; a fresh search classifies ~30 items. See the
  MODEL_CARD for why 8b (not 70b) is the operational model.
- **Graceful degradation:** if the LLM is rate-limited, items still render with an "Unrated"
  badge instead of the request hanging; that degraded result is cached only briefly
  (`CACHE_TTL_DEGRADED`) so it self-heals. The frontend also has a 30s request timeout.
- **Abuse protection:** `/search` and `/feed` are per-IP rate-limited; CORS is restricted to
  `CORS_ORIGINS`; all outbound URLs are http(s)-validated before reaching the client.

## Layout

```
nereus/
├── BUILD_BRIEF.md          working spec — read this first
├── MODEL_CARD.md           classifier evaluation + where it breaks
├── backend/                FastAPI + the AI core
│   ├── app/
│   │   ├── main.py         API: /health /search /feed (+ CORS, rate-limit middleware)
│   │   ├── models.py       ContentItem — the one normalized shape (+ URL sanitization)
│   │   ├── cache.py        in-memory TTL cache (a hit skips the source APIs AND the LLM)
│   │   ├── ratelimit.py    per-IP sliding-window limiter
│   │   ├── sources/        SourceProvider interface + news / reddit / youtube
│   │   ├── llm/            LLMClient interface + gemini / groq clients (swappable)
│   │   ├── classifier/     Classifier interface + LLM classifier (batched, concurrent)
│   │   └── pipeline/       retrieve() — fan-out, interleave, dedup, cap (RAG socket)
│   ├── eval/               evaluation harness + local labelling tool
│   ├── tests/              pytest suite (classifier, retriever, ratelimit, retry, models)
│   ├── requirements.txt / requirements-dev.txt
│   └── .env.template       copy to .env and add keys
└── frontend/               React (Vite) — thin client over the API
```

## Run the backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env          # then fill in GROQ_API_KEY and NEWSDATA_API_KEY (minimum)
uvicorn app.main:app --reload
```

Then:

- `GET http://127.0.0.1:8000/health` — shows which sources/classifier are live
- `GET http://127.0.0.1:8000/search?q=elections` — live, classified content as JSON
- `GET http://127.0.0.1:8000/feed` — default topic feed
- `http://127.0.0.1:8000/docs` — interactive API docs

## Run the frontend

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173 (proxies /api → backend :8000)
```

For a deployed frontend, set `VITE_API_BASE` to the backend URL and `CORS_ORIGINS`
(backend) to the frontend's origin.

## Test

```bash
cd backend && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                         # classifier, retriever, rate limiter, retry policy, models
python eval/evaluate.py        # re-run the classifier evaluation (reads the labelled CSV)
```

### Keys (all free, no card)

- **Groq** — https://console.groq.com/keys → `GROQ_API_KEY` (the classifier)
- **NewsData.io** — https://newsdata.io/register → `NEWSDATA_API_KEY` (news source)
- **YouTube Data API v3** — https://console.cloud.google.com → `YOUTUBE_API_KEY` (optional)
- **Reddit** — works with no key (public RSS); add `REDDIT_CLIENT_ID`/`SECRET` to upgrade
- **Gemini** — https://aistudio.google.com/apikey → `GEMINI_API_KEY` (alternative provider)

Without keys the app still boots: each source returns empty and `/health` reports it down.
