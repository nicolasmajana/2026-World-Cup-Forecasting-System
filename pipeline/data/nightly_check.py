"""Nightly data quality checks for the automated review."""
import os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Duplicate teams
cur.execute("SELECT name FROM teams GROUP BY name HAVING count(*)>1")
dups = cur.fetchall()
print('Duplicate team names:', dups if dups else 'none')

# Fixtures with result but no Brier score scored >3h ago
cur.execute("""
    SELECT f.id, ht.name, at.name, f.kickoff_utc, f.home_goals, f.away_goals, p.brier_score
    FROM fixtures f
    JOIN teams ht ON ht.id = f.home_team_id
    JOIN teams at ON at.id = f.away_team_id
    JOIN predictions p ON p.fixture_id = f.id
    WHERE f.home_goals IS NOT NULL
      AND p.brier_score IS NULL
      AND f.kickoff_utc < NOW() - interval '3 hours'
""")
unbrier = cur.fetchall()
print('Results without Brier (>3h old):', unbrier if unbrier else 'none')

# Last 5 scored fixtures
cur.execute("""
    SELECT ht.name, at.name,
           f.kickoff_utc AT TIME ZONE 'UTC',
           f.home_goals, f.away_goals, p.brier_score
    FROM fixtures f
    JOIN teams ht ON ht.id = f.home_team_id
    JOIN teams at ON at.id = f.away_team_id
    JOIN predictions p ON p.fixture_id = f.id
    WHERE f.home_goals IS NOT NULL
    ORDER BY f.kickoff_utc DESC LIMIT 5
""")
recent = cur.fetchall()
print('Last 5 scored fixtures:')
for r in recent:
    print(' ', r)

# Upcoming fixtures in next 48h needing predictions
cur.execute("""
    SELECT f.match_num, ht.name, at.name,
           f.kickoff_utc AT TIME ZONE 'UTC',
           (p.locked_at IS NOT NULL) AS has_prediction
    FROM fixtures f
    JOIN teams ht ON ht.id = f.home_team_id
    JOIN teams at ON at.id = f.away_team_id
    LEFT JOIN predictions p ON p.fixture_id = f.id
    WHERE f.kickoff_utc BETWEEN NOW() AND NOW() + interval '48 hours'
      AND f.home_team_id IS NOT NULL AND f.away_team_id IS NOT NULL
    ORDER BY f.kickoff_utc
""")
upcoming = cur.fetchall()
print('Upcoming fixtures in next 48h:')
for u in upcoming:
    print(' ', u)

# Check for fixtures finished without results (>4h past kickoff)
cur.execute("""
    SELECT f.id, ht.name, at.name, f.kickoff_utc AT TIME ZONE 'UTC'
    FROM fixtures f
    JOIN teams ht ON ht.id = f.home_team_id
    JOIN teams at ON at.id = f.away_team_id
    WHERE f.kickoff_utc < NOW() - interval '4 hours'
      AND f.home_goals IS NULL
      AND f.home_team_id IS NOT NULL
      AND f.away_team_id IS NOT NULL
    ORDER BY f.kickoff_utc DESC LIMIT 10
""")
missing = cur.fetchall()
print('Fixtures >4h past without results:')
for m in missing:
    print(' ', m)

conn.close()
