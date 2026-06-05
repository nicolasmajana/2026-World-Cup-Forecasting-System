# WC 2026 Forecast

Live probabilistic forecasting for the 2026 FIFA World Cup.

Every prediction is locked before kickoff and cannot be edited once the match starts. The goal is public accountability: you can see exactly what the model said, and exactly whether it was right.

**[Live site →](https://wc2026.vercel.app)** · **[Methodology →](https://wc2026.vercel.app/methodology)**

---

## How it works

Before every match, the pipeline generates win/draw/loss probabilities and an expected scoreline using a Poisson regression model. Those predictions are timestamped and locked in the database. After the match, the actual result is recorded and the Brier score is updated.

The headline metric is **Brier score**, not accuracy. Accuracy is a vanity number in forecasting — what matters is calibration. A model that says "70% home win" should be right about 70% of the time across all such predictions.

### Model (v1)

1. **Poisson regression** estimates expected goals (λ) for each team using ~10 features:
   - Rolling attacking and defensive strength (last 10 games)
   - FIFA Elo rating
   - Home / away / neutral venue
   - Days of rest
   - Confederation
   - Head-to-head record

2. **Monte Carlo simulation** (10,000 trials) samples `Poisson(λ)` for both teams and counts win/draw/loss frequencies to produce final probabilities.

### Immutability guarantee

The `predictions` table has a database-level constraint that prevents any update once `match_kickoff` has passed. Application code cannot override this — it's enforced at the Postgres layer.

---

## Stack

| Layer | Tech |
|---|---|
| Modeling & pipeline | Python (scikit-learn, pandas, scipy) |
| Backend API | FastAPI |
| Database | Postgres on Supabase |
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui |
| Frontend host | Vercel |
| Backend host | Railway |
| Scheduled jobs | GitHub Actions |

---

## Project structure

```
wc2026/
├── pipeline/          # Python: feature engineering, model training, prediction jobs
│   ├── data/          # Data loading and preprocessing
│   ├── model/         # Poisson regression + Monte Carlo
│   └── jobs/          # GitHub Actions job scripts
├── backend/           # FastAPI app
│   ├── routers/
│   └── db/
├── frontend/          # Next.js app
│   ├── app/
│   └── components/
├── db/
│   └── schema.sql     # Supabase schema with immutability constraint
└── .github/
    └── workflows/     # lock-predictions.yml, update-results.yml
```

---

## Running locally

See [docs/setup.md](docs/setup.md).

---

## Calibration

Current Brier score and reliability diagram: [wc2026.vercel.app/calibration](https://wc2026.vercel.app/calibration)
