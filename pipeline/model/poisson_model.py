"""Poisson regression model + Monte Carlo simulation."""

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import StandardScaler
from scipy.stats import poisson


FEATURE_COLS = [
    "attack_strength",
    "defense_strength",
    "opp_defense_strength",
    "elo",
    "elo_diff",
    "venue_enc",
]

N_SIMULATIONS = 10_000


class PoissonGoalModel:
    def __init__(self):
        self.model = PoissonRegressor(alpha=0.1, max_iter=300)
        self.scaler = StandardScaler()

    def fit(self, features: pd.DataFrame, sample_weight=None) -> "PoissonGoalModel":
        X = self.scaler.fit_transform(features[FEATURE_COLS])
        y = features["goals_scored"].values
        self.model.fit(X, y, sample_weight=sample_weight)
        return self

    def predict_lambda(self, features: pd.DataFrame) -> np.ndarray:
        X = self.scaler.transform(features[FEATURE_COLS])
        return self.model.predict(X)

    def predict_match(
        self,
        home_features: dict,
        away_features: dict,
    ) -> dict:
        """
        Given feature dicts for each team, run Monte Carlo and return probabilities.

        Returns:
            p_home_win, p_draw, p_away_win, xg_home, xg_away, features (snapshot)
        """
        home_df = pd.DataFrame([home_features])[FEATURE_COLS]
        away_df = pd.DataFrame([away_features])[FEATURE_COLS]

        xg_home = float(self.predict_lambda(home_df)[0])
        xg_away = float(self.predict_lambda(away_df)[0])

        home_goals = np.random.poisson(xg_home, N_SIMULATIONS)
        away_goals = np.random.poisson(xg_away, N_SIMULATIONS)

        p_home_win = float((home_goals > away_goals).mean())
        p_draw     = float((home_goals == away_goals).mean())
        p_away_win = float((home_goals < away_goals).mean())

        features_snapshot = {
            "home": home_features,
            "away": away_features,
            "xg_home": xg_home,
            "xg_away": xg_away,
        }

        return {
            "p_home_win": round(p_home_win, 4),
            "p_draw":     round(p_draw, 4),
            "p_away_win": round(p_away_win, 4),
            "xg_home":    round(xg_home, 2),
            "xg_away":    round(xg_away, 2),
            "features":   features_snapshot,
        }


    def predict_outcome_probs(
        self,
        home_features: pd.DataFrame,
        away_features: pd.DataFrame,
        max_goals: int = 15,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Vectorized, exact W/D/L probabilities for many matches at once.

        Instead of Monte Carlo per match, compute the analytic outcome
        probabilities from two independent Poisson(λ) distributions over a
        goal grid 0..max_goals. Returns (p_home_win, p_draw, p_away_win),
        each shape (n_matches,). This is exact (no sampling noise) and ~100x
        faster than looping predict_match — used for validation/backtesting.
        """
        lam_h = self.predict_lambda(home_features)   # (n,)
        lam_a = self.predict_lambda(away_features)   # (n,)
        ks = np.arange(0, max_goals + 1)
        ph = poisson.pmf(ks[None, :], lam_h[:, None])  # (n, G)
        pa = poisson.pmf(ks[None, :], lam_a[:, None])  # (n, G)

        p_draw = (ph * pa).sum(axis=1)
        cum_pa = np.cumsum(pa, axis=1)                  # P(away <= j)
        pa_lt = np.concatenate(
            [np.zeros((pa.shape[0], 1)), cum_pa[:, :-1]], axis=1
        )                                               # P(away < i)
        p_home_win = (ph * pa_lt).sum(axis=1)
        p_away_win = 1.0 - p_draw - p_home_win
        return p_home_win, p_draw, p_away_win


def brier_score(prediction: dict, home_goals: int, away_goals: int) -> float:
    """
    Multi-class Brier score for a single match.
    Outcome vector: [home_win, draw, away_win]
    """
    if home_goals > away_goals:
        outcome = [1, 0, 0]
    elif home_goals == away_goals:
        outcome = [0, 1, 0]
    else:
        outcome = [0, 0, 1]

    probs = [prediction["p_home_win"], prediction["p_draw"], prediction["p_away_win"]]
    return sum((p - o) ** 2 for p, o in zip(probs, outcome)) / 3
