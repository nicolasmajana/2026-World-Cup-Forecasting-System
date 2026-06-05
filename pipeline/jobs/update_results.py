"""
GitHub Actions polling job (runs every few hours).
Finds finished matches without a Brier score, fetches results, and updates.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.loader import get_connection, load_finished_unscored_fixtures
from model.poisson_model import brier_score

load_dotenv()


def update_brier(conn, prediction_id: int, score: float):
    sql = "UPDATE predictions SET brier_score = %s WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (score, prediction_id))
    conn.commit()


def main():
    fixtures = load_finished_unscored_fixtures()
    if fixtures.empty:
        print("No finished matches need Brier score updates.")
        return

    print(f"Updating Brier scores for {len(fixtures)} match(es).")
    conn = get_connection()

    for _, row in fixtures.iterrows():
        pred = {
            "p_home_win": float(row["p_home_win"]),
            "p_draw":     float(row["p_draw"]),
            "p_away_win": float(row["p_away_win"]),
        }
        score = brier_score(pred, int(row["home_goals"]), int(row["away_goals"]))
        update_brier(conn, int(row["prediction_id"]), score)
        print(f"  Prediction {row['prediction_id']}: Brier = {score:.5f}")

    conn.close()


if __name__ == "__main__":
    main()
