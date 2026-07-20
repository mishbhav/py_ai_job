# Job Market Fit Analyzer

Scrapes live Adzuna job postings for a target role, computes a CV-to-market
match score (TF-IDF + cosine similarity), aggregates in-demand keywords,
clusters postings into sub-domains, and asks a Hugging Face LLM to generate a
targeted skill-gap analysis with a learning path.

## Architecture

```
backend/   FastAPI + Playwright scraper + scikit-learn + Keras + Anthropic API
frontend/  React (Vite) + Recharts dual-panel dashboard
```
Pipeline: `Upload CV (PDF) → fetch JDs from Adzuna → clean text → TF-IDF match score + keyword frequency (pandas) → domain clustering → Hugging Face LLM gap synthesis → dashboard`.

## Running in GitHub Codespaces

1. Push this folder to a GitHub repo, then **Code → Create codespace on main**.
2. The devcontainer auto-installs backend (`pip`) and frontend (`npm`) deps via `postCreate.sh`. This can take a few minutes on first boot.
3. Add your Hugging Face token as a Codespaces secret named `HF_API_TOKEN` (Settings → Secrets and variables → Codespaces), or copy `backend/.env.example` to `backend/.env` and paste it in there.
4. Start both servers:
   ```bash
   bash scripts/dev.sh
   ```
   Or run them separately:
   ```bash
   cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   cd frontend && npm run dev
   ```
5. Codespaces will prompt to forward ports 8000 and 5173 — open the 5173 preview. The frontend auto-detects the matching `-8000.app.github.dev` backend URL (see `frontend/src/api/client.js`); no manual config needed.

## Known rough edges to expect

- **Adzuna API Limits**: The application relies on free-tier Adzuna API calls. Ensure your API keys (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`) are active and have sufficient request allowances. If API limits are exhausted, fallback to the manual input endpoint.
- **Hugging Face Serverless API**: Free-tier inference endpoints can occasionally face cold starts or temporary rate limits. If a model is unavailable, swap `HF_INFERENCE_MODEL` in your environment config to an alternative open-source model.
- **Keras classifier** ships as an architecture + a keyword-overlap fallback (`backend/app/services/classifier.py`) since multi-label training needs a labeled dataset this project doesn't have yet. Swap in `classify_with_keras` once you've trained on labeled JDs.
- **In-memory job store** (`_JOBS` dict in `routes.py`) is fine for solo/local use; swap for Redis or a DB table before deploying for multiple users.

## Environment variables (backend/.env)

| Variable | Purpose |
|---|---|
| `HF_API_TOKEN` | Required for the free Hugging Face serverless LLM gap-analysis step |
| `HF_INFERENCE_MODEL` | Hugging Face model repository ID (e.g., `Qwen/Qwen2.5-7B-Instruct`) |
| `LLM_PROVIDER` | Set to `huggingface_api` (or `local_transformers` for offline execution) |
| `ADZUNA_APP_ID` | Your Adzuna developer Application ID |
| `ADZUNA_APP_KEY` | Your Adzuna developer Application Secret Key |
| `SCRAPE_MAX_JOBS` | Cap on JDs requested per query search (default 40) |

## API surface

- `POST /api/analysis` — multipart form: `role_query`, `location?`, `max_jobs`, `cv_file` → `{ job_id, status }`
- `POST /api/analysis/manual` — same but with `jd_texts[]` instead of live Adzuna queries
- `GET /api/analysis/{job_id}` — poll for status + results
- `GET /health` — liveness check
- `GET /api/analysis/{job_id}` — poll for status + results
- `GET /health` — liveness check
