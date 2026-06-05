"""Endpoints for fixtures and predictions."""

from fastapi import APIRouter, HTTPException
from ..db.connection import get_cursor

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/upcoming")
def upcoming_matches():
    """Upcoming fixtures with their locked predictions (if any)."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM v_upcoming_predictions")
        return cur.fetchall()


@router.get("/{fixture_id}")
def match_detail(fixture_id: int):
    """Full detail for one fixture: prediction, feature snapshot, and result."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                f.id AS fixture_id, f.kickoff_utc, f.stage, f.group_name,
                f.venue, f.city, f.home_goals, f.away_goals,
                ht.name AS home_team, ht.fifa_code AS home_code,
                at.name AS away_team, at.fifa_code AS away_code,
                p.p_home_win, p.p_draw, p.p_away_win,
                p.xg_home, p.xg_away, p.features, p.locked_at, p.brier_score
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
            LEFT JOIN predictions p ON p.fixture_id = f.id
            WHERE f.id = %s
            """,
            (fixture_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(404, "Fixture not found")
        return row
