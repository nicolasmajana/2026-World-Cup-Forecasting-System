"""
Fetch finished World Cup results and write the scores into `fixtures`.

Source: openfootball/worldcup.json (same free, public-domain feed we use for
the schedule). A played match carries score.ft = [home_goals, away_goals];
this updates the matching fixture. Run before update_results.py, which then
computes the Brier score for each scored prediction.

This is the real-time results connector. openfootball is community-maintained
and updates through the tournament; if you later want lower-latency official
data, swap this for API-Football (paid key) behind the same interface.

Usage:
    python pipeline/jobs/fetch_results.py
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

RESULTS_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)


def main():
    print(f"Fetching results from {RESULTS_URL}")
    data = requests.get(RESULTS_URL, timeout=30).json()

    conn = get_connection()
    updated = 0
    with conn.cursor() as cur:
        for match in data.get("matches", []):
            score = match.get("score") or {}
            ft = score.get("ft")
            if not ft or len(ft) != 2:
                continue  # not played yet

            home = match.get("team1")
            away = match.get("team2")
            home_name = home.get("name") if isinstance(home, dict) else home
            away_name = away.get("name") if isinstance(away, dict) else away
            # same slug load_fixtures.py built
            slug = f"{match['date']}-{home_name or 'TBD'}-{away_name or 'TBD'}"

            cur.execute(
                """
                UPDATE fixtures
                SET home_goals = %s, away_goals = %s,
                    result_source = 'openfootball', result_at = now()
                WHERE match_id = %s AND home_goals IS NULL
                """,
                (int(ft[0]), int(ft[1]), slug),
            )
            updated += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Recorded {updated} new result(s).")


if __name__ == "__main__":
    main()
