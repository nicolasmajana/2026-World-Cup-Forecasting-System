# Data Sources

Confirmed and evaluated for the WC 2026 forecasting system. The decision for each
category is in **bold**.

## 1. Historical match results — TRAINING BACKBONE
**Use: martj42 raw CSV from GitHub.** Public domain (CC0), updated within days of matches,
machine-readable, and the only free source with a neutral-venue flag going back to 1872.

- Direct (no auth): `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Columns: `date, home_team, away_team, home_score, away_score, tournament, city, country, neutral`
- Companion files in same repo: `shootouts.csv`, `goalscorers.csv` (goal-level, optional later)
- Confirmed current through 2026.

## 2. Enriched stats (xG, shots) — FEATURE ENRICHMENT LAYER
**Use: FBref via the `soccerdata` package, for 2018 + 2022 World Cups and post-2017
internationals only.** This is a supplement on top of martj42, not a replacement.

- xG coverage starts 2017–18 season. ~500–600 relevant international matches have xG.
- **License: personal use only** — FBref ToS prohibits commercial redistribution. Fine for a portfolio project; do not resell.
- Rate-limited: don't parallelize. First historical pull ~20–40 min; cached locally afterward.
- League strings: `"INT-FIFA World Cup"`, `"INT-UEFA Nations League"`, `"INT-Copa América"`, etc.

## 3. Elo / rankings — KEY FEATURE
**Use: eloratings.net TSV for historical Elo at match date; Kaggle FIFA rankings CSV as a cross-check.**

- Current: `https://www.eloratings.net/World.tsv`
- Year snapshots (training time series): `https://www.eloratings.net/{YEAR}.tsv` (1901–present)
- Caveat: eloratings uses full country names, NOT codes — must join via the name-mapping table.
- FIFA Kaggle CSV (`country_abrv`) and FIFA JSON API (`countryCode`) both expose the 3-letter code.
- England / Scotland / Wales / Northern Ireland are correctly separate teams — don't merge.

## 4. 2026 fixture list — THE SCHEDULE
**Use: openfootball/worldcup.json as the base; API-Football free tier for live results during the tournament.**

- Base (public domain): `https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json`
- Caveat: times are local-with-offset (e.g. `"13:00 UTC-6"`) — normalize to UTC in the ETL.
- 48 teams, 12 groups (A–L), top 2 + 8 best 3rd-place → Round of 32.
- API-Football: `GET /fixtures?league=1&season=2026`, free tier 100 req/day (enough for live polling).

## Team-name normalization
The biggest operational hazard when joining the four sources. The canonical key is the
**FIFA 3-letter code**. The `teams` table carries per-source alias columns
(`martj42_name`, `elo_name`, `fbref_name`, `fifa_name`) so each loader joins by its own
spelling. Known mismatches are seeded in `db/seed_teams.sql`.
