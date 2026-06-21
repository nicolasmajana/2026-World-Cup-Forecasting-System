"""
Experiment: Bivariate Poisson correlation term (Dixon-Coles style).

The existing model predicts lambda_h and lambda_a independently (two separate
Poisson processes). Under the bivariate Poisson, goals are instead:

  X = X* + Z,  X* ~ Poisson(lambda_h - lam3)
  Y = Y* + Z,  Y* ~ Poisson(lambda_a - lam3)
  Z            ~ Poisson(lam3), independent of X*, Y*

This adds positive correlation (Cov(X,Y) = lam3) while preserving marginal
means. The key mathematical identity: P(home win), P(draw), P(away win) under
bivariate Poisson equal the independent Poisson probabilities computed at
shifted lambdas (lambda_h - lam3, lambda_a - lam3). So the experiment reduces
to: does subtracting a global constant from both predicted lambdas lower Brier?

If the model over-predicts expected goals, lam3 > 0 would tighten the
distributions and shift probability mass toward draws.

Design:
- Tune lam3 on val1 (2024 matches), evaluate on val2 (2025 matches).
- No training-set data is used for tuning, avoiding leakage.

Champion: poisson-v2 Brier 0.17154 (train pre-2024, val 2024-2025)
"""

import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import poisson

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../pipeline/.env"))

from data.loader import load_historical_from_db
from data.features import (
    compute_team_rolling_strengths, add_elo_columns, build_match_features,
)
from model.poisson_model import PoissonGoalModel, FEATURE_COLS
from model.train import feature_pair_for_match

TRAIN_CUTOFF = pd.Timestamp("2024-01-01")
VAL1_CUTOFF = pd.Timestamp("2025-01-01")


def collect_lambdas(matches, model, rolling):
    """Return (lam_h, lam_a, outcomes) arrays for val matches with enough history."""
    home_rows, away_rows, outcomes = [], [], []
    for _, m in matches.iterrows():
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
    lam_h = model.predict_lambda(home_df)
    lam_a = model.predict_lambda(away_df)
    return lam_h, lam_a, np.array(outcomes, dtype=float)


def wdl_brier(lam_h, lam_a, outcomes, lam3=0.0, max_goals=15):
    """Brier score under independent Poisson at (lam_h - lam3, lam_a - lam3)."""
    l1 = np.maximum(lam_h - lam3, 1e-6)
    l2 = np.maximum(lam_a - lam3, 1e-6)
    ks = np.arange(max_goals + 1)
    ph = poisson.pmf(ks[None, :], l1[:, None])
    pa = poisson.pmf(ks[None, :], l2[:, None])
    p_draw = (ph * pa).sum(axis=1)
    cum_pa = np.cumsum(pa, axis=1)
    pa_lt = np.concatenate([np.zeros((pa.shape[0], 1)), cum_pa[:, :-1]], axis=1)
    p_home_win = (ph * pa_lt).sum(axis=1)
    p_away_win = 1.0 - p_draw - p_home_win
    probs = np.column_stack([p_home_win, p_draw, p_away_win])
    return float(((probs - outcomes) ** 2).mean(axis=1).mean())


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
    val1 = val[val["match_date"] < VAL1_CUTOFF]
    val2 = val[val["match_date"] >= VAL1_CUTOFF]
    print(f"Train: {len(train):,}  |  Val1(2024): {len(val1):,}  |  Val2(2025): {len(val2):,}")

    print("Fitting model on training set...")
    train_feats = build_match_features(train, rolling)
    model = PoissonGoalModel().fit(
        train_feats, sample_weight=train_feats["weight"].to_numpy()
    )

    print("Collecting val1 lambdas (tune set)...")
    lam_h1, lam_a1, out1 = collect_lambdas(val1, model, rolling)
    print(f"  {len(lam_h1):,} matches with enough history")

    print("Collecting val2 lambdas (test set)...")
    lam_h2, lam_a2, out2 = collect_lambdas(val2, model, rolling)
    print(f"  {len(lam_h2):,} matches with enough history")

    base_val2 = wdl_brier(lam_h2, lam_a2, out2, lam3=0.0)
    base_full = wdl_brier(
        np.concatenate([lam_h1, lam_h2]),
        np.concatenate([lam_a1, lam_a2]),
        np.concatenate([out1, out2]),
        lam3=0.0,
    )
    print(f"\nBaseline (lam3=0) val2 Brier:  {base_val2:.5f}")
    print(f"Baseline (lam3=0) full val Brier: {base_full:.5f}")

    print("\nGrid-searching lam3 on val1 (2024)...")
    lam3_grid = np.linspace(0.0, 0.5, 26)
    results = []
    for lam3 in lam3_grid:
        b = wdl_brier(lam_h1, lam_a1, out1, lam3)
        results.append((lam3, b))
        print(f"  lam3={lam3:.2f}  val1 Brier={b:.5f}")

    best_lam3, best_val1_brier = min(results, key=lambda x: x[1])
    print(f"\nBest lam3 (val1): {best_lam3:.2f}  (val1 Brier={best_val1_brier:.5f})")

    exp_val2 = wdl_brier(lam_h2, lam_a2, out2, lam3=best_lam3)
    delta = exp_val2 - base_val2
    print(f"\nBivariate Poisson (lam3={best_lam3:.2f}) val2 Brier: {exp_val2:.5f}")
    print(f"Baseline                          val2 Brier: {base_val2:.5f}")
    print(f"Delta: {delta:+.5f}")

    if delta < -0.0001:
        print("\n=> IMPROVEMENT: bivariate Poisson wins. Consider applying to poisson-v3.")
    else:
        print("\n=> No meaningful improvement. Discard.")


if __name__ == "__main__":
    main()
