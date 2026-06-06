import { query } from "./db";

export type MatchPrediction = {
  fixture_id: number;
  kickoff_utc: string;
  stage: string;
  group_name: string | null;
  home_team: string;
  home_code: string;
  away_team: string;
  away_code: string;
  p_home_win: string | null;
  p_draw: string | null;
  p_away_win: string | null;
  xg_home: string | null;
  xg_away: string | null;
  locked_at: string | null;
  home_goals: number | null;
  away_goals: number | null;
  brier_score: string | null;
};

export type CalibrationSummary = {
  scored_matches: number;
  mean_brier: number | null;
};

/** Upcoming fixtures with their locked predictions (next matches first). */
export async function getUpcomingPredictions(
  limit = 30,
): Promise<MatchPrediction[]> {
  return query<MatchPrediction>(
    `SELECT * FROM v_upcoming_predictions
     WHERE p_home_win IS NOT NULL
     ORDER BY kickoff_utc
     LIMIT $1`,
    [limit],
  );
}

/** Headline accuracy: overall Brier score + how many matches it's based on. */
export async function getCalibrationSummary(): Promise<CalibrationSummary> {
  const rows = await query<CalibrationSummary>(
    `SELECT COUNT(*)::int AS scored_matches,
            AVG(brier_score)::float AS mean_brier
     FROM predictions
     WHERE brier_score IS NOT NULL`,
  );
  return rows[0] ?? { scored_matches: 0, mean_brier: null };
}

export type FixtureRow = {
  fixture_id: number;
  kickoff_utc: string;
  stage: string;
  group_name: string | null;
  home_team: string | null;
  home_code: string | null;
  away_team: string | null;
  away_code: string | null;
  p_home_win: string | null;
  p_draw: string | null;
  p_away_win: string | null;
  xg_home: string | null;
  xg_away: string | null;
  home_goals: number | null;
  away_goals: number | null;
};

const FIXTURE_SELECT = `
  SELECT f.id AS fixture_id, f.kickoff_utc, f.stage, f.group_name,
         ht.name AS home_team, ht.fifa_code AS home_code,
         at.name AS away_team, at.fifa_code AS away_code,
         p.p_home_win, p.p_draw, p.p_away_win, p.xg_home, p.xg_away,
         f.home_goals, f.away_goals
  FROM fixtures f
  LEFT JOIN teams ht ON ht.id = f.home_team_id
  LEFT JOIN teams at ON at.id = f.away_team_id
  LEFT JOIN predictions p ON p.fixture_id = f.id
`;

/** All group-stage fixtures (with predictions where available). */
export async function getGroupMatches(): Promise<FixtureRow[]> {
  return query<FixtureRow>(
    `${FIXTURE_SELECT} WHERE f.stage = 'group'
     ORDER BY f.group_name, f.kickoff_utc`,
  );
}

/** All knockout fixtures (teams may be TBD until the bracket resolves). */
export async function getKnockoutMatches(): Promise<FixtureRow[]> {
  return query<FixtureRow>(
    `${FIXTURE_SELECT} WHERE f.stage <> 'group'
     ORDER BY f.kickoff_utc`,
  );
}

/** Metadata about the latest model run (for the footer / methodology hook). */
export async function getLatestModelRun() {
  const rows = await query<{
    model_version: string;
    val_brier_score: string | null;
    n_train_matches: number | null;
    run_at: string;
  }>(
    `SELECT model_version, val_brier_score, n_train_matches, run_at
     FROM model_runs ORDER BY run_at DESC LIMIT 1`,
  );
  return rows[0] ?? null;
}
