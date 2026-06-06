"""
One-off: recompute every fixture's stage from openfootball and correct the DB.

Needed because load_fixtures.py originally missed openfootball's singular
'Quarter-final'/'Semi-final' labels, so those matches were stored as 'group'
(creating an empty, group-less section on the Groups page). load_fixtures uses
ON CONFLICT DO NOTHING, so it won't fix existing rows; this does.

Usage:
    python pipeline/data/fix_stages.py
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402
from data.load_fixtures import FIXTURES_URL, stage_for  # noqa: E402


def main():
    data = requests.get(FIXTURES_URL, timeout=30).json()
    conn = get_connection()
    fixed = 0
    with conn.cursor() as cur:
        for match in data.get("matches", []):
            stage = stage_for(match.get("round", ""))
            home = match.get("team1")
            away = match.get("team2")
            home_name = home.get("name") if isinstance(home, dict) else home
            away_name = away.get("name") if isinstance(away, dict) else away
            slug = f"{match['date']}-{home_name or 'TBD'}-{away_name or 'TBD'}"
            # group_name only belongs to actual group games
            group = match.get("group") if stage == "group" else None
            cur.execute(
                """
                UPDATE fixtures
                SET stage = %s, group_name = %s
                WHERE match_id = %s AND (stage <> %s OR group_name IS DISTINCT FROM %s)
                """,
                (stage, group, slug, stage, group),
            )
            fixed += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Corrected {fixed} fixture(s).")


if __name__ == "__main__":
    main()
