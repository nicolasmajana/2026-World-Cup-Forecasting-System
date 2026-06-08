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
from data.features import (  # noqa: E402
    compute_team_rolling_strengths, add_elo_columns, build_match_features,
    build_fixture_feature_pair,
)
from model.poisson_model import (  # noqa: E402
    PoissonGoalModel, FEATURE_COLS,
)

TRAIN_CUTOFF = pd.Timestamp("2024-01-01")
MODEL_VERSION = "poisson-v2"


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


def feature_pair_for_match(m, rolling):
    """Build (home_features, away_features) dicts for one historical match,
    using the team's form and pre-match Elo as of that date. Returns None if
    either team lacks enough history."""
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


def main():
    print("Loading historical matches from DB…")
    hist = load_historical_from_db()
    print(f"  {len(hist):,} matches, {hist['match_date'].min().date()} -> "
          f"{hist['match_date'].max().date()}")

    print("Computing time-varying Elo from match history…")
    hist, latest_elo = add_elo_columns(hist)
    print(f"  Elo computed for {len(latest_elo)} teams.")

    print("Computing rolling attack/defense strengths…")
    rolling = compute_team_rolling_strengths(hist)

    train = hist[hist["match_date"] < TRAIN_CUTOFF]
    val = hist[hist["match_date"] >= TRAIN_CUTOFF]
    print(f"Train: {len(train):,}  |  Val: {len(val):,}")

    print("Building training features…")
    train_feats = build_match_features(train, rolling)
    print(f"  {len(train_feats):,} team-match training rows")

    print("Fitting Poisson model (competition-weighted)…")
    model = PoissonGoalModel().fit(
        train_feats, sample_weight=train_feats["weight"].to_numpy()
    )

    print("Evaluating on 2024-2025 hold-out (Brier score)…")
    # Collect feature rows for every val match with enough history, then score
    # them all in ONE vectorized call (exact analytic probabilities).
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
              "elo": "self-computed time-varying", "competition_weighted": True}
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
    print("\nSample 2026 predictions (using each team's latest form + Elo):")
    show_sample_predictions(model, rolling, latest_elo, conn)
    conn.close()


def show_sample_predictions(model, rolling, latest_elo, conn):
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
        pair = build_fixture_feature_pair(
            m["home_code"], m["away_code"], rolling, latest_elo
        )
        if pair is None:
            continue
        p = model.predict_match(pair[0], pair[1])
        print(f"\n  {m['home']} vs {m['away']}  (Group {m['group_name']})")
        print(f"    xG: {p['xg_home']:.2f} - {p['xg_away']:.2f}")
        print(f"    {m['home']} win {p['p_home_win']*100:4.1f}%  |  "
              f"Draw {p['p_draw']*100:4.1f}%  |  "
              f"{m['away']} win {p['p_away_win']*100:4.1f}%")


if __name__ == "__main__":
    main()
