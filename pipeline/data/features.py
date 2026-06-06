"""Build the feature matrix for the Poisson regression model."""

import numpy as np
import pandas as pd


ROLLING_WINDOW = 10  # matches


def compute_team_rolling_strengths(matches: pd.DataFrame) -> pd.DataFrame:
    """
    For each team in each match, compute rolling attack and defense strength
    over the previous ROLLING_WINDOW games.

    Returns a DataFrame indexed by (match_date, team_code) with columns:
        attack_strength, defense_strength
    """
    records = []

    # Expand to one row per team per match
    home_rows = matches[["match_date", "home_code", "home_goals", "away_goals"]].copy()
    home_rows.columns = ["match_date", "team_code", "goals_scored", "goals_conceded"]

    away_rows = matches[["match_date", "away_code", "away_goals", "home_goals"]].copy()
    away_rows.columns = ["match_date", "team_code", "goals_scored", "goals_conceded"]

    team_games = pd.concat([home_rows, away_rows]).sort_values(
        ["team_code", "match_date"]
    )

    # Rolling mean of the PREVIOUS ROLLING_WINDOW games, per team. Using
    # groupby().transform keeps everything vectorized — no per-row Python loop.
    grouped = team_games.groupby("team_code", sort=False)
    team_games["attack_strength"] = grouped["goals_scored"].transform(
        lambda s: s.shift(1).rolling(ROLLING_WINDOW, min_periods=3).mean()
    )
    team_games["defense_strength"] = grouped["goals_conceded"].transform(
        lambda s: s.shift(1).rolling(ROLLING_WINDOW, min_periods=3).mean()
    )

    df = team_games[
        ["match_date", "team_code", "attack_strength", "defense_strength"]
    ].set_index(["match_date", "team_code"])
    # A team can have >1 match on the same calendar date in the historical
    # record. Collapse to one row per (date, team) — keep the latest — so
    # .loc lookups return scalars, not Series. Sorting also removes the
    # "indexing past lexsort depth" performance warning.
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def build_match_features(
    matches: pd.DataFrame,
    elo_map: dict[str, int],
    rolling: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build feature matrix where each row is a team-in-a-match.
    Columns: attack_strength, defense_strength, elo, venue_type_enc, days_rest (placeholder)
    """
    flat = rolling.reset_index()  # match_date, team_code, attack_strength, defense_strength

    def side_frame(team_col, opp_col, goals_col, venue_val, venue_sign):
        # own attack/defense for the team on this side
        own = flat.rename(columns={"team_code": team_col})
        m = matches.merge(own, on=["match_date", team_col], how="left")
        # opponent's defense strength
        opp = flat.rename(
            columns={"team_code": opp_col, "defense_strength": "opp_defense_strength"}
        )[["match_date", opp_col, "opp_defense_strength"]]
        m = m.merge(opp, on=["match_date", opp_col], how="left")
        return pd.DataFrame({
            "match_date": m["match_date"],
            "team_code": m[team_col],
            "goals_scored": m[goals_col],
            "attack_strength": m["attack_strength"],
            "defense_strength": m["defense_strength"],
            "opp_defense_strength": m["opp_defense_strength"],
            "elo": m[team_col].map(elo_map).fillna(1500),
            "venue_enc": np.where(m["venue_type"] == venue_val, venue_sign, 0),
        })

    home = side_frame("home_code", "away_code", "home_goals", "home", 1)
    away = side_frame("away_code", "home_code", "away_goals", "away", -1)

    return pd.concat([home, away], ignore_index=True).dropna(
        subset=["attack_strength", "defense_strength", "opp_defense_strength"]
    )
