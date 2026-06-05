"""
One-time bulk loader: parse the martj42 international results CSV and
populate the `teams` and `historical_matches` tables.

Source (public domain, no auth needed):
    https://raw.githubusercontent.com/martj42/international_results/master/results.csv

By default this reads straight from GitHub. To work offline, save the CSV as
pipeline/data/raw/results.csv and it will be used instead.

Run db/seed_teams.sql FIRST so known source-name mismatches are pre-mapped.

Usage:
    python pipeline/data/load_kaggle.py
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

GITHUB_CSV = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
RAW_CSV = os.path.join(os.path.dirname(__file__), "raw", "results.csv")

# Minimal name -> (fifa_code, confederation) map. Extend as needed; unknown
# teams are inserted with a generated code and 'UNKNOWN' confederation so the
# load never fails on a missing entry.
CONFED = {
    "Colombia": ("COL", "CONMEBOL"),
    "Brazil": ("BRA", "CONMEBOL"),
    "Argentina": ("ARG", "CONMEBOL"),
    "Uruguay": ("URU", "CONMEBOL"),
    "France": ("FRA", "UEFA"),
    "Germany": ("GER", "UEFA"),
    "Spain": ("ESP", "UEFA"),
    "England": ("ENG", "UEFA"),
    "United States": ("USA", "CONCACAF"),
    "Mexico": ("MEX", "CONCACAF"),
    "Canada": ("CAN", "CONCACAF"),
    "Japan": ("JPN", "AFC"),
    "Morocco": ("MAR", "CAF"),
    "Nigeria": ("NGA", "CAF"),
    "Australia": ("AUS", "AFC"),
}


def derive_code(name: str, used: set[str]) -> str:
    """Generate a unique 3-char code for teams not in CONFED."""
    base = "".join(c for c in name.upper() if c.isalpha())[:3].ljust(3, "X")
    code = base
    i = 1
    while code in used:
        code = (base[:2] + str(i))[:3]
        i += 1
    return code


def load_existing_alias_map(conn) -> dict[str, int]:
    """
    Map martj42 source names -> team_id for teams already seeded by
    db/seed_teams.sql (the known cross-source mismatches).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, COALESCE(martj42_name, name) FROM teams"
        )
        return {row[1]: row[0] for row in cur.fetchall()}


def upsert_teams(conn, df: pd.DataFrame) -> dict[str, int]:
    """
    Map every martj42 team name to a team_id. Teams pre-seeded in
    db/seed_teams.sql are reused (joined by martj42_name); any remaining
    teams are inserted with a generated code.
    """
    names = pd.unique(df[["home_team", "away_team"]].values.ravel())
    name_to_id = load_existing_alias_map(conn)
    used_codes: set[str] = set()

    with conn.cursor() as cur:
        # collect codes already in use to avoid collisions
        cur.execute("SELECT fifa_code FROM teams")
        used_codes = {row[0] for row in cur.fetchall()}

        for name in sorted(names):
            if name in name_to_id:
                continue  # already seeded / inserted
            code, conf = CONFED.get(name, (None, "UNKNOWN"))
            if code is None:
                code = derive_code(name, used_codes)
            used_codes.add(code)

            cur.execute(
                """
                INSERT INTO teams (fifa_code, name, confederation, martj42_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (fifa_code) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (code, name, conf, name),
            )
            name_to_id[name] = cur.fetchone()[0]
    conn.commit()
    return name_to_id


def insert_matches(conn, df: pd.DataFrame, name_to_id: dict[str, int]):
    rows = []
    for _, m in df.iterrows():
        home_id = name_to_id.get(m["home_team"])
        away_id = name_to_id.get(m["away_team"])
        if home_id is None or away_id is None:
            continue
        venue = "neutral" if m.get("neutral") else "home"
        rows.append((
            m["date"], home_id, away_id,
            int(m["home_score"]), int(m["away_score"]),
            venue, m.get("tournament", "Unknown"), "kaggle",
        ))

    # Batched insert via execute_values — far faster than executemany and
    # won't time out the pooled connection on ~49k rows.
    from psycopg2.extras import execute_values

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO historical_matches
                (match_date, home_team_id, away_team_id,
                 home_goals, away_goals, venue_type, tournament, source)
            VALUES %s
            """,
            rows,
            page_size=1000,
        )
    conn.commit()
    return len(rows)


def main():
    source = RAW_CSV if os.path.exists(RAW_CSV) else GITHUB_CSV
    print(f"Reading results from: {source}")
    df = pd.read_csv(source, parse_dates=["date"])
    df = df.dropna(subset=["home_score", "away_score"])
    print(f"Loaded {len(df)} matches from CSV.")

    conn = get_connection()
    name_to_id = upsert_teams(conn, df)
    print(f"Upserted {len(name_to_id)} teams.")
    n = insert_matches(conn, df, name_to_id)
    print(f"Inserted {n} historical matches.")
    conn.close()


if __name__ == "__main__":
    main()
