"""
Daily odds snapshot for the drift charts.

Re-trains the model on the latest data and records the model's CURRENT odds
for every upcoming fixture (both teams known, not yet played) into
prediction_history. This builds the "how the odds moved" time series: the
locked official prediction in `predictions` never changes, but this captures
the model's evolving view as Elo refreshes and results come in.

Idempotent per day: a fixture already snapshotted today is skipped.

Usage:
    python pipeline/jobs/snapshot_odds.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection, load_historical_from_db  # noqa: E402
from data.features import (  # noqa: E402
    compute_team_rolling_strengths, add_elo_columns, build_match_features,
    build_fixture_feature_pair,
)
from model.poisson_model import PoissonGoalModel  # noqa: E402

MIGRATION = os.path.join(
    os.path.dirname(__file__), "..", "..", "db", "migrations",
    "002_prediction_history.sql",
)


def main():
    conn = get_connection()
    with conn.cursor() as cur:
        with open(MIGRATION) as f:
            cur.execute(f.read())  # ensure table exists
        conn.commit()
        cur.execute("SELECT id FROM model_runs ORDER BY run_at DESC LIMIT 1")
        row = cur.fetchone()
        model_run_id = row[0] if row else None

    print("Training model on latest data...")
    hist = load_historical_from_db()
    hist, latest_elo = add_elo_columns(hist)
    rolling = compute_team_rolling_strengths(hist)
    feats = build_match_features(hist, rolling)
    model = PoissonGoalModel().fit(feats, sample_weight=feats["weight"].to_numpy())

    fixtures = pd.read_sql(
        """
        SELECT f.id AS fixture_id, ht.fifa_code AS home_code,
               at.fifa_code AS away_code
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        WHERE f.home_goals IS NULL              -- not played yet
          AND f.kickoff_utc > now()
          AND NOT EXISTS (
            SELECT 1 FROM prediction_history h
            WHERE h.fixture_id = f.id AND h.captured_at::date = now()::date
          )
        """,
        conn,
    )
    print(f"{len(fixtures)} fixture(s) to snapshot today.")

    inserted = 0
    for _, fx in fixtures.iterrows():
        pair = build_fixture_feature_pair(
            fx["home_code"], fx["away_code"], rolling, latest_elo
        )
        if pair is None:
            continue
        pred = model.predict_match(pair[0], pair[1])
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO prediction_history
                    (fixture_id, model_run_id, p_home_win, p_draw, p_away_win,
                     xg_home, xg_away)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (int(fx["fixture_id"]), model_run_id, pred["p_home_win"],
                 pred["p_draw"], pred["p_away_win"], pred["xg_home"],
                 pred["xg_away"]),
            )
            inserted += 1
        conn.commit()

    conn.close()
    print(f"Snapshotted odds for {inserted} fixture(s).")


if __name__ == "__main__":
    main()
