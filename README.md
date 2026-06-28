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

- **Phase 1 — backend spine (in progress).** `/search?q=...` returns live, classified
  news as JSON. NewsData.io source → normalized `ContentItem` → LLM fact/opinion
  classifier (batched) → cached JSON.
- Phase 2 (classifier evaluation), Phase 3 (Reddit + YouTube + React frontend + deploy),
  Phase 4+ (RAG) — not started.

## Layout

```
nereus/
├── BUILD_BRIEF.md          working spec — read this first
├── backend/                FastAPI + the AI core
│   ├── app/
│   │   ├── main.py         API: /health /search /feed (only place concretes are wired)
│   │   ├── models.py       ContentItem — the one normalized shape
│   │   ├── cache.py        in-memory TTL cache (a hit skips the source APIs AND the LLM)
│   │   ├── sources/        SourceProvider interface + NewsData source
│   │   ├── llm/            LLMClient interface + Gemini client (swappable)
│   │   ├── classifier/     Classifier interface + LLM classifier (batched)
│   │   └── pipeline/       retrieve() — the RAG socket for Phase 4
│   ├── requirements.txt
│   └── .env.template       copy to .env and add keys
└── frontend/               React (Vite) — Phase 3
```

## Run the backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env          # then fill in GEMINI_API_KEY and NEWSDATA_API_KEY
uvicorn app.main:app --reload
```

Then:

- `GET http://127.0.0.1:8000/health` — shows which sources/classifier are live
- `GET http://127.0.0.1:8000/search?q=elections` — live, classified news as JSON
- `GET http://127.0.0.1:8000/feed` — default topic feed
- `http://127.0.0.1:8000/docs` — interactive API docs

### Keys (both free, no card)

- **Gemini** — https://aistudio.google.com/apikey → `GEMINI_API_KEY`
- **NewsData.io** — https://newsdata.io/register → `NEWSDATA_API_KEY`

Without keys the app still boots: sources return empty and `/health` reports them down.
