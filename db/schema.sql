-- WC 2026 Forecasting System — Database Schema
-- Target: Supabase (Postgres 15)
-- Run this in the Supabase SQL editor to initialize the schema.

-- ─────────────────────────────────────────────
-- Teams  (acts as the canonical dim_team dimension)
--
-- fifa_code is the canonical join key across all data sources. The per-source
-- alias columns let the loaders join martj42 / eloratings / FBref / FIFA data
-- that each spell country names differently (e.g. "United States" vs "USA",
-- "Korea Republic" vs "South Korea"). See docs/data-sources.md.
-- ─────────────────────────────────────────────
CREATE TABLE teams (
    id            SERIAL PRIMARY KEY,
    fifa_code     CHAR(3)      NOT NULL UNIQUE,   -- canonical key: 'COL', 'USA', 'KOR'
    name          TEXT         NOT NULL,           -- display name
    confederation TEXT         NOT NULL,           -- UEFA, CONMEBOL, CONCACAF, CAF, AFC, OFC
    fifa_elo      INTEGER,                         -- latest eloratings.net value

    -- Source-specific name aliases (NULL if same as `name`)
    martj42_name  TEXT,                            -- name as it appears in martj42 results.csv
    elo_name      TEXT,                            -- name as it appears in eloratings.net TSV
    fbref_name    TEXT,                            -- name as it appears on FBref
    fifa_name     TEXT,                            -- official FIFA name (e.g. 'Korea Republic')

    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Lookup helpers for the loaders (join incoming rows by their source spelling)
CREATE INDEX idx_teams_martj42 ON teams(martj42_name);
CREATE INDEX idx_teams_elo     ON teams(elo_name);

-- ─────────────────────────────────────────────
-- Historical matches (training data)
-- ─────────────────────────────────────────────
CREATE TABLE historical_matches (
    id              SERIAL PRIMARY KEY,
    match_date      DATE         NOT NULL,
    home_team_id    INTEGER      NOT NULL REFERENCES teams(id),
    away_team_id    INTEGER      NOT NULL REFERENCES teams(id),
    home_goals      SMALLINT     NOT NULL,
    away_goals      SMALLINT     NOT NULL,
    venue_type      TEXT         NOT NULL CHECK (venue_type IN ('home', 'away', 'neutral')),
    tournament      TEXT,                           -- 'World Cup', 'Friendly', 'Copa America', …
    source          TEXT                            -- 'kaggle', 'fbref', etc.
);

CREATE INDEX idx_historical_home ON historical_matches(home_team_id, match_date);
CREATE INDEX idx_historical_away ON historical_matches(away_team_id, match_date);

-- ─────────────────────────────────────────────
-- 2026 WC fixtures
-- ─────────────────────────────────────────────
CREATE TABLE fixtures (
    id              SERIAL PRIMARY KEY,
    match_id        TEXT         NOT NULL UNIQUE,  -- date-team slug (display/debug)
    match_num       INTEGER      UNIQUE,           -- stable openfootball match number
    kickoff_utc     TIMESTAMPTZ  NOT NULL,
    home_team_id    INTEGER      REFERENCES teams(id),   -- NULL for TBD group-stage qualifiers
    away_team_id    INTEGER      REFERENCES teams(id),
    venue           TEXT,
    city            TEXT,
    country         TEXT,
    stage           TEXT         NOT NULL,          -- 'group', 'r32', 'r16', 'qf', 'sf', 'f'
    group_name      TEXT,                           -- 'A' … 'L', NULL for knockouts
    home_goals      SMALLINT,                       -- filled after match
    away_goals      SMALLINT,
    home_pens       SMALLINT,                       -- shootout score, NULL unless FT was level
    away_pens       SMALLINT,
    result_source   TEXT,                           -- where we pulled the result from
    result_at       TIMESTAMPTZ                     -- when we recorded the result
);

-- ─────────────────────────────────────────────
-- Predictions (append-only, immutable after kickoff)
-- ─────────────────────────────────────────────
CREATE TABLE predictions (
    id              SERIAL PRIMARY KEY,
    fixture_id      INTEGER      NOT NULL REFERENCES fixtures(id),
    model_run_id    INTEGER,                        -- FK added after model_runs table exists
    locked_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    match_kickoff   TIMESTAMPTZ  NOT NULL,          -- denormalized from fixtures for the constraint

    -- Probabilities (must sum to ~1.0)
    p_home_win      NUMERIC(5,4) NOT NULL CHECK (p_home_win BETWEEN 0 AND 1),
    p_draw          NUMERIC(5,4) NOT NULL CHECK (p_draw BETWEEN 0 AND 1),
    p_away_win      NUMERIC(5,4) NOT NULL CHECK (p_away_win BETWEEN 0 AND 1),

    -- Expected scoreline
    xg_home         NUMERIC(4,2) NOT NULL,
    xg_away         NUMERIC(4,2) NOT NULL,

    -- Feature snapshot (JSON so we can display "what drove this" on the match page)
    features        JSONB        NOT NULL,

    -- Brier score filled in after the match
    brier_score     NUMERIC(6,5),

    CONSTRAINT predictions_probabilities_sum
        CHECK (ABS((p_home_win + p_draw + p_away_win) - 1.0) < 0.01),

    -- Only one locked prediction per fixture
    CONSTRAINT predictions_one_per_fixture UNIQUE (fixture_id)
);

-- ─────────────────────────────────────────────
-- THE IMMUTABILITY CONSTRAINT
-- This is enforced at the database layer, not just in application code.
-- Any UPDATE or DELETE on a prediction row after kickoff is rejected.
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION prevent_prediction_mutation()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow brier_score to be filled in after the match (it didn't exist at lock time)
    IF TG_OP = 'UPDATE'
       AND OLD.brier_score IS NULL
       AND OLD.p_home_win = NEW.p_home_win
       AND OLD.p_draw = NEW.p_draw
       AND OLD.p_away_win = NEW.p_away_win
       AND OLD.xg_home = NEW.xg_home
       AND OLD.xg_away = NEW.xg_away
       AND OLD.features = NEW.features
    THEN
        RETURN NEW;  -- only brier_score changed, that's fine
    END IF;

    IF now() >= OLD.match_kickoff THEN
        RAISE EXCEPTION
            'Prediction % is locked - match kicked off at %. Cannot mutate after kickoff.',
            OLD.id, OLD.match_kickoff;
    END IF;

    -- Before kickoff: allow. A BEFORE DELETE trigger must return OLD (returning
    -- NEW, which is NULL for DELETE, would silently cancel the delete).
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER predictions_immutable
    BEFORE UPDATE OR DELETE ON predictions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_prediction_mutation();

-- ─────────────────────────────────────────────
-- Model runs (audit trail)
-- ─────────────────────────────────────────────
CREATE TABLE model_runs (
    id              SERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    model_version   TEXT         NOT NULL,          -- e.g. 'poisson-v1.2'
    train_cutoff    DATE         NOT NULL,           -- last date in training set
    val_brier_score NUMERIC(6,5),                   -- Brier on 2024-2025 hold-out
    n_train_matches INTEGER,
    parameters      JSONB,                           -- model hyperparameters snapshot
    git_sha         TEXT                             -- commit that produced this run
);

-- Wire up the FK now that model_runs exists
ALTER TABLE predictions
    ADD CONSTRAINT predictions_model_run_fk
    FOREIGN KEY (model_run_id) REFERENCES model_runs(id);

-- ─────────────────────────────────────────────
-- Handy view: upcoming predictions with team names
-- ─────────────────────────────────────────────
CREATE VIEW v_upcoming_predictions AS
SELECT
    f.id            AS fixture_id,
    f.kickoff_utc,
    f.stage,
    f.group_name,
    ht.name         AS home_team,
    ht.fifa_code    AS home_code,
    at.name         AS away_team,
    at.fifa_code    AS away_code,
    p.p_home_win,
    p.p_draw,
    p.p_away_win,
    p.xg_home,
    p.xg_away,
    p.locked_at,
    f.home_goals,
    f.away_goals,
    p.brier_score
FROM fixtures f
JOIN teams ht ON ht.id = f.home_team_id
JOIN teams at ON at.id = f.away_team_id
LEFT JOIN predictions p ON p.fixture_id = f.id
WHERE f.kickoff_utc > now() - INTERVAL '3 hours'
ORDER BY f.kickoff_utc;
