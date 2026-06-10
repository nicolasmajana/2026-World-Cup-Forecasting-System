# Local Setup

## Prerequisites
- Python 3.12+
- Node.js 20+
- A Supabase project (free tier is fine)

## 1. Database

1. Create a new Supabase project at supabase.com
2. In the SQL editor, run in order:
   - `db/schema.sql` (tables + immutability trigger)
   - `db/seed_teams.sql` (cross-source team-name aliases)
   - `db/migrations/002_prediction_history.sql`
   - `db/migrations/003_fix_delete_trigger.sql`
   - `db/migrations/004_tournament_sim.sql`
3. Get your connection strings from the **Connect** button. There are two and the difference matters:
   - **Session pooler** (port 5432): for the Python pipeline and GitHub Actions. Capped at 15 clients.
   - **Transaction pooler** (port 6543): for the frontend (serverless, many short connections).
4. URL-encode special characters in the password (a `+` becomes `%2B`).

## 2. Pipeline

```bash
cd pipeline
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Create `pipeline/.env` (session pooler):
```
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-X-region.pooler.supabase.com:5432/postgres
```

On Windows, run scripts with `PYTHONUTF8=1` set to avoid console encoding crashes.

## 3. Load data

```bash
python pipeline/data/load_kaggle.py      # 49k historical matches, streamed from GitHub
python pipeline/data/load_fixtures.py    # the 2026 fixture list
python pipeline/data/verify_load.py      # sanity-check row counts
```

## 4. Train, predict, simulate

```bash
python pipeline/model/train.py                  # validate + log a model run
python pipeline/jobs/backfill_predictions.py    # lock predictions for all known fixtures
python pipeline/jobs/snapshot_odds.py           # first odds snapshot
python pipeline/jobs/simulate_tournament.py 5000  # full-tournament Monte Carlo
python pipeline/data/verify_ready.py            # end-to-end readiness check
```

## 5. GitHub Actions

In repo **Settings → Secrets and variables → Actions → Repository secrets**, add:
- `DATABASE_URL` (the session-pooler string)

That activates both workflows: `lock-predictions.yml` (daily 06:00 UTC) and `update-results.yml` (every 3 hours). Trigger them once manually from the Actions tab to confirm they go green.

## 6. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local` (transaction pooler, port 6543; server-only, no NEXT_PUBLIC prefix):
```
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-X-region.pooler.supabase.com:6543/postgres
```

The frontend queries Postgres directly from Server Components; no backend service is required.

## 7. Deploy (Vercel)

Import the GitHub repo in Vercel, set **Root Directory = `frontend`**, and add the `DATABASE_URL` env var (transaction pooler). Every push to `main` auto-deploys.

## Optional: FastAPI backend

`backend/` is a standalone API layer (not used by the site):
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Data source details and licensing: [data-sources.md](data-sources.md).
