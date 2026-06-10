"""
Knockout slot resolver. Runs before fetch_results in the update workflow.

As the group stage resolves, openfootball rewrites knockout slot refs
("1E", "W74") into real team names. This job:

1. Ensures fixtures.match_num exists and is backfilled (slug match against the
   feed; the numeric id is the stable key once labels start changing).
2. For every knockout fixture with an empty team slot, checks whether the feed
   now names a real team there, and fills in the team id.

Name matching normalizes "&" vs "and" (the mismatch that originally left
Bosnia's slots NULL) and checks every alias column. A name that is not a slot
ref and still fails lookup is printed loudly: that means a new alias is
needed in the teams table.

Usage:
    python pipeline/jobs/resolve_knockout.py
"""

import os
import re
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402
from data.load_fixtures import FIXTURES_URL  # noqa: E402
from data.bracket_wiring import feed_num  # noqa: E402

MIGRATION = os.path.join(
    os.path.dirname(__file__), "..", "..", "db", "migrations",
    "005_match_num.sql",
)

SLOT_REF = re.compile(r"^([12][A-L]|3[A-L](/[A-L])+|[WL]\d+)$")


def team_name(entry):
    return entry.get("name") if isinstance(entry, dict) else entry


def find_team_id(cur, name: str):
    """Team id by name across all alias columns, tolerant of '&' vs 'and'."""
    variants = {name, name.replace("&", "and"), name.replace("and", "&")}
    for v in variants:
        cur.execute(
            """
            SELECT id FROM teams
            WHERE name = %s OR fifa_name = %s OR martj42_name = %s
               OR elo_name = %s OR fbref_name = %s
            LIMIT 1
            """,
            (v, v, v, v, v),
        )
        row = cur.fetchone()
        if row:
            return row[0]
    return None


def backfill_match_nums(cur, matches) -> int:
    """One-time slug -> match_num mapping (idempotent; only fills NULLs)."""
    filled = 0
    for m in matches:
        num = feed_num(m)
        if num is None:
            continue
        h = team_name(m.get("team1")) or "TBD"
        a = team_name(m.get("team2")) or "TBD"
        slug = f"{m['date']}-{h}-{a}"
        cur.execute(
            "UPDATE fixtures SET match_num = %s WHERE match_id = %s AND match_num IS NULL",
            (num, slug),
        )
        filled += cur.rowcount
    return filled


def resolve_slots(cur, matches) -> int:
    """Fill NULL team slots on knockout fixtures from real names in the feed."""
    resolved = 0
    for m in matches:
        num = feed_num(m)
        if num is None or num < 73:
            continue  # group stage: teams were known at load time
        for side, col in (("team1", "home_team_id"), ("team2", "away_team_id")):
            name = team_name(m.get(side))
            if not name or SLOT_REF.match(name):
                continue  # still an unresolved slot ref
            tid = find_team_id(cur, name)
            if tid is None:
                print(f"WARNING: match {num}: no team matches feed name {name!r}. "
                      f"Add an alias in the teams table.")
                continue
            cur.execute(
                f"UPDATE fixtures SET {col} = %s "
                f"WHERE match_num = %s AND {col} IS NULL",
                (tid, num),
            )
            if cur.rowcount:
                print(f"  match {num}: {col.split('_')[0]} -> {name}")
                resolved += cur.rowcount
    return resolved


def main():
    data = requests.get(FIXTURES_URL, timeout=30).json()
    matches = data.get("matches", [])

    conn = get_connection()
    with conn.cursor() as cur:
        with open(MIGRATION) as f:
            cur.execute(f.read())
        conn.commit()

        filled = backfill_match_nums(cur, matches)
        conn.commit()

        cur.execute("SELECT count(*) FROM fixtures WHERE match_num IS NULL")
        missing = cur.fetchone()[0]
        print(f"match_num: backfilled {filled}, still missing {missing}.")

        resolved = resolve_slots(cur, matches)
        conn.commit()

        cur.execute(
            """SELECT count(*) FROM fixtures
               WHERE stage <> 'group'
                 AND (home_team_id IS NULL OR away_team_id IS NULL)"""
        )
        open_slots = cur.fetchone()[0]
    conn.close()
    print(f"Resolved {resolved} knockout slot(s); "
          f"{open_slots} knockout fixture(s) still have an open slot.")


if __name__ == "__main__":
    main()
