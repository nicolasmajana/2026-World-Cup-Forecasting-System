-- Odds drift over time.
--
-- `predictions` holds the ONE official, locked, immutable prediction per
-- fixture. But the model re-evaluates upcoming matches every morning, and we
-- want to chart how the odds move as new results and (later) news come in.
-- This append-only table stores every snapshot; nothing here is ever updated.

CREATE TABLE IF NOT EXISTS prediction_history (
    id            SERIAL PRIMARY KEY,
    fixture_id    INTEGER     NOT NULL REFERENCES fixtures(id),
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_run_id  INTEGER     REFERENCES model_runs(id),

    p_home_win    NUMERIC(5,4) NOT NULL,
    p_draw        NUMERIC(5,4) NOT NULL,
    p_away_win    NUMERIC(5,4) NOT NULL,
    xg_home       NUMERIC(4,2) NOT NULL,
    xg_away       NUMERIC(4,2) NOT NULL,

    -- Optional qualitative note attached to this snapshot (e.g. "Mbappé out").
    note          TEXT
);

CREATE INDEX IF NOT EXISTS idx_pred_history_fixture
    ON prediction_history(fixture_id, captured_at);
