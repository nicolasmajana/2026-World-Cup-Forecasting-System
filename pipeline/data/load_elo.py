"""
Load current Elo ratings from eloratings.net into teams.fifa_elo.

Reality check: World.tsv uses 2-letter (mostly ISO-3166 alpha-2) codes in
column 3, and an Elo rating in column 4 — NOT full country names as some
docs claim. So we map our canonical team NAME -> eloratings 2-letter code
for the teams we care about (the 2026 World Cup field), look up the rating,
and write it to teams.fifa_elo. Teams without a mapping keep NULL (the model
falls back to 1500).

Usage:
    python pipeline/data/load_elo.py
"""

import os
import sys
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

ELO_URL = "https://www.eloratings.net/World.tsv"

# Canonical team name (as stored in teams.name) -> eloratings.net 2-letter code.
# Covers the 2026 World Cup field. England/Scotland use eloratings' custom codes.
NAME_TO_ELO_CODE = {
    "Algeria": "DZ", "Argentina": "AR", "Australia": "AU", "Austria": "AT",
    "Belgium": "BE", "Brazil": "BR", "Canada": "CA", "Cape Verde": "CV",
    "Colombia": "CO", "Croatia": "HR", "Curaçao": "CW", "Czechia": "CZ",
    "DR Congo": "CD", "Ecuador": "EC", "Egypt": "EG", "England": "EN",
    "France": "FR", "Germany": "DE", "Ghana": "GH", "Haiti": "HT",
    "Iran": "IR", "Iraq": "IQ", "Ivory Coast": "CI", "Japan": "JP",
    "Jordan": "JO", "Mexico": "MX", "Morocco": "MA", "Netherlands": "NL",
    "New Zealand": "NZ", "Norway": "NO", "Panama": "PA", "Paraguay": "PY",
    "Portugal": "PT", "Qatar": "QA", "Saudi Arabia": "SA", "Scotland": "SC",
    "Senegal": "SN", "South Africa": "ZA", "South Korea": "KR", "Spain": "ES",
    "Sweden": "SE", "Switzerland": "CH", "Tunisia": "TN", "Turkey": "TR",
    "United States": "US", "Uruguay": "UY", "Uzbekistan": "UZ",
}


def fetch_elo() -> dict[str, int]:
    """2-letter code -> current Elo rating."""
    r = requests.get(ELO_URL, timeout=30)
    r.raise_for_status()
    elo = {}
    for line in r.text.splitlines():
        parts = line.split("\t")
        if len(parts) > 3 and parts[3].isdigit():
            elo[parts[2]] = int(parts[3])
    return elo


def main():
    elo = fetch_elo()
    print(f"Fetched {len(elo)} Elo ratings from eloratings.net")

    conn = get_connection()
    updated, missing = 0, []
    with conn.cursor() as cur:
        for name, code in NAME_TO_ELO_CODE.items():
            rating = elo.get(code)
            if rating is None:
                missing.append(f"{name} ({code})")
                continue
            cur.execute(
                "UPDATE teams SET fifa_elo = %s, elo_name = %s WHERE name = %s",
                (rating, code, name),
            )
            updated += cur.rowcount
    conn.commit()
    conn.close()

    print(f"Updated Elo for {updated} teams.")
    if missing:
        print(f"No Elo found for {len(missing)}: {', '.join(missing)}")


if __name__ == "__main__":
    main()
