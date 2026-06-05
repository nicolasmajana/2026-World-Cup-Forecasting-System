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

    team_games = pd.concat([home_rows, away_rows]).sort_values("match_date")

    for team, grp in team_games.groupby("team_code"):
        grp = grp.sort_values("match_date")
        attack  = grp["goals_scored"].shift(1).rolling(ROLLING_WINDOW, min_periods=3).mean()
        defense = grp["goals_conceded"].shift(1).rolling(ROLLING_WINDOW, min_periods=3).mean()
        for i, (_, row) in enumerate(grp.iterrows()):
            records.append({
                "match_date": row["match_date"],
                "team_code": team,
                "attack_strength": attack.iloc[i],
                "defense_strength": defense.iloc[i],
            })

    df = pd.DataFrame(records).set_index(["match_date", "team_code"])
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
    rows = []
    for _, m in matches.iterrows():
        for side in ("home", "away"):
            code = m[f"{side}_code"]
            opp_side = "away" if side == "home" else "home"
            opp_code = m[f"{opp_side}_code"]
            try:
                atk = rolling.loc[(m["match_date"], code), "attack_strength"]
                dfs = rolling.loc[(m["match_date"], code), "defense_strength"]
                opp_dfs = rolling.loc[(m["match_date"], opp_code), "defense_strength"]
            except KeyError:
                continue  # skip if insufficient history

            venue_enc = 1 if side == "home" and m["venue_type"] == "home" else (
                -1 if side == "away" and m["venue_type"] == "away" else 0
            )

            rows.append({
                "match_date": m["match_date"],
                "team_code": code,
                "goals_scored": m[f"{side}_goals"],
                "attack_strength": atk,
                "defense_strength": dfs,
                "opp_defense_strength": opp_dfs,
                "elo": elo_map.get(code, 1500),
                "venue_enc": venue_enc,
            })

    return pd.DataFrame(rows).dropna(
        subset=["attack_strength", "defense_strength", "opp_defense_strength"]
    )
