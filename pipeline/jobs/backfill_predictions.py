"""
One-off backfill: generate and lock a prediction for every 2026 fixture that
has both teams resolved and hasn't been predicted yet. Gives the frontend real
content before the daily morning job takes over.

Safe to re-run: ON CONFLICT (fixture_id) DO NOTHING means existing locked
predictions are never overwritten (and the DB trigger blocks post-kickoff edits).

Usage:
    python pipeline/jobs/backfill_predictions.py
"""

import os
import sys
import json

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection, load_historical_from_db  # noqa: E402
from data.features import (  # noqa: E402
    compute_team_rolling_strengths, add_elo_columns, build_match_features,
    build_fixture_feature_pair,
)
from model.poisson_model import PoissonGoalModel  # noqa: E402


def main():
    print("Loading data + training model…")
    hist = load_historical_from_db()
    hist, latest_elo = add_elo_columns(hist)
    rolling = compute_team_rolling_strengths(hist)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM model_runs ORDER BY run_at DESC LIMIT 1")
        row = cur.fetchone()
        model_run_id = row[0] if row else None

    feats = build_match_features(hist, rolling)
    model = PoissonGoalModel().fit(feats, sample_weight=feats["weight"].to_numpy())

    # Fixtures with both teams resolved and not yet predicted
    fixtures = pd.read_sql(
        """
        SELECT f.id AS fixture_id, f.kickoff_utc,
               ht.fifa_code AS home_code, ht.name AS home,
               at.fifa_code AS away_code, at.name AS away
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN predictions p ON p.fixture_id = f.id
        WHERE p.id IS NULL
        ORDER BY f.kickoff_utc
        """,
        conn,
    )
    print(f"{len(fixtures)} fixture(s) to predict.")

    inserted, skipped = 0, 0
    for _, fx in fixtures.iterrows():
        pair = build_fixture_feature_pair(
            fx["home_code"], fx["away_code"], rolling, latest_elo
        )
        if pair is None:
            skipped += 1
            continue
        pred = model.predict_match(pair[0], pair[1])

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO predictions
                    (fixture_id, model_run_id, match_kickoff,
                     p_home_win, p_draw, p_away_win, xg_home, xg_away, features)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fixture_id) DO NOTHING
                """,
                (int(fx["fixture_id"]), model_run_id, fx["kickoff_utc"],
                 pred["p_home_win"], pred["p_draw"], pred["p_away_win"],
                 pred["xg_home"], pred["xg_away"], json.dumps(pred["features"])),
            )
            inserted += cur.rowcount
        conn.commit()

    conn.close()
    print(f"Inserted {inserted} predictions. Skipped {skipped} (insufficient history).")


if __name__ == "__main__":
    main()
