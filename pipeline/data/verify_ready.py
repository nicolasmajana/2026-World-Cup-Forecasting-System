"""Pre-tournament readiness check. Run anytime; prints the state of every
moving part the automation depends on."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection  # noqa: E402

conn = get_connection()
cur = conn.cursor()
checks = [
    ("predictions locked", "SELECT count(*) FROM predictions"),
    ("fixtures with both teams", "SELECT count(*) FROM fixtures WHERE home_team_id IS NOT NULL AND away_team_id IS NOT NULL"),
    ("next 48h fixtures missing a prediction",
     """SELECT count(*) FROM fixtures f
        LEFT JOIN predictions p ON p.fixture_id = f.id
        WHERE p.id IS NULL AND f.home_team_id IS NOT NULL AND f.away_team_id IS NOT NULL
          AND f.kickoff_utc BETWEEN now() AND now() + INTERVAL '48 hours'"""),
    ("odds snapshots", "SELECT count(*) FROM prediction_history"),
    ("distinct snapshot days", "SELECT count(DISTINCT captured_at::date) FROM prediction_history"),
    ("tournament sims stored", "SELECT count(*) FROM tournament_sim"),
    ("latest sim", "SELECT max(simulated_at) FROM tournament_sim"),
    ("latest model run", "SELECT model_version || ' Brier ' || val_brier_score FROM model_runs ORDER BY run_at DESC LIMIT 1"),
    ("results recorded", "SELECT count(*) FROM fixtures WHERE home_goals IS NOT NULL"),
]
for label, q in checks:
    cur.execute(q)
    print(f"{label:42} {cur.fetchone()[0]}")
conn.close()
