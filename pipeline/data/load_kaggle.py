"""
One-time bulk loader: parse the Kaggle international results CSV and
populate the `teams` and `historical_matches` tables.

Dataset: https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017
Save the CSV as pipeline/data/raw/results.csv before running.

Usage:
    python pipeline/data/load_kaggle.py
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

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


def upsert_teams(conn, df: pd.DataFrame) -> dict[str, int]:
    """Insert all teams appearing in the dataset; return name -> team_id map."""
    names = pd.unique(df[["home_team", "away_team"]].values.ravel())
    used_codes: set[str] = set()
    name_to_id: dict[str, int] = {}

    with conn.cursor() as cur:
        for name in sorted(names):
            code, conf = CONFED.get(name, (None, "UNKNOWN"))
            if code is None:
                code = derive_code(name, used_codes)
            used_codes.add(code)

            cur.execute(
                """
                INSERT INTO teams (fifa_code, name, confederation)
                VALUES (%s, %s, %s)
                ON CONFLICT (fifa_code) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (code, name, conf),
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

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO historical_matches
                (match_date, home_team_id, away_team_id,
                 home_goals, away_goals, venue_type, tournament, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def main():
    if not os.path.exists(RAW_CSV):
        sys.exit(f"CSV not found at {RAW_CSV} — download it first (see docs/setup.md).")

    df = pd.read_csv(RAW_CSV, parse_dates=["date"])
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
