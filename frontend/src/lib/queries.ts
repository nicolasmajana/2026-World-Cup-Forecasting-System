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
