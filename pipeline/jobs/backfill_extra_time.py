"""
One-off backfill for knockout matches recorded before fetch_results.py learned
to read score.et and score.p (see git history around 2026-07-08).

fetch_results.py only ever wrote score.ft into fixtures.home_goals/away_goals,
and only started reading score.p (penalty shootouts) on 2026-07-05. Any
knockout match that finished before that fix, and that either went to extra
time or a shootout, is stuck with a stale or incomplete score: fetch_results.py
only ever updates a fixture WHERE home_goals IS NULL, so it will never revisit
an already-recorded row on its own.

This corrects fixtures.home_goals/away_goals/home_pens/away_pens for those
matches from the feed, then propagates the same correction into
historical_matches (promote_results.py already copied the stale score there
for any match promoted before this backfill ran). predictions.brier_score is
NOT touched: the immutability trigger only allows a NULL -> value fill, by
design, so any prediction already scored against a stale goal count keeps
that score permanently. That is documented in the nightly report, not fixed
here.

Usage:
    python pipeline/jobs/backfill_extra_time.py
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402
from data.bracket_wiring import feed_num  # noqa: E402

RESULTS_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)


def main():
    data = requests.get(RESULTS_URL, timeout=30).json()

    conn = get_connection()
    fixed = 0
    with conn.cursor() as cur:
        for match in data.get("matches", []):
            score = match.get("score") or {}
            ft = score.get("ft")
            if not ft or len(ft) != 2:
                continue
            final = score.get("et") or ft
            pens = score.get("p")
            home_pens = int(pens[0]) if pens and len(pens) == 2 else None
            away_pens = int(pens[1]) if pens and len(pens) == 2 else None

            num = feed_num(match)
            if num is None:
                continue

            cur.execute(
                """
                SELECT id, home_goals, away_goals, home_pens, away_pens
                FROM fixtures WHERE match_num = %s
                """,
                (num,),
            )
            row = cur.fetchone()
            if row is None:
                continue
            fid, hg, ag, hp, ap = row
            new_hg, new_ag = int(final[0]), int(final[1])
            if hg == new_hg and ag == new_ag and hp == home_pens and ap == away_pens:
                continue  # already correct, nothing to backfill

            cur.execute(
                """
                UPDATE fixtures
                SET home_goals = %s, away_goals = %s,
                    home_pens = %s, away_pens = %s
                WHERE id = %s
                """,
                (new_hg, new_ag, home_pens, away_pens, fid),
            )
            print(f"  fixtures match {num}: {hg}-{ag} (pens {hp}-{ap}) -> "
                  f"{new_hg}-{new_ag} (pens {home_pens}-{away_pens})")
            fixed += 1

            # Propagate into historical_matches if the stale score was already
            # promoted there (same team pair + kickoff date, matched by id).
            cur.execute(
                """
                UPDATE historical_matches hm
                SET home_goals = %s, away_goals = %s
                FROM fixtures f
                WHERE f.id = %s
                  AND hm.home_team_id = f.home_team_id
                  AND hm.away_team_id = f.away_team_id
                  AND hm.match_date = (f.kickoff_utc AT TIME ZONE 'UTC')::date
                  AND hm.source = 'openfootball-wc2026'
                """,
                (new_hg, new_ag, fid),
            )
            if cur.rowcount:
                print(f"    historical_matches: corrected {cur.rowcount} row(s)")

    conn.commit()
    conn.close()
    print(f"Backfilled {fixed} fixture(s).")


if __name__ == "__main__":
    main()
