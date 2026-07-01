# Nereus frontend

React (Vite). A **thin rendering layer** — zero business logic here; it only calls the
backend API (`src/api.js`) and renders faithful cards. That boundary is what keeps a
future mobile client a drop-in.

## Run locally

The backend must be running on `http://127.0.0.1:8000` first (see `../backend/README.md`).

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (Vite proxies /api -> :8000)
```

## What it does

- **Search** a topic → live news + Reddit + YouTube, each classified factual/opinion.
- **Faithful cards** per source: article (thumbnail), Reddit post (score/comments),
  YouTube (embedded player).
- **Filters** (client-side, session-local — no accounts in v1): fact vs. opinion, and by source.
- Every card shows the classifier's stance + confidence; hover the badge for the model's rationale.

## Deploy (Phase 3 finish)

`npm run build` → static bundle in `dist/`. Host on Vercel/Netlify. Set `VITE_API_BASE`
to the deployed backend URL before building (see `.env.example`).
