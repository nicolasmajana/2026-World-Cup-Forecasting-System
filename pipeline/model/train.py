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


def connect_with_retry(attempts: int = 5, delay: float = 5.0):
    """Open a DB connection, retrying on transient network/DNS failures so a
    brief internet blip doesn't discard an expensive training run."""
    import time
    last = None
    for i in range(1, attempts + 1):
        try:
            return get_connection()
        except Exception as e:  # OperationalError (DNS, refused, etc.)
            last = e
            print(f"  DB connect attempt {i}/{attempts} failed: {e}".strip())
            if i < attempts:
                time.sleep(delay)
    raise last


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

    # Load Elo from the DB (teams.fifa_elo). Teams without a value fall back
    # to 1500 inside the feature builder.
    conn0 = get_connection()
    with conn0.cursor() as cur:
        cur.execute("SELECT fifa_code, fifa_elo FROM teams WHERE fifa_elo IS NOT NULL")
        elo_map = {code: elo for code, elo in cur.fetchall()}
    conn0.close()
    print(f"Loaded Elo for {len(elo_map)} teams.")

    train = hist[hist["match_date"] < TRAIN_CUTOFF]
    val = hist[hist["match_date"] >= TRAIN_CUTOFF]
    print(f"Train: {len(train):,}  |  Val: {len(val):,}")

    print("Building training features…")
    train_feats = build_match_features(train, elo_map, rolling)
    print(f"  {len(train_feats):,} team-match training rows")

    print("Fitting Poisson model…")
    model = PoissonGoalModel().fit(train_feats)

    print("Evaluating on 2024-2025 hold-out (Brier score)…")
    # Collect feature rows for every val match with enough history, then score
    # them all in ONE vectorized call (exact analytic probabilities).
    home_rows, away_rows, outcomes = [], [], []
    for _, m in val.iterrows():
        pair = feature_pair_for_match(m, rolling, elo_map)
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

    p_h, p_d, p_a = model.predict_outcome_probs(home_df, away_df)
    probs = np.column_stack([p_h, p_d, p_a])
    # multi-class Brier: mean over matches of mean squared error across 3 classes
    briers = ((probs - outcomes) ** 2).mean(axis=1)

    # naive baseline: always predict the train-set base rates
    base = np.array([
        (train["home_goals"] > train["away_goals"]).mean(),
        (train["home_goals"] == train["away_goals"]).mean(),
        (train["home_goals"] < train["away_goals"]).mean(),
    ])
    base_briers = ((base[None, :] - outcomes) ** 2).mean(axis=1)

    val_brier = float(briers.mean())
    base_brier = float(base_briers.mean())
    print(f"\n  Model Brier:    {val_brier:.4f}  (lower is better)")
    print(f"  Baseline Brier: {base_brier:.4f}  (always predict base rates)")
    print(f"  Evaluated on {len(briers):,} matches with enough history.")
    improvement = (base_brier - val_brier) / base_brier * 100
    print(f"  Improvement over baseline: {improvement:+.1f}%")

    # ── Persist results LOCALLY first, so the expensive compute is never
    #    lost to a network blip during the DB write. ────────────────
    params = {"alpha": 0.1, "features": FEATURE_COLS, "n_sims": 10000,
              "elo_loaded": len(elo_map) > 0}
    result = {
        "model_version": MODEL_VERSION,
        "train_cutoff": str(TRAIN_CUTOFF.date()),
        "val_brier_score": round(val_brier, 5),
        "baseline_brier": round(base_brier, 5),
        "n_train_matches": len(train_feats),
        "n_val_matches": len(briers),
        "parameters": params,
        "git_sha": git_sha(),
    }
    results_path = os.path.join(os.path.dirname(__file__), "last_run.json")
    with open(results_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved results to {results_path}")

    # ── Log the run to the DB (with retry on transient failures) ───
    conn = connect_with_retry()
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
             len(train_feats), json.dumps(params), git_sha()),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    print(f"Logged model_run id={run_id}.")

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
