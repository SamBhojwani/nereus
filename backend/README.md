---
title: Nereus API
emoji: 🌊
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Nereus API (backend)

FastAPI service for [Nereus](https://github.com/SamBhojwani/nereus): pulls live content
from news / Reddit / YouTube, classifies each item **fact vs. opinion** with an evaluated
LLM, and returns normalized JSON. The `README.md` front-matter above configures the
Hugging Face **Docker** Space (it serves on port 7860 via the `Dockerfile`).

**Endpoints:** `/` · `/health` · `/search?q=...` · `/feed` · `/docs`

**Required secrets** (set in the Space's *Settings → Secrets*, never commit them):
`GROQ_API_KEY`, `NEWSDATA_API_KEY`, and optionally `YOUTUBE_API_KEY`. Set `CORS_ORIGINS`
to your deployed frontend URL. See `.env.template` for the full list and defaults.

Run locally: `uvicorn app.main:app --reload` (see the repo root README).
