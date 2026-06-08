-- Fix: the immutability trigger silently cancelled ALL deletes.
--
-- A BEFORE DELETE trigger that returns NULL cancels the delete. The original
-- function ended with `RETURN NEW`, and NEW is NULL for DELETE, so even
-- pre-kickoff predictions could never be deleted. The intent is: block
-- mutation only AFTER kickoff. This returns OLD for allowed deletes.

CREATE OR REPLACE FUNCTION prevent_prediction_mutation()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow filling in brier_score after the match (it didn't exist at lock).
    IF TG_OP = 'UPDATE'
       AND OLD.brier_score IS NULL
       AND OLD.p_home_win = NEW.p_home_win
       AND OLD.p_draw = NEW.p_draw
       AND OLD.p_away_win = NEW.p_away_win
       AND OLD.xg_home = NEW.xg_home
       AND OLD.xg_away = NEW.xg_away
       AND OLD.features = NEW.features
    THEN
        RETURN NEW;
    END IF;

    IF now() >= OLD.match_kickoff THEN
        RAISE EXCEPTION
            'Prediction % is locked - match kicked off at %. Cannot mutate after kickoff.',
            OLD.id, OLD.match_kickoff;
    END IF;

    -- Before kickoff: allow. Return the right row for the op.
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
