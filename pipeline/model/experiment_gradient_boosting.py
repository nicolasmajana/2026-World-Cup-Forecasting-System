"""
Experiment: gradient boosting (HistGradientBoostingRegressor, Poisson loss)
as a drop-in replacement for the linear PoissonRegressor.

Hypothesis: the true relationship between attack/defense strength, Elo, and
goals may be nonlinear (e.g. diminishing returns at Elo extremes, interaction
between attack_strength and opp_defense_strength). Gradient boosting with a
Poisson objective predicts the same kind of goal rate (lambda) as the linear
model, so the downstream analytic W/D/L formula is unchanged; only the
lambda estimator changes.

This script trains the GBM alongside the baseline PoissonRegressor on the
exact same features (FEATURE_COLS) and compares hold-out Brier. It does NOT
modify production code; if this wins, the change goes into poisson_model.py
manually and MODEL_VERSION gets bumped.

Champion: poisson-v2 Brier 0.17154 (baseline naive Brier 0.21208)
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


def feature_pair_for_match(m, rolling):
    try:
        h_atk = rolling.loc[(m["match_date"], m["home_code"]), "attack_strength"]
        h_def = rolling.loc[(m["match_date"], m["home_code"]), "defense_strength"]
        a_atk = rolling.loc[(m["match_date"], m["away_code"]), "attack_strength"]
        a_def = rolling.loc[(m["match_date"], m["away_code"]), "defense_strength"]
    except KeyError:
        return None
    if any(pd.isna(v) for v in (h_atk, h_def, a_atk, a_def)):
        return None
    he, ae = m["home_elo_pre"], m["away_elo_pre"]
    home = {"attack_strength": h_atk, "defense_strength": h_def,
            "opp_defense_strength": a_def, "elo": he, "elo_diff": he - ae,
            "venue_enc": 1 if m["venue_type"] == "home" else 0}
    away = {"attack_strength": a_atk, "defense_strength": a_def,
            "opp_defense_strength": h_def, "elo": ae, "elo_diff": ae - he,
            "venue_enc": -1 if m["venue_type"] == "away" else 0}
    return home, away


def build_val_arrays(val, rolling):
    home_rows, away_rows, outcomes = [], [], []
    for _, m in val.iterrows():
        pair = feature_pair_for_match(m, rolling)
        if pair is None:
            continue
        home_rows.append(pair[0])
        away_rows.append(pair[1])
        if m["home_goals"] > m["away_goals"]:
            outcomes.append([1, 0, 0])
        elif m["home_goals"] == m["away_goals"]:
            outcomes.append([0, 1, 0])
        else:
            outcomes.append([0, 0, 1])
    home_df = pd.DataFrame(home_rows)[FEATURE_COLS]
    away_df = pd.DataFrame(away_rows)[FEATURE_COLS]
    outcomes = np.array(outcomes, dtype=float)
    return home_df, away_df, outcomes


def brier_from_lambdas(lam_h, lam_a, outcomes, max_goals=15):
    from scipy.stats import poisson
    ks = np.arange(0, max_goals + 1)
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

    print("Building training features...")
    train_feats = build_match_features(train, rolling)
    print(f"  {len(train_feats):,} team-match training rows")

    print("Building validation arrays...")
    home_df, away_df, outcomes = build_val_arrays(val, rolling)
    print(f"  {len(outcomes):,} val matches with enough history")

    print("\n--- Baseline: linear PoissonRegressor (poisson-v2, current champion) ---")
    base_model = PoissonGoalModel().fit(
        train_feats, sample_weight=train_feats["weight"].to_numpy()
    )
    p_h, p_d, p_a = base_model.predict_outcome_probs(home_df, away_df)
    probs = np.column_stack([p_h, p_d, p_a])
    base_brier = float(((probs - outcomes) ** 2).mean())
    print(f"Baseline Brier: {base_brier:.5f}")

    print("\n--- Experiment: HistGradientBoostingRegressor (Poisson loss) ---")
    from sklearn.ensemble import HistGradientBoostingRegressor

    X_train = train_feats[FEATURE_COLS].to_numpy()
    y_train = train_feats["goals_scored"].to_numpy()
    w_train = train_feats["weight"].to_numpy()

    results = []
    for max_leaf, max_iter, l2 in [
        (15, 100, 1.0),
        (31, 100, 1.0),
        (15, 200, 1.0),
        (31, 200, 0.1),
    ]:
        gbm = HistGradientBoostingRegressor(
            loss="poisson", max_leaf_nodes=max_leaf, max_iter=max_iter,
            l2_regularization=l2, learning_rate=0.05, random_state=42,
        )
        gbm.fit(X_train, y_train, sample_weight=w_train)
        lam_h = gbm.predict(home_df.to_numpy())
        lam_a = gbm.predict(away_df.to_numpy())
        # guard against degenerate near-zero lambdas breaking the Poisson pmf
        lam_h = np.clip(lam_h, 1e-3, None)
        lam_a = np.clip(lam_a, 1e-3, None)
        brier, n = brier_from_lambdas(lam_h, lam_a, outcomes)
        results.append((max_leaf, max_iter, l2, brier))
        print(f"  max_leaf_nodes={max_leaf:3d} max_iter={max_iter:3d} l2={l2:.1f}  "
              f"-> Brier {brier:.5f}  (n={n:,})")

    best = min(results, key=lambda r: r[3])
    print(f"\nBest GBM config: max_leaf_nodes={best[0]} max_iter={best[1]} "
          f"l2={best[2]} -> Brier {best[3]:.5f}")

    delta = best[3] - base_brier
    print(f"\nDelta vs poisson-v2: {delta:+.5f}  "
          f"({'IMPROVEMENT' if delta < 0 else 'REGRESSION'})")
    if delta < 0:
        print("=> GBM WINS. Consider promoting to production (bump MODEL_VERSION).")
    else:
        print("=> No improvement. Discard; do not change production code.")


if __name__ == "__main__":
    main()
