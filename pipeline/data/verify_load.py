"""Quick sanity check on loaded data. Run after the loaders."""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
checks = [
    ("SELECT count(*) FROM teams", "teams"),
    ("SELECT count(*) FROM historical_matches", "historical_matches"),
    ("SELECT min(match_date), max(match_date) FROM historical_matches", "date range"),
    ("SELECT count(*) FROM fixtures", "fixtures"),
    ("SELECT count(*) FROM fixtures WHERE home_team_id IS NOT NULL "
     "AND away_team_id IS NOT NULL", "fixtures w/ both teams"),
    ("SELECT count(*) FROM historical_matches WHERE match_date < '2024-01-01'",
     "train (pre-2024)"),
    ("SELECT count(*) FROM historical_matches WHERE match_date >= '2024-01-01'",
     "val (2024+)"),
]
for q, label in checks:
    cur.execute(q)
    print(f"{label:28} {cur.fetchone()}")
conn.close()
