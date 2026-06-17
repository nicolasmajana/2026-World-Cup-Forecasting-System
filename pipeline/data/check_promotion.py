"""Check WC 2026 match promotion to historical_matches."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

cur.execute("SELECT count(*) FROM historical_matches WHERE tournament = 'World Cup' AND match_date >= '2026-01-01'")
wc2026_count = cur.fetchone()[0]
print('WC 2026 matches in historical_matches:', wc2026_count)

cur.execute("""
    SELECT hm.match_date, ht.name, at.name, hm.home_goals, hm.away_goals
    FROM historical_matches hm
    JOIN teams ht ON ht.id = hm.home_team_id
    JOIN teams at ON at.id = hm.away_team_id
    WHERE hm.tournament = 'World Cup' AND hm.match_date >= '2026-01-01'
    ORDER BY hm.match_date DESC LIMIT 5
""")
rows = cur.fetchall()
print('Recent WC 2026 entries:')
for r in rows:
    print(' ', r)

conn.close()
