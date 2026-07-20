# Job Market Fit Analyzer

Scrapes live Naukri job postings for a target role, computes a CV-to-market
match score (TF-IDF + cosine similarity), aggregates in-demand keywords,
clusters postings into sub-domains, and asks an LLM to generate a targeted
skill-gap analysis with a learning path.

## Architecture

```
backend/   FastAPI + Playwright scraper + scikit-learn + Keras + Anthropic API
frontend/  React (Vite) + Recharts dual-panel dashboard
```

Pipeline: `Upload CV (PDF) → scrape JDs → clean text → TF-IDF match score +
keyword frequency (pandas) → domain clustering → LLM gap synthesis → dashboard`.

## Running in GitHub Codespaces

1. Push this folder to a GitHub repo, then **Code → Create codespace on main**.
2. The devcontainer auto-installs backend (`pip`) and frontend (`npm`) deps,
   plus the Playwright Chromium binary, via `postCreate.sh`. This can take
   a few minutes on first boot.
3. Add your Anthropic key as a Codespaces secret named `ANTHROPIC_API_KEY`
   (Settings → Secrets and variables → Codespaces), or copy
   `backend/.env.example` to `backend/.env` and paste it in there.
4. Start both servers:
   ```bash
   bash scripts/dev.sh
   ```
   Or run them separately:
   ```bash
   cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   cd frontend && npm run dev
   ```
5. Codespaces will prompt to forward ports 8000 and 5173 — open the 5173
   preview. The frontend auto-detects the matching `-8000.app.github.dev`
   backend URL (see `frontend/src/api/client.js`); no manual config needed.

## Known rough edges to expect

- **Scraper selectors** (`backend/app/services/scraper.py`) are a best-effort
  starting point — Naukri's DOM changes over time and may show captchas to
  automated browsers. If scraping fails, use the `/api/analysis/manual`
  endpoint to paste JD text directly and keep the rest of the pipeline
  running.
- **Keras classifier** ships as an architecture + a keyword-overlap fallback
  (`backend/app/services/classifier.py`) since multi-label training needs a
  labeled dataset this project doesn't have yet. Swap in `classify_with_keras`
  once you've trained on labeled JDs.
- **In-memory job store** (`_JOBS` dict in `routes.py`) is fine for solo/local
  use; swap for Redis or a DB table before deploying for multiple users.

## Environment variables (backend/.env)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required for the LLM gap-analysis step |
| `ANTHROPIC_MODEL` | Defaults to `claude-sonnet-4-6` |
| `SCRAPE_MAX_JOBS` | Cap on JDs scraped per search (default 40) |
| `SCRAPE_HEADLESS` | Set `false` locally to watch Playwright work |

## API surface

- `POST /api/analysis` — multipart form: `role_query`, `location?`, `max_jobs`, `cv_file` → `{ job_id, status }`
- `POST /api/analysis/manual` — same but with `jd_texts[]` instead of scraping
- `GET /api/analysis/{job_id}` — poll for status + results
- `GET /health` — liveness check
