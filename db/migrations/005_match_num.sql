-- Stable openfootball match number on fixtures.
--
-- The match_id slug embeds team labels ("2026-06-28-2A-2B"), and openfootball
-- rewrites those labels into real team names as the bracket resolves, which
-- would break slug matching for knockout results. The numeric match id (73,
-- 74, ... ; Final = 103, third place = 104) never changes, so results and
-- team resolution key on it instead.

ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS match_num INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fixtures_match_num
    ON fixtures(match_num) WHERE match_num IS NOT NULL;
