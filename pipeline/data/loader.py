"""Load and preprocess historical match data from multiple sources."""

import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def load_historical_from_db() -> pd.DataFrame:
    """Return all historical matches joined with team metadata."""
    sql = """
        SELECT
            hm.match_date,
            ht.fifa_code  AS home_code,
            ht.name       AS home_team,
            ht.confederation AS home_conf,
            at.fifa_code  AS away_code,
            at.name       AS away_team,
            at.confederation AS away_conf,
            hm.home_goals,
            hm.away_goals,
            hm.venue_type,
            hm.tournament
        FROM historical_matches hm
        JOIN teams ht ON ht.id = hm.home_team_id
        JOIN teams at ON at.id = hm.away_team_id
        ORDER BY hm.match_date
    """
    with get_connection() as conn:
        return pd.read_sql(sql, conn, parse_dates=["match_date"])


def load_upcoming_fixtures() -> pd.DataFrame:
    """Return fixtures in the next 48 hours that don't yet have a locked prediction."""
    sql = """
        SELECT
            f.id        AS fixture_id,
            f.kickoff_utc,
            f.stage,
            ht.fifa_code AS home_code,
            at.fifa_code AS away_code
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN predictions p ON p.fixture_id = f.id
        WHERE p.id IS NULL
          AND f.kickoff_utc BETWEEN now() AND now() + INTERVAL '48 hours'
        ORDER BY f.kickoff_utc
    """
    with get_connection() as conn:
        return pd.read_sql(sql, conn, parse_dates=["kickoff_utc"])


def load_finished_unscored_fixtures() -> pd.DataFrame:
    """Return fixtures that finished but don't yet have a brier_score computed."""
    sql = """
        SELECT
            f.id        AS fixture_id,
            f.home_goals,
            f.away_goals,
            p.id        AS prediction_id,
            p.p_home_win,
            p.p_draw,
            p.p_away_win
        FROM fixtures f
        JOIN predictions p ON p.fixture_id = f.id
        WHERE f.home_goals IS NOT NULL
          AND p.brier_score IS NULL
    """
    with get_connection() as conn:
        return pd.read_sql(sql, conn)
