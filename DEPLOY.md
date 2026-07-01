# Deploying Nereus

Backend → **Hugging Face Spaces** (Docker). Frontend → **Netlify**. Both have free tiers.

The two talk cross-origin, so there's an ordering: **deploy the backend first**, point the
frontend at it, then tell the backend to trust the frontend's origin.

```
1. Backend → HF Space        →  get  https://<user>-<space>.hf.space
2. Frontend → Netlify         →  set  VITE_API_BASE = that backend URL
                              →  get  https://<site>.netlify.app
3. Backend  →  set  CORS_ORIGINS = that frontend URL, restart
```

---

## 1. Backend — Hugging Face Space (Docker)

1. **Create the Space:** huggingface.co → *New* → *Space*. Choose **Docker** (blank), free
   CPU. This gives you a git repo at `https://huggingface.co/spaces/<user>/<space>`.

2. **Push the backend into it.** The `Dockerfile` and `README.md` (with the HF front-matter)
   already live in `backend/`, so the Space just needs the contents of `backend/`:

   ```bash
   git clone https://huggingface.co/spaces/<user>/<space> nereus-space
   cd nereus-space
   # copy backend contents but NOT secrets or local cruft:
   rsync -a --exclude='.env' --exclude='.venv' --exclude='__pycache__' \
         --exclude='.pytest_cache' /path/to/nereus/backend/ .
   git add .
   git commit -m "Deploy Nereus backend"
   git push
   ```

   > ⚠️ **HF Spaces are public git repos.** Never commit `.env` — the `rsync --exclude`
   > above keeps it out. Double-check with `git status` before pushing. Keys go in Secrets ↓

3. **Set Secrets** (Space → *Settings → Secrets and variables*). These become env vars:
   - `GROQ_API_KEY` — your Groq key
   - `NEWSDATA_API_KEY` — your NewsData key
   - `YOUTUBE_API_KEY` — optional (Reddit needs no key; it uses public RSS)
   - `LLM_PROVIDER` = `groq`
   - `GROQ_MODEL` = `llama-3.1-8b-instant`
   - `CORS_ORIGINS` — leave for now; set in step 3 once you have the Netlify URL.

4. Wait for the build, then check `https://<user>-<space>.hf.space/health` → should report
   the sources and classifier as live. Copy this base URL.

## 2. Frontend — Netlify

1. Netlify → *Add new site → Import from Git* → pick the `nereus` GitHub repo. `netlify.toml`
   already sets the base (`frontend`), build (`npm run build`), and publish (`dist`).
2. **Environment variables** → add `VITE_API_BASE` = the HF base URL from step 1.4
   (e.g. `https://<user>-<space>.hf.space`). Vite bakes this in at build time.
3. Deploy. Note your site URL, e.g. `https://<site>.netlify.app`.
   *(If you set `VITE_API_BASE` after the first build, trigger a redeploy so it takes.)*

## 3. Close the loop (CORS)

Back in the HF Space Secrets, set `CORS_ORIGINS` = your Netlify URL
(`https://<site>.netlify.app`) and restart the Space (*Settings → Factory reboot*, or push
any commit). The frontend can now call the backend.

Visit the Netlify URL — you're live. 🎉

---

## Good to know

- **Cold starts / sleep:** free HF Spaces sleep after inactivity; the first request wakes
  them (can take ~30s). The frontend's 30s request timeout covers this; a retry usually
  lands instantly once warm.
- **Shared free-tier budget:** every visitor shares one Groq/YouTube/NewsData daily quota.
  Caching softens this, but under real traffic the classifier can hit its daily cap — the UI
  degrades to "Unrated" rather than breaking. Raising `CACHE_TTL_*` stretches the budget.
- **Custom domain:** both hosts support one; add it in their dashboards and remember to add
  the new origin to `CORS_ORIGINS`.
