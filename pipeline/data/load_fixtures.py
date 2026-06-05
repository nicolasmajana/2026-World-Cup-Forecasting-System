"""
Load the 2026 World Cup fixture list into the `fixtures` table.

Source (public domain): openfootball/worldcup.json
    https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json

Caveat handled here: openfootball stores kickoff as local time with a UTC
offset (e.g. "13:00" + "UTC-6"). We normalize everything to UTC before insert.

Teams that are still TBD (e.g. knockout slots, playoff winners) are stored
with NULL team ids until the bracket resolves.

Usage:
    python pipeline/data/load_fixtures.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

FIXTURES_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)

# openfootball "round" labels -> our stage codes
STAGE_MAP = {
    "Round of 32": "r32",
    "Round of 16": "r16",
    "Quarterfinals": "qf",
    "Quarter-finals": "qf",
    "Semifinals": "sf",
    "Semi-finals": "sf",
    "Final": "f",
    "Match for third place": "f",
}


def stage_for(round_label: str) -> str:
    if round_label in STAGE_MAP:
        return STAGE_MAP[round_label]
    return "group"  # "Matchday 1/2/3" and group labels


def parse_offset(tz: str) -> timezone:
    """'UTC-6' / 'UTC+2' / 'UTC' -> a timezone object."""
    tz = tz.replace("UTC", "").strip()
    if not tz:
        return timezone.utc
    sign = 1 if tz[0] == "+" else -1
    hours = int(tz[1:].split(":")[0])
    return timezone(sign * timedelta(hours=hours))


def to_utc(date_str: str, time_str: str, tz_str: str) -> datetime:
    """Combine date + local time + offset into a UTC datetime."""
    local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    local = local.replace(tzinfo=parse_offset(tz_str))
    return local.astimezone(timezone.utc)


def team_id_by_name(cur, name: str):
    """Resolve a fixture team name to a team_id, or None if TBD/unknown."""
    if not name:
        return None
    cur.execute(
        """
        SELECT id FROM teams
        WHERE name = %s OR fifa_name = %s OR martj42_name = %s
        LIMIT 1
        """,
        (name, name, name),
    )
    row = cur.fetchone()
    return row[0] if row else None


def main():
    print(f"Fetching fixtures from {FIXTURES_URL}")
    data = requests.get(FIXTURES_URL, timeout=30).json()

    conn = get_connection()
    inserted = 0
    with conn.cursor() as cur:
        for rnd in data.get("rounds", []):
            stage = stage_for(rnd.get("name", ""))
            for match in rnd.get("matches", []):
                kickoff = to_utc(
                    match["date"],
                    match.get("time", "12:00"),
                    match.get("timezone", "UTC"),
                )
                home = match.get("team1", {})
                away = match.get("team2", {})
                home_name = home.get("name") if isinstance(home, dict) else home
                away_name = away.get("name") if isinstance(away, dict) else away

                match_slug = f"{match['date']}-{home_name or 'TBD'}-{away_name or 'TBD'}"
                ground = match.get("ground", {})
                venue = ground.get("name") if isinstance(ground, dict) else ground

                cur.execute(
                    """
                    INSERT INTO fixtures
                        (match_id, kickoff_utc, home_team_id, away_team_id,
                         venue, stage, group_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (match_id) DO NOTHING
                    """,
                    (
                        match_slug,
                        kickoff,
                        team_id_by_name(cur, home_name),
                        team_id_by_name(cur, away_name),
                        venue,
                        stage,
                        match.get("group"),
                    ),
                )
                inserted += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Inserted {inserted} fixtures.")


if __name__ == "__main__":
    main()
