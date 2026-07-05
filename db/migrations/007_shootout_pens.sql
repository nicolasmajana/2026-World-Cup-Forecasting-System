-- Condition the tournament sim on penalty-shootout winners.
--
-- A knockout match drawn at full time is decided on penalties, but
-- fetch_results.py only ever wrote score.ft, so a shootout draw left
-- home_goals = away_goals with no way to tell who actually advanced.
-- simulate_tournament.py's load_actual_ko_winners() only derives a winner
-- from a decisive FT scoreline, so a shootout match kept being sampled as
-- open in the Monte Carlo even after it was played.
--
-- These columns hold the penalty score (openfootball score.p) so the
-- winner can be derived when ft is level. NULL for every match that isn't
-- a shootout.

ALTER TABLE fixtures
    ADD COLUMN IF NOT EXISTS home_pens SMALLINT,
    ADD COLUMN IF NOT EXISTS away_pens SMALLINT;
