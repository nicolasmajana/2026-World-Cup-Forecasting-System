# World Cup 2026 Forecasting System

Live probabilistic forecasting for the 2026 FIFA World Cup.

Every prediction is locked with a timestamp before kickoff and cannot be edited once the match starts. The point is public accountability: anyone can see exactly what the model said before the ball was kicked, and exactly how well it is calibrated as the tournament unfolds.

**[Live site](https://2026-world-cup-forecasting-system.vercel.app/)** · **[Methodology](https://2026-world-cup-forecasting-system.vercel.app/methodology)** · **[Calibration](https://2026-world-cup-forecasting-system.vercel.app/calibration)**

---

## How it works

Before every match, the pipeline generates win/draw/loss probabilities and a most-likely scoreline, then writes a timestamped, locked prediction to the database. After the match, the result is pulled in automatically and the prediction is scored.

The headline metric is the **Brier score**, not accuracy. Accuracy is a vanity number in forecasting; what matters is calibration. A model that says "70% home win" should be right about 70% of the time across all such calls.

### Model (v1)

1. **Poisson regression** estimates expected goals for each team from these features:
   - Rolling attacking strength (last 10 matches)
   - Rolling defensive strength (last 10 matches)
   - Opponent's defensive strength
   - A time-varying Elo rating computed from the full match history itself (every team, margin-of-victory multiplier), which bakes in strength of schedule
   - Elo difference vs the opponent
   - Home / away / neutral venue

   Training samples are weighted by competition: a World Cup match counts more than a qualifier, which counts more than a friendly.

2. **Monte Carlo simulation** (10,000 trials) samples Poisson goals for both teams and counts win/draw/loss frequencies. For validation, the same probabilities are computed analytically (exact, no sampling noise).

3. **Tournament simulation**: the whole World Cup (groups, best-third-place routing, full knockout wiring) is simulated 5,000 times daily, conditioned on results already played, producing each team's odds of winning its group, reaching each round, and lifting the trophy.

Trained on internationals before 2024 and validated on 2024 to 2025 as a true hold-out:

| Metric | v1 (form only) | v2 (current) |
|---|---|---|
| Brier score (hold-out) | 0.1925 | **0.1715** |
| Baseline (predict base rates) | 0.2121 | 0.2121 |
| Improvement over baseline | +9.2% | **+19.1%** |

Training set: 49,318 internationals (1872 to 2026). Parked for later: bivariate Poisson (correlated scoring), gradient boosting, days of rest, head-to-head.

### Two kinds of success rate

The site separates two different bets, each with its own number:
- **Outcome** (win/draw/loss), graded by Brier score and an outcome hit rate.
- **Exact scoreline**, the modal Poisson score, which is hard by nature and reported on its own.

### Immutability guarantee

The `predictions` table has a database-level trigger that rejects any update or delete once `match_kickoff` has passed (it allows only the post-match Brier score to be filled in). Application code cannot override this; it is enforced in Postgres. This is the spine of the credibility pitch.

---

## Pages

- **Home**: upcoming matches with locked probabilities and the current Brier score
- **Groups**: all 12 groups with flags and per-match forecasts
- **Bracket**: the real knockout tree (centered, line-connected), slots filling in as the group stage resolves
- **Predicted**: title odds for every team, champion odds tracked day by day, predicted group standings, and the most likely bracket from 5,000 daily tournament simulations
- **Match detail**: probabilities, predicted scoreline, and a chart of how the odds moved over time
- **Calibration**: reliability diagram and success-rate breakdown
- **Methodology**: the model explained plainly, then in technical depth

The site auto-refreshes every 60 seconds and redeploys on every push.

---

## Stack

| Layer | Tech |
|---|---|
| Modeling and pipeline | Python (scikit-learn, pandas, scipy) |
| Database | Postgres on Supabase |
| Frontend | Next.js 16 (App Router), Tailwind CSS v4 |
| Data access | Server Components query Postgres directly (node-postgres) |
| Frontend host | Vercel |
| Scheduled jobs | GitHub Actions |
| API (optional) | FastAPI (`backend/`) |

The frontend reads the database directly from Server Components, so no separate backend host is required to run the site. The FastAPI app is available as a standalone API layer.

---

## Data sources

All free and public. See [docs/data-sources.md](docs/data-sources.md).

- **History**: martj42 international results (1872 to present), via GitHub raw CSV
- **Fixtures and live results**: openfootball/worldcup.json
- **Elo ratings**: eloratings.net

The canonical join key across sources is the FIFA 3-letter code; the `teams` table carries per-source name aliases to reconcile spellings like "United States" vs "USA".

---

## Automation

Two GitHub Actions workflows keep the system running on its own:

- **Lock Predictions** (daily, 06:00 UTC): locks forecasts for matches in the next 48 hours, snapshots the odds for the drift charts, and re-simulates the full tournament (5,000 runs, conditioned on results so far).
- **Update Results** (every 3 hours): fetches finished scores from openfootball and computes the Brier score for each scored prediction.

---

## Project structure

```
.
├── pipeline/              # Python: data, model, scheduled jobs
│   ├── data/              # loaders (history, fixtures, Elo) + feature engineering
│   ├── model/            # Poisson regression + Monte Carlo + training
│   └── jobs/              # lock, fetch results, score, snapshot odds
├── backend/               # FastAPI app (optional API layer)
├── frontend/              # Next.js app (the live site)
│   └── src/
│       ├── app/           # pages: home, groups, bracket, match, calibration, methodology
│       ├── components/
│       └── lib/           # db access, queries, flags
├── db/
│   ├── schema.sql         # tables + immutability trigger
│   ├── seed_teams.sql     # cross-source team-name aliases
│   └── migrations/        # prediction_history (odds over time)
└── .github/workflows/     # lock-predictions.yml, update-results.yml
```

---

## Running locally

See [docs/setup.md](docs/setup.md).
