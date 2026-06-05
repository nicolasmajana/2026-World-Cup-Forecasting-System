"""Endpoints for calibration / Brier score stats."""

from fastapi import APIRouter
from ..db.connection import get_cursor

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("/summary")
def calibration_summary():
    """Headline metrics: overall Brier score and number of scored matches."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*)            AS scored_matches,
                AVG(brier_score)    AS mean_brier
            FROM predictions
            WHERE brier_score IS NOT NULL
            """
        )
        return cur.fetchone()


@router.get("/reliability")
def reliability_bins():
    """
    Reliability diagram data: bucket predicted home-win probability into
    deciles and compare predicted vs. observed frequency.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                width_bucket(p.p_home_win, 0, 1, 10) AS bucket,
                AVG(p.p_home_win)                     AS mean_predicted,
                AVG(CASE WHEN f.home_goals > f.away_goals THEN 1.0 ELSE 0.0 END)
                                                      AS observed_freq,
                COUNT(*)                              AS n
            FROM predictions p
            JOIN fixtures f ON f.id = p.fixture_id
            WHERE f.home_goals IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket
            """
        )
        return cur.fetchall()
