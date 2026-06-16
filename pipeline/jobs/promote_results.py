"""
Promote finished World Cup results into the training data.

fetch_results.py writes scores into `fixtures`, but the model trains on
`historical_matches` (load_historical_from_db). Without this step a team's
rolling attack/defense form and self-computed Elo never move during the
tournament, so the most predictive signal available - how a side is actually
playing at the World Cup - is invisible to the daily re-train in
snapshot_odds.py and simulate_tournament.py.

This copies every finished fixture (both teams known, score recorded) into
historical_matches as a 'World Cup' match (competition weight 1.6, the heaviest
the model uses). It is idempotent: the partial unique index from migration 006
plus ON CONFLICT DO NOTHING means re-running it never double-counts a game, so
it is safe to run every 3h right after fetch_results.py.

Notes:
- Venue is recorded 'neutral', matching how the predictions were generated
  (lock_predictions uses venue_enc=0 for every 2026 fixture). Host nations are
  not given a home edge in training, keeping training and prediction consistent.
- A knockout decided on penalties is a draw at full time; the recorded FT score
  is a draw, which is the honest scoreline to train on (the model learns from
  goals, not the shootout).

Usage:
    python pipeline/jobs/promote_results.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

MIGRATION = os.path.join(
    os.path.dirname(__file__), "..", "..", "db", "migrations",
    "006_promote_wc_results.sql",
)

SOURCE = "openfootball-wc2026"


def main():
    conn = get_connection()
    with conn.cursor() as cur:
        with open(MIGRATION) as f:
            cur.execute(f.read())  # ensure the idempotency index exists
        conn.commit()

        cur.execute(
            """
            INSERT INTO historical_matches
                (match_date, home_team_id, away_team_id,
                 home_goals, away_goals, venue_type, tournament, source)
            SELECT
                (f.kickoff_utc AT TIME ZONE 'UTC')::date,
                f.home_team_id, f.away_team_id,
                f.home_goals, f.away_goals,
                'neutral', 'World Cup', %s
            FROM fixtures f
            WHERE f.home_goals IS NOT NULL
              AND f.away_goals IS NOT NULL
              AND f.home_team_id IS NOT NULL
              AND f.away_team_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """,
            (SOURCE,),
        )
        promoted = cur.rowcount
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM historical_matches WHERE source = %s", (SOURCE,)
        )
        total = cur.fetchone()[0]
    conn.close()

    print(f"Promoted {promoted} new result(s); {total} WC 2026 match(es) now in "
          f"historical_matches.")


if __name__ == "__main__":
    main()
