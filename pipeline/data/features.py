"""Build the feature matrix for the Poisson regression model.

v2 adds a self-computed, time-varying Elo rating (so team strength and
strength-of-schedule are real signals across all 49k training matches, instead
of relying on the partial external Elo we had before), an Elo-difference
feature, and competition-based sample weights (a World Cup result counts for
more than a friendly).
"""

import numpy as np
import pandas as pd


ROLLING_WINDOW = 10  # matches
ELO_K = 30.0         # Elo update step
ELO_HOME_ADV = 100.0  # Elo points of home advantage (non-neutral only)
DEFAULT_ELO = 1500.0


def compute_team_rolling_strengths(matches: pd.DataFrame) -> pd.DataFrame:
    """Rolling attack/defense (mean goals for/against over the previous
    ROLLING_WINDOW games) per team, indexed by (match_date, team_code)."""
    home_rows = matches[["match_date", "home_code", "home_goals", "away_goals"]].copy()
    home_rows.columns = ["match_date", "team_code", "goals_scored", "goals_conceded"]
    away_rows = matches[["match_date", "away_code", "away_goals", "home_goals"]].copy()
    away_rows.columns = ["match_date", "team_code", "goals_scored", "goals_conceded"]

    team_games = pd.concat([home_rows, away_rows]).sort_values(
        ["team_code", "match_date"]
    )
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
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def add_elo_columns(matches: pd.DataFrame):
    """Walk matches in date order, maintaining an Elo rating per team. Adds
    `home_elo_pre` / `away_elo_pre` (each team's rating BEFORE that match) and
    returns (annotated_matches, latest_elo_dict).

    Strength-of-schedule falls out naturally: beating a strong team gains more
    rating than beating a weak one, and a margin multiplier rewards big wins.
    """
    matches = matches.sort_values("match_date").reset_index(drop=True)
    hc = matches["home_code"].to_numpy()
    ac = matches["away_code"].to_numpy()
    hg = matches["home_goals"].to_numpy()
    ag = matches["away_goals"].to_numpy()
    venue = matches["venue_type"].to_numpy()

    elo: dict[str, float] = {}
    home_pre = np.empty(len(matches))
    away_pre = np.empty(len(matches))

    for i in range(len(matches)):
        rh = elo.get(hc[i], DEFAULT_ELO)
        ra = elo.get(ac[i], DEFAULT_ELO)
        home_pre[i] = rh
        away_pre[i] = ra

        adv = ELO_HOME_ADV if venue[i] == "home" else 0.0
        exp_home = 1.0 / (1.0 + 10 ** ((ra - rh - adv) / 400.0))
        if hg[i] > ag[i]:
            score = 1.0
        elif hg[i] == ag[i]:
            score = 0.5
        else:
            score = 0.0

        gd = abs(int(hg[i]) - int(ag[i]))
        mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8.0)
        delta = ELO_K * mult * (score - exp_home)
        elo[hc[i]] = rh + delta
        elo[ac[i]] = ra - delta

    matches["home_elo_pre"] = home_pre
    matches["away_elo_pre"] = away_pre
    return matches, elo


def competition_weight(tournament: str) -> float:
    """Sample weight by match importance: the World Cup itself counts most,
    friendlies least."""
    t = (tournament or "").lower()
    if "world cup" in t and "qualif" not in t:
        return 1.6
    if "qualif" in t:
        return 1.2
    if "friendly" in t:
        return 0.5
    return 1.0


def build_match_features(matches: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    """One row per team-in-a-match. `matches` must already carry the Elo
    columns from add_elo_columns()."""
    flat = rolling.reset_index()

    def side_frame(team_col, opp_col, goals_col, elo_col, opp_elo_col,
                   venue_val, venue_sign):
        own = flat.rename(columns={"team_code": team_col})
        m = matches.merge(own, on=["match_date", team_col], how="left")
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
            "elo": m[elo_col],
            "elo_diff": m[elo_col] - m[opp_elo_col],
            "venue_enc": np.where(m["venue_type"] == venue_val, venue_sign, 0),
            "weight": m["tournament"].map(competition_weight),
        })

    home = side_frame("home_code", "away_code", "home_goals",
                      "home_elo_pre", "away_elo_pre", "home", 1)
    away = side_frame("away_code", "home_code", "away_goals",
                      "away_elo_pre", "home_elo_pre", "away", -1)

    return pd.concat([home, away], ignore_index=True).dropna(
        subset=["attack_strength", "defense_strength", "opp_defense_strength"]
    )


def latest_strength(rolling: pd.DataFrame, code: str):
    """Most recent rolling attack/defense for a team, or None."""
    try:
        sub = rolling.xs(code, level="team_code").dropna()
    except KeyError:
        return None
    if sub.empty:
        return None
    last = sub.iloc[-1]
    return float(last["attack_strength"]), float(last["defense_strength"])


def build_fixture_feature_pair(home_code, away_code, rolling, latest_elo,
                               venue_enc=0):
    """Build (home_features, away_features) dicts for an upcoming fixture using
    each team's most recent form and current Elo. Returns None if either team
    lacks enough history."""
    hs = latest_strength(rolling, home_code)
    as_ = latest_strength(rolling, away_code)
    if hs is None or as_ is None:
        return None
    he = latest_elo.get(home_code, DEFAULT_ELO)
    ae = latest_elo.get(away_code, DEFAULT_ELO)
    home = {"attack_strength": hs[0], "defense_strength": hs[1],
            "opp_defense_strength": as_[1], "elo": he, "elo_diff": he - ae,
            "venue_enc": venue_enc}
    away = {"attack_strength": as_[0], "defense_strength": as_[1],
            "opp_defense_strength": hs[1], "elo": ae, "elo_diff": ae - he,
            "venue_enc": -venue_enc}
    return home, away
