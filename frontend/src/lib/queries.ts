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

export type OddsSnapshot = {
  captured_at: string;
  p_home_win: string;
  p_draw: string;
  p_away_win: string;
  note: string | null;
};

/** One fixture's full detail (teams, prediction, result). */
export async function getMatchDetail(fixtureId: number): Promise<FixtureRow | null> {
  const rows = await query<FixtureRow>(
    `${FIXTURE_SELECT} WHERE f.id = $1`,
    [fixtureId],
  );
  return rows[0] ?? null;
}

/** Time series of odds for one fixture (for the drift chart). */
export async function getOddsHistory(fixtureId: number): Promise<OddsSnapshot[]> {
  return query<OddsSnapshot>(
    `SELECT captured_at, p_home_win, p_draw, p_away_win, note
     FROM prediction_history
     WHERE fixture_id = $1
     ORDER BY captured_at`,
    [fixtureId],
  );
}

export type ReliabilityBin = {
  bucket: number;
  mean_predicted: number;
  observed_freq: number;
  n: number;
};

/** Reliability-diagram bins: predicted vs. observed home-win frequency. */
export async function getReliabilityBins(): Promise<ReliabilityBin[]> {
  return query<ReliabilityBin>(
    `SELECT width_bucket(p.p_home_win, 0, 1, 10) AS bucket,
            AVG(p.p_home_win)::float AS mean_predicted,
            AVG(CASE WHEN f.home_goals > f.away_goals THEN 1.0 ELSE 0.0 END)::float
              AS observed_freq,
            COUNT(*)::int AS n
     FROM predictions p
     JOIN fixtures f ON f.id = p.fixture_id
     WHERE f.home_goals IS NOT NULL
     GROUP BY bucket ORDER BY bucket`,
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
