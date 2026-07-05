"""
Fetch finished World Cup results and write the scores into `fixtures`.

Source: openfootball/worldcup.json (same free, public-domain feed we use for
the schedule). A played match carries score.ft = [home_goals, away_goals];
this updates the matching fixture. A knockout match still level at full time
also carries score.p = [home_pens, away_pens], recorded alongside so the
tournament sim can tell who actually advanced. Run before update_results.py,
which then computes the Brier score for each scored prediction.

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
from data.bracket_wiring import feed_num  # noqa: E402

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

            pens = score.get("p")
            home_pens = int(pens[0]) if pens and len(pens) == 2 else None
            away_pens = int(pens[1]) if pens and len(pens) == 2 else None

            # Prefer the stable numeric id; slugs embed team labels that
            # openfootball rewrites as the bracket resolves.
            num = feed_num(match)
            if num is not None:
                cur.execute(
                    """
                    UPDATE fixtures
                    SET home_goals = %s, away_goals = %s,
                        home_pens = %s, away_pens = %s,
                        result_source = 'openfootball', result_at = now()
                    WHERE match_num = %s AND home_goals IS NULL
                    """,
                    (int(ft[0]), int(ft[1]), home_pens, away_pens, num),
                )
                updated += cur.rowcount
            else:
                home = match.get("team1")
                away = match.get("team2")
                home_name = home.get("name") if isinstance(home, dict) else home
                away_name = away.get("name") if isinstance(away, dict) else away
                slug = f"{match['date']}-{home_name or 'TBD'}-{away_name or 'TBD'}"
                cur.execute(
                    """
                    UPDATE fixtures
                    SET home_goals = %s, away_goals = %s,
                        home_pens = %s, away_pens = %s,
                        result_source = 'openfootball', result_at = now()
                    WHERE match_id = %s AND home_goals IS NULL
                    """,
                    (int(ft[0]), int(ft[1]), home_pens, away_pens, slug),
                )
                updated += cur.rowcount
                if cur.rowcount == 0:
                    # Distinguish "already recorded" (fine) from "no such slug"
                    # (the feed renamed a team and the result can't land).
                    cur.execute(
                        "SELECT 1 FROM fixtures WHERE match_id = %s", (slug,)
                    )
                    if cur.fetchone() is None:
                        print(f"WARNING: played match has no matching fixture "
                              f"slug {slug!r}. A team name in the feed changed; "
                              f"fix the fixture or add an alias.")
    conn.commit()
    conn.close()
    print(f"Recorded {updated} new result(s).")


if __name__ == "__main__":
    main()
