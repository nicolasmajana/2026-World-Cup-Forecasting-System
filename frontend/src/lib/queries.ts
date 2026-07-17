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

export type KnockoutSlot = {
  match_num: number;
  home_team: string | null;
  away_team: string | null;
  home_goals: number | null;
  away_goals: number | null;
};

/** Resolved teams and scores for each knockout fixture, keyed by the stable
 * openfootball match number. Slots fill in as resolve_knockout.py writes real
 * teams into `fixtures`; the bracket reads this to replace its slot labels. */
export async function getKnockoutSlots(): Promise<KnockoutSlot[]> {
  return query<KnockoutSlot>(
    `SELECT f.match_num,
            ht.name AS home_team, at.name AS away_team,
            f.home_goals, f.away_goals
     FROM fixtures f
     LEFT JOIN teams ht ON ht.id = f.home_team_id
     LEFT JOIN teams at ON at.id = f.away_team_id
     WHERE f.stage <> 'group' AND f.match_num IS NOT NULL`,
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

export type ScorelineAccuracy = {
  played: number;
  exact_hits: number;
  outcome_hits: number;
};

/**
 * Success rate of the *exact predicted scoreline* (and, separately, the
 * outcome) vs. actual results. The predicted scoreline is the modal Poisson
 * scoreline: floor(xg) for each side. Exact-score hits are rare by nature, so
 * this is reported on its own, distinct from the Brier score for W/D/L.
 */
export async function getScorelineAccuracy(): Promise<ScorelineAccuracy> {
  const rows = await query<ScorelineAccuracy>(
    `SELECT
       COUNT(*) FILTER (WHERE f.home_goals IS NOT NULL)::int AS played,
       COUNT(*) FILTER (
         WHERE f.home_goals IS NOT NULL
           AND round(p.xg_home) = f.home_goals
           AND round(p.xg_away) = f.away_goals
       )::int AS exact_hits,
       COUNT(*) FILTER (
         WHERE f.home_goals IS NOT NULL
           AND sign(p.xg_home - p.xg_away) = sign(f.home_goals - f.away_goals)
       )::int AS outcome_hits
     FROM predictions p
     JOIN fixtures f ON f.id = p.fixture_id`,
  );
  return rows[0] ?? { played: 0, exact_hits: 0, outcome_hits: 0 };
}

export type TeamOdds = {
  code: string;
  name: string;
  champion: number;
  final: number;
  semifinal: number;
  quarterfinal: number;
  r16: number;
  group_winner: number;
};

export type PredictedMatch = {
  num: number;
  home: string;
  away: string;
  winner: string;
  home_pct: number;
  away_pct: number;
  half: "L" | "R" | "C";
};

export type GroupStandingRow = {
  pos: number;
  code: string;
  name: string;
  w: number;
  d: number;
  l: number;
  gf: number;
  ga: number;
  gd: number;
  pts: number;
  qualified: boolean;
  third: boolean;
};

export type PredictedGroup = { name: string; teams: GroupStandingRow[] };

export type TournamentSim = {
  simulated_at: string;
  n_sims: number;
  team_odds: TeamOdds[];
  predicted_bracket: {
    champion: string | null;
    groups: PredictedGroup[];
    rounds: { key: string; label: string; matches: PredictedMatch[] }[];
  };
};

/** The latest full-tournament Monte Carlo simulation. */
export async function getTournamentSim(): Promise<TournamentSim | null> {
  const rows = await query<TournamentSim>(
    `SELECT simulated_at, n_sims, team_odds, predicted_bracket
     FROM tournament_sim ORDER BY simulated_at DESC LIMIT 1`,
  );
  return rows[0] ?? null;
}

export type ChampionHistory = {
  columns: string[]; // one ISO timestamp per day (the latest run that day)
  teams: { code: string; name: string; values: (number | null)[] }[];
};

/** Champion probability per team over time: one column per day (the latest
 * simulation that day), so you can watch the odds move as results come in.
 * Covers every team that ever had a title chance; once the column count
 * outgrows maxCols, the first day is kept and the rest are the most recent
 * days, so the initial odds always stay visible for comparison. */
export async function getChampionHistory(
  topN = 48,
  maxCols = 9,
): Promise<ChampionHistory> {
  let rows = await query<{ simulated_at: string; team_odds: TeamOdds[] }>(
    `SELECT DISTINCT ON (date_trunc('day', simulated_at AT TIME ZONE 'America/New_York'))
            simulated_at, team_odds
     FROM tournament_sim
     ORDER BY date_trunc('day', simulated_at AT TIME ZONE 'America/New_York'),
              simulated_at DESC`,
  );
  if (rows.length === 0) return { columns: [], teams: [] };
  if (rows.length > maxCols) {
    rows = [rows[0], ...rows.slice(-(maxCols - 1))];
  }

  const latest = rows[rows.length - 1];
  const top = [...latest.team_odds]
    .filter((t) => rows.some((r) => {
      const e = r.team_odds.find((o) => o.code === t.code);
      return e != null && e.champion > 0;
    }))
    .sort((a, b) => b.champion - a.champion)
    .slice(0, topN);

  return {
    columns: rows.map((r) => r.simulated_at),
    teams: top.map((t) => ({
      code: t.code,
      name: t.name,
      values: rows.map((r) => {
        const e = r.team_odds.find((o) => o.code === t.code);
        return e ? e.champion : null;
      }),
    })),
  };
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

// ── Prediction vs reality ─────────────────────────────────────────

export type RoundComparison = {
  key: string;
  label: string;
  slots: number;       // how many teams the round holds
  resolved: number;    // how many of those slots are actually known
  hits: number;        // actual teams the initial sim had in its top-`slots`
  predicted: string[]; // initial top-`slots` team names
  actual: string[];    // actual team names (so far)
};

export type TournamentComparison = {
  initial_at: string;
  rounds: RoundComparison[];
  predicted_champion: string | null;
  actual_champion: string | null;
};

const ROUND_DEFS = [
  { key: "r16", label: "Reach knockouts", slots: 32, stage: "r32" },
  { key: "quarterfinal", label: "Reach quarter-finals", slots: 8, stage: "qf" },
  { key: "semifinal", label: "Reach semi-finals", slots: 4, stage: "sf" },
  { key: "final", label: "Reach the final", slots: 2, stage: "f" },
] as const;

/** Compare the initial (pre-tournament) simulation against what actually
 * happened: for each knockout round, the initial top-N teams by reach
 * probability vs the teams that really got there. Builds up live as slots
 * resolve; complete after the final. */
export async function getTournamentComparison(): Promise<TournamentComparison | null> {
  // The "initial" prediction: the last simulation before the opening kickoff.
  const sims = await query<{ simulated_at: string; team_odds: TeamOdds[] }>(
    `SELECT simulated_at, team_odds FROM tournament_sim
     WHERE simulated_at < (SELECT min(kickoff_utc) FROM fixtures)
     ORDER BY simulated_at DESC LIMIT 1`,
  );
  if (sims.length === 0) return null;
  const initial = sims[0];

  // Actual participants per knockout stage (filled in by the resolver), and
  // the champion once the final has a result.
  const stageRows = await query<{ stage: string; name: string; code: string }>(
    `SELECT f.stage, t.name, t.fifa_code AS code
     FROM fixtures f
     JOIN teams t ON t.id IN (f.home_team_id, f.away_team_id)
     WHERE f.stage <> 'group'
     GROUP BY f.stage, t.name, t.fifa_code`,
  );
  const champRows = await query<{ name: string }>(
    `SELECT CASE WHEN f.home_goals > f.away_goals THEN ht.name
                 WHEN f.away_goals > f.home_goals THEN at.name END AS name
     FROM fixtures f
     JOIN teams ht ON ht.id = f.home_team_id
     JOIN teams at ON at.id = f.away_team_id
     WHERE f.match_num = 104 AND f.home_goals IS NOT NULL`,
  );

  const byStage = new Map<string, { name: string; code: string }[]>();
  for (const r of stageRows) {
    if (!byStage.has(r.stage)) byStage.set(r.stage, []);
    byStage.get(r.stage)!.push(r);
  }

  const rounds: RoundComparison[] = ROUND_DEFS.map((d) => {
    const predicted = [...initial.team_odds]
      .sort((a, b) => (b[d.key] as number) - (a[d.key] as number))
      .slice(0, d.slots);
    const predictedCodes = new Set(predicted.map((t) => t.code));
    const actual = byStage.get(d.stage) ?? [];
    return {
      key: d.key,
      label: d.label,
      slots: d.slots,
      resolved: actual.length,
      hits: actual.filter((t) => predictedCodes.has(t.code)).length,
      predicted: predicted.map((t) => t.name),
      actual: actual.map((t) => t.name),
    };
  });

  const topChamp = [...initial.team_odds].sort((a, b) => b.champion - a.champion)[0];
  return {
    initial_at: initial.simulated_at,
    rounds,
    predicted_champion: topChamp?.name ?? null,
    actual_champion: champRows[0]?.name ?? null,
  };
}

// ── Results log ───────────────────────────────────────────────────

export type ResultLogRow = {
  fixture_id: number;
  kickoff_utc: string;
  stage: string;
  group_name: string | null;
  home_team: string;
  away_team: string;
  home_goals: number;
  away_goals: number;
  p_home_win: string | null;
  p_draw: string | null;
  p_away_win: string | null;
  xg_home: string | null;
  xg_away: string | null;
  locked_at: string | null;
  brier_score: string | null;
};

export type PendingMatch = {
  fixture_id: number;
  kickoff_utc: string;
  stage: string;
  group_name: string | null;
  home_team: string;
  away_team: string;
  p_home_win: string | null;
  p_draw: string | null;
  p_away_win: string | null;
  xg_home: string | null;
  xg_away: string | null;
  minutes_since_kickoff: number;
};

/** Matches that have kicked off but have no recorded result yet (the openfootball
 * feed publishes scores with a delay). Newest kickoff first. */
export async function getPendingResults(): Promise<PendingMatch[]> {
  return query<PendingMatch>(
    `SELECT f.id AS fixture_id, f.kickoff_utc, f.stage, f.group_name,
            ht.name AS home_team, at.name AS away_team,
            p.p_home_win, p.p_draw, p.p_away_win, p.xg_home, p.xg_away,
            EXTRACT(EPOCH FROM (now() - f.kickoff_utc)) / 60 AS minutes_since_kickoff
     FROM fixtures f
     JOIN teams ht ON ht.id = f.home_team_id
     JOIN teams at ON at.id = f.away_team_id
     LEFT JOIN predictions p ON p.fixture_id = f.id
     WHERE f.home_goals IS NULL AND f.kickoff_utc < now()
     ORDER BY f.kickoff_utc DESC`,
  );
}

/** Every played match with its locked pre-kickoff prediction, newest first. */
export async function getResultsLog(): Promise<ResultLogRow[]> {
  return query<ResultLogRow>(
    `SELECT f.id AS fixture_id, f.kickoff_utc, f.stage, f.group_name,
            ht.name AS home_team, at.name AS away_team,
            f.home_goals, f.away_goals,
            p.p_home_win, p.p_draw, p.p_away_win, p.xg_home, p.xg_away,
            p.locked_at, p.brier_score
     FROM fixtures f
     JOIN teams ht ON ht.id = f.home_team_id
     JOIN teams at ON at.id = f.away_team_id
     LEFT JOIN predictions p ON p.fixture_id = f.id
     WHERE f.home_goals IS NOT NULL
     ORDER BY f.kickoff_utc DESC`,
  );
}
