"""
Append the current odds for every predicted fixture to prediction_history.
Run daily (after the lock job) to build the odds-drift time series that the
match-detail graph plots. Also applies the history migration if needed.

Usage:
    python pipeline/jobs/snapshot_odds.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

MIGRATION = os.path.join(
    os.path.dirname(__file__), "..", "..", "db", "migrations",
    "002_prediction_history.sql",
)


def main():
    conn = get_connection()
    with conn.cursor() as cur:
        # ensure table exists (idempotent)
        with open(MIGRATION) as f:
            cur.execute(f.read())
        conn.commit()

        # snapshot: copy each fixture's current official odds into history,
        # but skip if an identical latest snapshot already exists today
        cur.execute(
            """
            INSERT INTO prediction_history
                (fixture_id, model_run_id, p_home_win, p_draw, p_away_win,
                 xg_home, xg_away)
            SELECT p.fixture_id, p.model_run_id, p.p_home_win, p.p_draw,
                   p.p_away_win, p.xg_home, p.xg_away
            FROM predictions p
            WHERE NOT EXISTS (
                SELECT 1 FROM prediction_history h
                WHERE h.fixture_id = p.fixture_id
                  AND h.captured_at::date = now()::date
            )
            """
        )
        inserted = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Snapshotted odds for {inserted} fixture(s).")


if __name__ == "__main__":
    main()
