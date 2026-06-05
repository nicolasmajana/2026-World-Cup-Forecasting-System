"""
GitHub Actions morning job.
Finds every fixture in the next 48 hours without a locked prediction,
generates one, and writes it to the database.
"""

import json
import os
import sys
import psycopg2
from dotenv import load_dotenv

# Add pipeline root to path when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.loader import get_connection, load_historical_from_db, load_upcoming_fixtures
from data.features import compute_team_rolling_strengths, build_match_features
from model.poisson_model import PoissonGoalModel

load_dotenv()


def load_elo_map(conn) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT fifa_code, fifa_elo FROM teams WHERE fifa_elo IS NOT NULL")
        return {row[0]: row[1] for row in cur.fetchall()}


def get_latest_model_run_id(conn) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM model_runs ORDER BY run_at DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None


def write_prediction(conn, fixture_id: int, kickoff_utc, model_run_id, pred: dict):
    sql = """
        INSERT INTO predictions
            (fixture_id, model_run_id, match_kickoff,
             p_home_win, p_draw, p_away_win, xg_home, xg_away, features)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fixture_id) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            fixture_id,
            model_run_id,
            kickoff_utc,
            pred["p_home_win"],
            pred["p_draw"],
            pred["p_away_win"],
            pred["xg_home"],
            pred["xg_away"],
            json.dumps(pred["features"]),
        ))
    conn.commit()


def main():
    upcoming = load_upcoming_fixtures()
    if upcoming.empty:
        print("No upcoming fixtures need predictions.")
        return

    print(f"Found {len(upcoming)} fixture(s) needing predictions.")

    historical = load_historical_from_db()
    rolling = compute_team_rolling_strengths(historical)

    conn = get_connection()
    elo_map = load_elo_map(conn)
    model_run_id = get_latest_model_run_id(conn)

    # Train model on all historical data
    feature_df = build_match_features(historical, elo_map, rolling)
    model = PoissonGoalModel().fit(feature_df)

    for _, fixture in upcoming.iterrows():
        # Build feature rows for both teams
        home_row = feature_df[
            (feature_df["match_date"] <= fixture["kickoff_utc"].date()) &
            (feature_df["team_code"] == fixture["home_code"])
        ].sort_values("match_date").iloc[-1] if not feature_df.empty else None

        away_row = feature_df[
            (feature_df["match_date"] <= fixture["kickoff_utc"].date()) &
            (feature_df["team_code"] == fixture["away_code"])
        ].sort_values("match_date").iloc[-1] if not feature_df.empty else None

        if home_row is None or away_row is None:
            print(f"Skipping fixture {fixture['fixture_id']}: insufficient history.")
            continue

        pred = model.predict_match(home_row.to_dict(), away_row.to_dict())

        write_prediction(
            conn,
            fixture_id=fixture["fixture_id"],
            kickoff_utc=fixture["kickoff_utc"],
            model_run_id=model_run_id,
            pred=pred,
        )
        print(
            f"Locked: {fixture['home_code']} vs {fixture['away_code']} | "
            f"HW={pred['p_home_win']:.1%} D={pred['p_draw']:.1%} AW={pred['p_away_win']:.1%}"
        )

    conn.close()


if __name__ == "__main__":
    main()
