"""
Experiment: add 'days_since_last_match' feature for each team side.

Hypothesis: freshness/fatigue matters. A team playing 3 days after a hard
qualifier may perform differently than one with 10 days of prep time. The
feature is the number of days elapsed since that team's previous game.

This script trains an augmented model alongside the baseline and compares
hold-out Brier scores. It does NOT modify production code; if this wins,
the change goes into features.py and poisson_model.py manually.

Champion: poisson-v2 Brier 0.17154  (baseline 0.21208)
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../pipeline/.env"))
from data.loader import load_historical_from_db
from data.features import (
    compute_team_rolling_strengths, add_elo_columns, build_match_features,
)
from model.poisson_model import PoissonGoalModel, FEATURE_COLS

TRAIN_CUTOFF = pd.Timestamp("2024-01-01")
MEDIAN_FILL_DAYS = 30  # imputation for a team's very first recorded game


def compute_days_rest(matches: pd.DataFrame) -> pd.DataFrame:
    """Return a Series indexed by (match_date, team_code) giving days since
    that team's previous game. First game per team gets MEDIAN_FILL_DAYS."""
    home = matches[["match_date", "home_code"]].rename(columns={"home_code": "team_code"})
    away = matches[["match_date", "away_code"]].rename(columns={"away_code": "team_code"})
    all_games = (
        pd.concat([home, away])
        .drop_duplicates()
        .sort_values(["team_code", "match_date"])
    )
    all_games["prev_date"] = all_games.groupby("team_code")["match_date"].shift(1)
    all_games["days_rest"] = (
        all_games["match_date"] - all_games["prev_date"]
    ).dt.days.fillna(MEDIAN_FILL_DAYS)
    return all_games.set_index(["match_date", "team_code"])["days_rest"]


def build_features_with_rest(matches, rolling):
    """Same as build_match_features but adds days_rest_norm (standardized
    days-since-last-game) and days_rest_diff (home minus away)."""
    base = build_match_features(matches, rolling)

    days = compute_days_rest(matches)

    flat = rolling.reset_index()

    def side_rest(team_col, opp_col, goals_col, elo_col, opp_elo_col,
                  venue_val, venue_sign):
        own = flat.rename(columns={"team_code": team_col})
        m = matches.merge(own, on=["match_date", team_col], how="left")
        opp = flat.rename(
            columns={"team_code": opp_col, "defense_strength": "opp_defense_strength"}
        )[["match_date", opp_col, "opp_defense_strength"]]
        m = m.merge(opp, on=["match_date", opp_col], how="left")
        df = pd.DataFrame({
            "match_date": m["match_date"],
            "team_code": m[team_col],
            "goals_scored": m[goals_col],
            "attack_strength": m["attack_strength"],
            "defense_strength": m["defense_strength"],
            "opp_defense_strength": m["opp_defense_strength"],
            "elo": m[elo_col],
            "elo_diff": m[elo_col] - m[opp_elo_col],
            "venue_enc": np.where(m["venue_type"] == venue_val, venue_sign, 0),
            "opp_team_code": m[opp_col],
            "weight": m["tournament"].map(
                lambda t: (
                    1.6 if ("world cup" in (t or "").lower() and "qualif" not in (t or "").lower())
                    else 1.2 if "qualif" in (t or "").lower()
                    else 0.5 if "friendly" in (t or "").lower()
                    else 1.0
                )
            ),
        })
        idx = df.set_index(["match_date", "team_code"]).index
        df["days_rest"] = days.reindex(idx).values
        df["opp_days_rest"] = days.reindex(
            pd.MultiIndex.from_arrays([df["match_date"], df["opp_team_code"]])
        ).values
        return df.drop(columns=["opp_team_code"])

    home_side = side_rest("home_code", "away_code", "home_goals",
                          "home_elo_pre", "away_elo_pre", "home", 1)
    away_side = side_rest("away_code", "home_code", "away_goals",
                          "away_elo_pre", "home_elo_pre", "away", -1)
    feats = pd.concat([home_side, away_side], ignore_index=True).dropna(
        subset=["attack_strength", "defense_strength", "opp_defense_strength"]
    )
    feats["days_rest"] = feats["days_rest"].fillna(MEDIAN_FILL_DAYS)
    feats["opp_days_rest"] = feats["opp_days_rest"].fillna(MEDIAN_FILL_DAYS)
    feats["days_rest_diff"] = feats["days_rest"] - feats["opp_days_rest"]
    return feats


FEATURE_COLS_EXT = FEATURE_COLS + ["days_rest", "days_rest_diff"]


def train_and_eval(feats_train, val_matches, rolling, feature_cols):
    from sklearn.linear_model import PoissonRegressor
    from sklearn.preprocessing import StandardScaler
    from scipy.stats import poisson

    scaler = StandardScaler()
    X_train = scaler.fit_transform(feats_train[feature_cols])
    y_train = feats_train["goals_scored"].values
    w_train = feats_train["weight"].values
    mdl = PoissonRegressor(alpha=0.1, max_iter=300)
    mdl.fit(X_train, y_train, sample_weight=w_train)

    home_rows, away_rows, outcomes = [], [], []
    days_series = compute_days_rest(val_matches.assign(match_date=val_matches["match_date"]))

    for _, m in val_matches.iterrows():
        try:
            h_atk = rolling.loc[(m["match_date"], m["home_code"]), "attack_strength"]
            h_def = rolling.loc[(m["match_date"], m["home_code"]), "defense_strength"]
            a_atk = rolling.loc[(m["match_date"], m["away_code"]), "attack_strength"]
            a_def = rolling.loc[(m["match_date"], m["away_code"]), "defense_strength"]
        except KeyError:
            continue
        if any(pd.isna(v) for v in (h_atk, h_def, a_atk, a_def)):
            continue

        he, ae = m["home_elo_pre"], m["away_elo_pre"]

        h_rest = days_series.get((m["match_date"], m["home_code"]), MEDIAN_FILL_DAYS)
        a_rest = days_series.get((m["match_date"], m["away_code"]), MEDIAN_FILL_DAYS)

        home_f = {"attack_strength": h_atk, "defense_strength": h_def,
                  "opp_defense_strength": a_def, "elo": he, "elo_diff": he - ae,
                  "venue_enc": 1 if m["venue_type"] == "home" else 0,
                  "days_rest": h_rest, "days_rest_diff": h_rest - a_rest}
        away_f = {"attack_strength": a_atk, "defense_strength": a_def,
                  "opp_defense_strength": h_def, "elo": ae, "elo_diff": ae - he,
                  "venue_enc": -1 if m["venue_type"] == "away" else 0,
                  "days_rest": a_rest, "days_rest_diff": a_rest - h_rest}
        home_rows.append(home_f)
        away_rows.append(away_f)
        if m["home_goals"] > m["away_goals"]:
            outcomes.append([1, 0, 0])
        elif m["home_goals"] == m["away_goals"]:
            outcomes.append([0, 1, 0])
        else:
            outcomes.append([0, 0, 1])

    if not home_rows:
        return float("nan"), 0

    home_df = pd.DataFrame(home_rows)[feature_cols]
    away_df = pd.DataFrame(away_rows)[feature_cols]
    outcomes = np.array(outcomes, dtype=float)

    lam_h = mdl.predict(scaler.transform(home_df))
    lam_a = mdl.predict(scaler.transform(away_df))
    ks = np.arange(0, 16)
    ph = poisson.pmf(ks[None, :], lam_h[:, None])
    pa = poisson.pmf(ks[None, :], lam_a[:, None])
    p_draw = (ph * pa).sum(axis=1)
    cum_pa = np.cumsum(pa, axis=1)
    pa_lt = np.concatenate([np.zeros((pa.shape[0], 1)), cum_pa[:, :-1]], axis=1)
    p_home_win = (ph * pa_lt).sum(axis=1)
    p_away_win = 1.0 - p_draw - p_home_win
    probs = np.column_stack([p_home_win, p_draw, p_away_win])
    briers = ((probs - outcomes) ** 2).mean(axis=1)
    return float(briers.mean()), len(briers)


def main():
    print("Loading historical matches...")
    hist = load_historical_from_db()
    print(f"  {len(hist):,} matches loaded")

    print("Computing Elo...")
    hist, _ = add_elo_columns(hist)

    print("Computing rolling strengths...")
    rolling = compute_team_rolling_strengths(hist)

    train = hist[hist["match_date"] < TRAIN_CUTOFF]
    val = hist[hist["match_date"] >= TRAIN_CUTOFF]
    print(f"Train: {len(train):,}  |  Val: {len(val):,}")

    print("\n--- Baseline (no days-of-rest) ---")
    base_feats = build_match_features(train, rolling)
    base_brier, n_base = train_and_eval(
        build_match_features(train, rolling), val, rolling, FEATURE_COLS
    )
    print(f"Baseline Brier: {base_brier:.5f}  (n={n_base:,})")

    print("\n--- Experiment: + days_rest + days_rest_diff ---")
    exp_feats = build_features_with_rest(train, rolling)
    exp_brier, n_exp = train_and_eval(
        exp_feats, val, rolling, FEATURE_COLS_EXT
    )
    print(f"Experiment Brier: {exp_brier:.5f}  (n={n_exp:,})")

    delta = exp_brier - base_brier
    print(f"\nDelta: {delta:+.5f}  ({'IMPROVEMENT' if delta < 0 else 'REGRESSION'})")
    if delta < 0:
        print("=> New feature WINS. Apply to production.")
    else:
        print("=> No improvement. Discard; do not change production code.")


if __name__ == "__main__":
    main()
