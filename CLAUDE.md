# WC 2026 Forecasting System - Claude Context

## What this is
Live probabilistic forecasting for the 2026 FIFA World Cup. The core pitch: every prediction is locked with a timestamp before kickoff and is immutable after the match starts. Public accountability: anyone can verify what the model said before the ball was kicked.

Portfolio project targeting the Aug/Sep 2026 internship cycle. Colombia angle is intentional.

**Live site:** https://2026-world-cup-forecasting-system.vercel.app/
**Repo:** https://github.com/nicolasmajana/2026-World-Cup-Forecasting-System

## Architecture (as deployed)
```
Python pipeline (GitHub Actions)  →  Supabase (Postgres)
                                          ↑
              Next.js frontend ───────────┘  (Server Components query
              (Vercel, auto-deploy on push)   Postgres directly via pg)
```
- The FastAPI app in `backend/` exists as an optional API layer but is NOT deployed; the frontend does not use it.
- Connection pooling matters: the frontend uses Supabase's TRANSACTION pooler (port 6543, serverless-friendly); the pipeline and Actions use the SESSION pooler (port 5432, capped at 15 clients). Mixing these up causes EMAXCONNSESSION errors.
- Local scripts: run with `pipeline/.venv` and `PYTHONUTF8=1` (Windows console chokes on Unicode otherwise). When the session pooler is flaky, point DATABASE_URL at port 6543.

## Model (v2, "poisson-v2")
- **Features:** rolling attack/defense strength (last 10 games), opponent defense, self-computed time-varying Elo, Elo difference, venue indicator.
- **Elo is computed from the match history itself** (every team, margin multiplier, 100-pt home advantage) in `features.py add_elo_columns()`. The external eloratings.net loader (`load_elo.py`) and `teams.fifa_elo` are vestigial; the model does not use them.
- **Training:** Poisson regression with competition sample weights (World Cup 1.6, qualifiers 1.2, friendlies 0.5), trained on pre-2024 internationals, validated on 2024-2025.
- **Hold-out Brier: 0.1715 vs 0.2121 baseline (+19.1%).** v1 (form-only) was 0.1925; the jump came from real Elo coverage across all 49k training matches.
- **Outputs:** 10,000-trial Monte Carlo per match (W/D/L probabilities, xG); exact analytic probabilities (`predict_outcome_probs`) for vectorized validation.
- Validation metric is Brier score, NOT accuracy. Keep changes only if they lower hold-out Brier.
- Parked: bivariate Poisson, gradient boosting, days of rest, head-to-head, confederation.

## Database
Seven tables: `teams`, `historical_matches`, `fixtures`, `predictions`, `model_runs`, `prediction_history` (append-only daily odds snapshots for the drift charts), `tournament_sim` (full-tournament Monte Carlo output: per-team round/title odds + predicted bracket + predicted group tables).

`predictions` is append-only and a DB trigger blocks UPDATE/DELETE after `match_kickoff` (only the post-match brier_score fill is allowed). The trigger must RETURN OLD for pre-kickoff deletes (a BEFORE DELETE returning NEW/NULL silently cancels the delete; that bug bit us once). Schema in `db/schema.sql`, migrations in `db/migrations/`.

## Pipeline jobs (`pipeline/jobs/`)
Two GitHub Actions workflows (secret: `DATABASE_URL`, session pooler):
- **lock-predictions.yml** (daily 06:00 UTC): `lock_predictions.py` (lock fixtures in next 48h) → `snapshot_odds.py` (re-train, snapshot current odds for every upcoming fixture, idempotent per day) → `simulate_tournament.py 5000` (full-tournament Monte Carlo, conditioned on actual group results AND decisive knockout results; stores team odds + predicted bracket).
- **update-results.yml** (every 3h): `resolve_knockout.py` (fill knockout team slots as the feed names them; keys on `fixtures.match_num`) → `fetch_results.py` (openfootball score.ft → fixtures, matched by match_num for knockouts, slug for groups, warns loudly on slug misses; also captures score.p as `home_pens`/`away_pens` when a knockout match is level at FT, so `simulate_tournament.py` can condition the sim on the actual shootout winner) → `promote_results.py` (copy finished fixtures into `historical_matches` as 'World Cup' rows, weight 1.6, neutral venue; idempotent via the migration 006 partial unique index, so the daily re-train in snapshot/sim now sees WC form) → `update_results.py` (Brier per scored prediction).
- `backfill_predictions.py` is the one-off that seeded the initial 72 predictions.
- The knockout STRUCTURE is hardcoded in `pipeline/data/bracket_wiring.py` (and mirrored in `frontend/src/lib/bracket2026.ts`); never parse it from the live feed, which rewrites slot refs into team names as the bracket resolves. `fixtures.match_num` (73-102, Final=103, third place=104) is the stable key; group matches carry no number in the feed and keep slug matching.

## Data sources (see docs/data-sources.md)
- **History:** martj42 results.csv via GitHub raw (CC0). 49,318 matches loaded.
- **2026 fixtures + live results:** openfootball/worldcup.json (CC0). Times are local-with-offset, normalized to UTC. Round labels are singular ("Quarter-final"); knockout slugs use slot refs (W89) so knockout results need a resolver (NOT yet built).
- **Canonical join key is `fifa_code`**; `teams` carries per-source alias columns. The seeded alias MUST match the exact martj42 spelling or you get a duplicate empty team (bit us with Bosnia and Ivory Coast).

## Frontend (Next.js 16, Tailwind v4, App Router)
Six tabs + detail page, all reading Postgres directly from Server Components (`src/lib/db.ts`, `queries.ts`):
1. **Home**: upcoming matches, locked probabilities, Brier headline
2. **Groups**: 12 groups, flags, per-match forecasts
3. **Bracket**: real knockout tree (slot labels fill in as groups resolve), centered with connector lines
4. **Predicted**: champion banner, title-odds bars, champion-odds-over-time table (every team with a title chance, one column per day, first column = pre-tournament), prediction-vs-reality report card (initial sim's top-N per round vs actual, success %), reach-round table, predicted group standings, predicted bracket
5. **Results**: log of every played match, locked prediction next to the actual score, pick hit/miss, per-match Brier
6. **Calibration**: reliability diagram, Brier + outcome hit rate + exact-score rate
7. **Methodology**: plain-language then technical (the recruiter page)
- `/match/[id]`: probabilities, predicted scoreline, odds-drift chart
- Bracket layout: matches MUST be ordered by bracket-tree position (`ORDER` in `lib/bracket2026.ts`), not match number; the 2026 wiring pairs non-adjacent numbers.
- Colors (style tile): Tomato #ff4b01 = home team, Sun #faa000 = away team, Ink #3e4749 = draw/neutral, Mute #879499. Flags via flagcdn.com (`lib/flags.ts`); flag emoji do not render on Windows.
- All times shown in US Eastern (`lib/datetime.ts`).
- AutoRefresh re-fetches dynamic routes every 60s.

## Key conventions
- Predictions are written by the pipeline, never by hand
- `predictions.locked_at` set at lock time, never updated
- Brier score is the single headline metric everywhere
- NO em dashes anywhere (UI copy, comments, commits, docs)
- Commit messages tell the story, written like a portfolio

## Known gaps / next steps
- Once knockout teams resolve, predictions are locked by the next 06:00 UTC run; a matchup decided less than a day before kickoff still gets locked in time because all knockout kickoffs are afternoon/evening UTC

## Dev setup
See `docs/setup.md`.
