-- Stores the latest full-tournament Monte Carlo simulation.
-- One row per run; the frontend reads the most recent.

CREATE TABLE IF NOT EXISTS tournament_sim (
    id                 SERIAL PRIMARY KEY,
    simulated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    n_sims             INTEGER     NOT NULL,
    model_run_id       INTEGER     REFERENCES model_runs(id),
    team_odds          JSONB       NOT NULL,  -- per-team round/title probabilities
    predicted_bracket  JSONB       NOT NULL   -- the single most-likely path to the final
);
