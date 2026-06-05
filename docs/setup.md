# Local Setup

## Prerequisites
- Python 3.12+
- Node.js 20+
- A Supabase project (free tier is fine)

## 1. Database

1. Create a new Supabase project at supabase.com
2. In the SQL editor, run `db/schema.sql` to create all tables and the immutability trigger
3. Copy your connection string: **Settings → Database → Connection string → URI**
4. It looks like `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`

## 2. Pipeline

```bash
cd pipeline
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Create `pipeline/.env`:
```
DATABASE_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
```

## 3. Seed teams and load data

First seed the known cross-source team-name mappings:
```bash
# run db/seed_teams.sql in the Supabase SQL editor (after schema.sql)
```

Then load historical results (reads straight from GitHub, no download needed):
```bash
python pipeline/data/load_kaggle.py
```

Then load the 2026 fixture list:
```bash
python pipeline/data/load_fixtures.py
```

Data source details and licensing are documented in [data-sources.md](data-sources.md).

## 4. GitHub Actions secrets

In your repo settings, add one secret:
- `DATABASE_URL` — same connection string as above

## 5. Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## 6. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```
