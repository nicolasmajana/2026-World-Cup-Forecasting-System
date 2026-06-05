"""
Train the Poisson model on pre-2024 internationals, validate on 2024-2025,
log the run to `model_runs`, and print a few real 2026 predictions.

Usage:
    python pipeline/model/train.py
"""

import os
import sys
import json
import subprocess

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection, load_historical_from_db  # noqa: E402
from data.features import compute_team_rolling_strengths, build_match_features  # noqa: E402
from model.poisson_model import (  # noqa: E402
    PoissonGoalModel, brier_score, FEATURE_COLS,
)

TRAIN_CUTOFF = pd.Timestamp("2024-01-01")
MODEL_VERSION = "poisson-v1"


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def feature_pair_for_match(m, rolling, elo_map):
    """Build (home_features, away_features) dicts for one match row, or None."""
    out = {}
    for side, opp in (("home", "away"), ("away", "home")):
        code, opp_code = m[f"{side}_code"], m[f"{opp}_code"]
        try:
            atk = rolling.loc[(m["match_date"], code), "attack_strength"]
            dfs = rolling.loc[(m["match_date"], code), "defense_strength"]
            opp_dfs = rolling.loc[(m["match_date"], opp_code), "defense_strength"]
        except KeyError:
            return None
        if pd.isna(atk) or pd.isna(dfs) or pd.isna(opp_dfs):
            return None
        venue_enc = 1 if side == "home" and m["venue_type"] == "home" else (
            -1 if side == "away" and m["venue_type"] == "away" else 0
        )
        out[side] = {
            "attack_strength": atk, "defense_strength": dfs,
            "opp_defense_strength": opp_dfs,
            "elo": elo_map.get(code, 1500), "venue_enc": venue_enc,
        }
    return out["home"], out["away"]


def main():
    print("Loading historical matches from DB…")
    hist = load_historical_from_db()
    print(f"  {len(hist):,} matches, {hist['match_date'].min().date()} -> "
          f"{hist['match_date'].max().date()}")

    print("Computing rolling attack/defense strengths…")
    rolling = compute_team_rolling_strengths(hist)

    # Elo not yet loaded — all teams default to 1500 (constant feature for v1).
    elo_map: dict[str, int] = {}

    train = hist[hist["match_date"] < TRAIN_CUTOFF]
    val = hist[hist["match_date"] >= TRAIN_CUTOFF]
    print(f"Train: {len(train):,}  |  Val: {len(val):,}")

    print("Building training features…")
    train_feats = build_match_features(train, elo_map, rolling)
    print(f"  {len(train_feats):,} team-match training rows")

    print("Fitting Poisson model…")
    model = PoissonGoalModel().fit(train_feats)

    print("Evaluating on 2024-2025 hold-out (Brier score)…")
    briers, base_briers = [], []
    # base rate for a naive baseline (home/draw/away frequencies in train)
    base = [
        (train["home_goals"] > train["away_goals"]).mean(),
        (train["home_goals"] == train["away_goals"]).mean(),
        (train["home_goals"] < train["away_goals"]).mean(),
    ]
    for _, m in val.iterrows():
        pair = feature_pair_for_match(m, rolling, elo_map)
        if pair is None:
            continue
        pred = model.predict_match(pair[0], pair[1])
        briers.append(brier_score(pred, m["home_goals"], m["away_goals"]))
        base_briers.append(
            brier_score(
                {"p_home_win": base[0], "p_draw": base[1], "p_away_win": base[2]},
                m["home_goals"], m["away_goals"],
            )
        )

    val_brier = float(np.mean(briers))
    base_brier = float(np.mean(base_briers))
    print(f"\n  Model Brier:    {val_brier:.4f}  (lower is better)")
    print(f"  Baseline Brier: {base_brier:.4f}  (always predict base rates)")
    print(f"  Evaluated on {len(briers):,} matches with enough history.")
    improvement = (base_brier - val_brier) / base_brier * 100
    print(f"  Improvement over baseline: {improvement:+.1f}%")

    # ── Log the run ───────────────────────────────────────────────
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO model_runs
                (model_version, train_cutoff, val_brier_score,
                 n_train_matches, parameters, git_sha)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (MODEL_VERSION, TRAIN_CUTOFF.date(), round(val_brier, 5),
             len(train_feats),
             json.dumps({"alpha": 0.1, "features": FEATURE_COLS,
                         "n_sims": 10000, "elo_loaded": False}),
             git_sha()),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    print(f"\nLogged model_run id={run_id}.")

    # ── Show a few real 2026 predictions ──────────────────────────
    print("\nSample 2026 predictions (using each team's latest form):")
    show_sample_predictions(model, rolling, elo_map, conn)
    conn.close()


def latest_strength(rolling, code):
    """Most recent rolling attack/defense for a team code."""
    try:
        sub = rolling.xs(code, level="team_code").dropna()
        if sub.empty:
            return None
        last = sub.iloc[-1]
        return last["attack_strength"], last["defense_strength"]
    except KeyError:
        return None


def show_sample_predictions(model, rolling, elo_map, conn):
    df = pd.read_sql(
        """
        SELECT ht.fifa_code AS home_code, ht.name AS home,
               at.fifa_code AS away_code, at.name AS away,
               f.kickoff_utc, f.group_name
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        WHERE f.stage = 'group'
        ORDER BY f.kickoff_utc
        LIMIT 5
        """,
        conn,
    )
    for _, m in df.iterrows():
        hs = latest_strength(rolling, m["home_code"])
        as_ = latest_strength(rolling, m["away_code"])
        if hs is None or as_ is None:
            continue
        home_f = {"attack_strength": hs[0], "defense_strength": hs[1],
                  "opp_defense_strength": as_[1],
                  "elo": elo_map.get(m["home_code"], 1500), "venue_enc": 0}
        away_f = {"attack_strength": as_[0], "defense_strength": as_[1],
                  "opp_defense_strength": hs[1],
                  "elo": elo_map.get(m["away_code"], 1500), "venue_enc": 0}
        p = model.predict_match(home_f, away_f)
        print(f"\n  {m['home']} vs {m['away']}  (Group {m['group_name']})")
        print(f"    xG: {p['xg_home']:.2f} - {p['xg_away']:.2f}")
        print(f"    {m['home']} win {p['p_home_win']*100:4.1f}%  |  "
              f"Draw {p['p_draw']*100:4.1f}%  |  "
              f"{m['away']} win {p['p_away_win']*100:4.1f}%")


if __name__ == "__main__":
    main()
