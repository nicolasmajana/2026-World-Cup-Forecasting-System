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
from data.features import compute_team_rolling_strengths, build_match_features  # noqa: E402
from model.poisson_model import PoissonGoalModel  # noqa: E402

MIGRATION = os.path.join(
    os.path.dirname(__file__), "..", "..", "db", "migrations",
    "002_prediction_history.sql",
)


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
    conn = get_connection()
    with conn.cursor() as cur:
        with open(MIGRATION) as f:
            cur.execute(f.read())  # ensure table exists
        conn.commit()
        cur.execute("SELECT fifa_code, fifa_elo FROM teams WHERE fifa_elo IS NOT NULL")
        elo_map = {c: e for c, e in cur.fetchall()}
        cur.execute("SELECT id FROM model_runs ORDER BY run_at DESC LIMIT 1")
        row = cur.fetchone()
        model_run_id = row[0] if row else None

    print("Training model on latest data...")
    hist = load_historical_from_db()
    rolling = compute_team_rolling_strengths(hist)
    model = PoissonGoalModel().fit(build_match_features(hist, elo_map, rolling))

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
        hs = latest_strength(rolling, fx["home_code"])
        as_ = latest_strength(rolling, fx["away_code"])
        if hs is None or as_ is None:
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
