-- Let finished 2026 World Cup results feed the training data.
--
-- WC results land in `fixtures` from fetch_results.py, but the model trains on
-- `historical_matches`, so a team's rolling form and Elo never moved with its
-- tournament games. promote_results.py copies each finished fixture into
-- historical_matches; this partial unique index makes that copy idempotent
-- (one promoted row per fixture) so the every-3h job can re-run safely.
--
-- Scoped to source = 'openfootball-wc2026' so it never collides with the
-- 49k martj42 rows (two teams can legitimately meet twice on a date in that
-- historical set).

CREATE UNIQUE INDEX IF NOT EXISTS idx_historical_wc2026_unique
    ON historical_matches(match_date, home_team_id, away_team_id)
    WHERE source = 'openfootball-wc2026';
