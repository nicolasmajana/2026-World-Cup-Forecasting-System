# WC 2026 Forecasting System — Claude Context

## What this is
Live probabilistic forecasting for the 2026 FIFA World Cup. The core pitch: every prediction is locked with a timestamp before kickoff and is immutable after the match starts. Public accountability — anyone can verify what the model said before the ball was kicked.

Portfolio project targeting the Aug/Sep 2026 internship cycle. Colombia angle is intentional.

## Architecture
```
Python pipeline  →  FastAPI backend  →  Supabase (Postgres)
                                              ↑
                  Next.js frontend ───────────┘
                  (Vercel)

GitHub Actions: morning job (lock predictions) + polling job (update scores/metrics)
Backend host: Railway
```

## Model (v1 — keep it simple until pipeline is stable)
- **Input features (~10):** rolling attacking strength, rolling defensive strength (last 10 games each), FIFA Elo, home/away/neutral indicator, days of rest, confederation, head-to-head record
- **Step 1:** Poisson regression → predicted expected goals (xG) for each team
- **Step 2:** Monte Carlo, 10,000 trials, sample Poisson(λ) for each team, count win/draw/loss
- **Output:** P(home win), P(draw), P(away win), expected scoreline
- **Validation metric:** Brier score (NOT accuracy — accuracy is a vanity metric for forecasting)
- **Train/val split:** train on pre-2024 internationals, validate on 2024–2025

Parked for later: bivariate Poisson (correlated scoring), gradient boosting. Ship simple first.

## Database schema
Five tables: `teams`, `historical_matches`, `fixtures`, `predictions`, `model_runs`.

The `predictions` table is append-only and has a DB-level constraint preventing updates after `match_kickoff`. This immutability is the spine of the credibility pitch — enforce it at the DB layer, not just in application code.

## Data sources
- Kaggle international football results dataset (historical backbone)
- FBref match stats via `soccerdata` Python package
- FIFA rankings
- Official 2026 fixture list (kickoff times, venues, group assignments)

## Frontend pages (Next.js + Tailwind + shadcn/ui)
1. **Home** — upcoming matches with locked probabilities, current Brier score
2. **Bracket** — tournament bracket with advance probabilities
3. **Match detail** — pre-match: prediction + feature breakdown. Post-match: what happened vs. what was predicted
4. **Calibration** — reliability diagram, Brier score over time
5. **Methodology** — explain the model to a smart non-statistician, then layer technical depth. This is the recruiter page.

## Key conventions
- Predictions are written by the pipeline, never by hand
- `predictions.locked_at` is set by the morning GitHub Action, never updated
- Brier score is the single headline metric everywhere in the UI
- Commit messages should tell the story — write them like a portfolio, not a changelog

## Dev setup
See `docs/setup.md` for local environment instructions.
