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
from data.features import compute_team_rolling_strengths, build_match_features  # noqa: E402
from model.poisson_model import PoissonGoalModel  # noqa: E402


def latest_strength(rolling, code):
    try:
        sub = rolling.xs(code, level="team_code").dropna()
        if sub.empty:
            return None
        last = sub.iloc[-1]
        return float(last["attack_strength"]), float(last["defense_strength"])
    except KeyError:
        return None


def main():
    print("Loading data + training model…")
    hist = load_historical_from_db()
    rolling = compute_team_rolling_strengths(hist)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT fifa_code, fifa_elo FROM teams WHERE fifa_elo IS NOT NULL")
        elo_map = {c: e for c, e in cur.fetchall()}
        cur.execute("SELECT id FROM model_runs ORDER BY run_at DESC LIMIT 1")
        row = cur.fetchone()
        model_run_id = row[0] if row else None

    feats = build_match_features(hist, elo_map, rolling)
    model = PoissonGoalModel().fit(feats)

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
        hs = latest_strength(rolling, fx["home_code"])
        as_ = latest_strength(rolling, fx["away_code"])
        if hs is None or as_ is None:
            skipped += 1
            continue
        home_f = {"attack_strength": hs[0], "defense_strength": hs[1],
                  "opp_defense_strength": as_[1],
                  "elo": elo_map.get(fx["home_code"], 1500), "venue_enc": 0}
        away_f = {"attack_strength": as_[0], "defense_strength": as_[1],
                  "opp_defense_strength": hs[1],
                  "elo": elo_map.get(fx["away_code"], 1500), "venue_enc": 0}
        pred = model.predict_match(home_f, away_f)

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
