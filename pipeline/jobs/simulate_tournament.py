"""
Full-tournament Monte Carlo: simulate the 2026 World Cup from groups through
the final thousands of times, then store each team's probability of winning
its group, reaching each round, and lifting the trophy, plus the single most
likely bracket.

Bracket wiring comes from openfootball (1A = winner Group A, 2B = runner-up,
3A/B/C/D/F = a qualifying third place from one of those groups, W74 = winner of
match 74). Match outcomes come from the v2 Poisson model: we precompute an
expected-goals matrix for every possible matchup, then sample scorelines.

Usage:
    python pipeline/jobs/simulate_tournament.py [n_sims]
"""

import os
import sys
import json
from collections import defaultdict, Counter

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import get_connection, load_historical_from_db  # noqa: E402
from data.features import (  # noqa: E402
    compute_team_rolling_strengths, add_elo_columns, build_match_features,
    latest_strength, DEFAULT_ELO,
)
from data.load_fixtures import FIXTURES_URL, stage_for  # noqa: E402
from model.poisson_model import PoissonGoalModel, FEATURE_COLS  # noqa: E402

N_SIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
PLAYOFF = "PO1"  # placeholder for the one unresolved (intercontinental playoff) slot

MIGRATION = os.path.join(
    os.path.dirname(__file__), "..", "..", "db", "migrations",
    "004_tournament_sim.sql",
)

ROUND_OF = {  # match num -> round key (for "reached round" tallies)
    **{n: "r32" for n in range(73, 89)},
    **{n: "r16" for n in range(89, 97)},
    **{n: "qf" for n in range(97, 101)},
    **{n: "sf" for n in range(101, 103)},
    103: "final",
}


# ────────────────────────────────────────────────────────────────────
# Setup: model, teams, expected-goals matrix, bracket structure
# ────────────────────────────────────────────────────────────────────
def build_xg_matrix(model, comp, teams):
    """Expected goals for the attacking team in every ordered matchup."""
    rows, idx = [], []
    for h in teams:
        ah, dh, eh = comp[h]
        for a in teams:
            if h == a:
                continue
            aa, da, ea = comp[a]
            rows.append({
                "attack_strength": ah, "defense_strength": dh,
                "opp_defense_strength": da, "elo": eh, "elo_diff": eh - ea,
                "venue_enc": 0,
            })
            idx.append((h, a))
    lam = model.predict_lambda(pd.DataFrame(rows)[FEATURE_COLS])
    lam = np.clip(lam, 0.05, 6.0)
    return {pair: float(lam[k]) for k, pair in enumerate(idx)}


def parse_bracket():
    """Return (ko_matches, third_slots).
    ko_matches: list of dicts {num, round, ref1, ref2} in play order.
    third_slots: list of (num_side_key, allowed_group_set) for 3rd-place slots."""
    data = requests.get(FIXTURES_URL, timeout=30).json()
    ko, third_slots = [], []
    for m in data["matches"]:
        if "Matchday" in m.get("round", ""):
            continue
        num = m.get("num")
        rnd = m.get("round", "")
        if num is None:  # Final / third place
            num = 103 if rnd == "Final" else 104
        ref1, ref2 = m.get("team1"), m.get("team2")
        for side, ref in (("1", ref1), ("2", ref2)):
            if isinstance(ref, str) and ref.startswith("3") and "/" in ref:
                allowed = set(ref[1:].split("/"))
                third_slots.append((f"{num}:{side}", allowed))
        ko.append({"num": num, "round": stage_for(rnd), "ref1": ref1, "ref2": ref2})
    ko.sort(key=lambda x: x["num"])
    return ko, third_slots


def assign_thirds(third_teams, third_slots):
    """Constrained assignment of the 8 qualifying third-place teams to the 8
    third-place R32 slots (each slot only accepts certain groups)."""
    slots = sorted(third_slots, key=lambda s: len(s[1]))  # most constrained first
    result, used = {}, set()

    def bt(i):
        if i == len(slots):
            return True
        key, allowed = slots[i]
        for code, grp in third_teams:
            if code in used or grp not in allowed:
                continue
            used.add(code); result[key] = code
            if bt(i + 1):
                return True
            used.remove(code); del result[key]
        return False

    bt(0)
    return result


# ────────────────────────────────────────────────────────────────────
# A single tournament
# ────────────────────────────────────────────────────────────────────
def sample_score(xg, rng, h, a):
    return rng.poisson(xg[(h, a)]), rng.poisson(xg[(a, h)])


def simulate_once(groups, group_matches, ko, third_slots, xg, rng, tally,
                  r32_pairs):
    placements = {}  # '1A', '2B' -> code
    thirds = []      # (code, group_letter, pts, gd, gf)

    for g, teams in groups.items():
        pts = {c: 0 for c in teams}
        gd = {c: 0 for c in teams}
        gf = {c: 0 for c in teams}
        for h, a in group_matches[g]:
            gh, ga = sample_score(xg, rng, h, a)
            gf[h] += gh; gf[a] += ga
            gd[h] += gh - ga; gd[a] += ga - gh
            if gh > ga:
                pts[h] += 3
            elif ga > gh:
                pts[a] += 3
            else:
                pts[h] += 1; pts[a] += 1
        ranked = sorted(teams, key=lambda c: (pts[c], gd[c], gf[c], rng.random()),
                        reverse=True)
        letter = g.replace("Group ", "")
        placements[f"1{letter}"] = ranked[0]
        placements[f"2{letter}"] = ranked[1]
        tally["group_winner"][ranked[0]] += 1
        thirds.append((ranked[2], letter, pts[ranked[2]], gd[ranked[2]], gf[ranked[2]]))

    # best 8 third-place teams
    thirds.sort(key=lambda t: (t[2], t[3], t[4], rng.random()), reverse=True)
    top8 = [(c, grp) for c, grp, *_ in thirds[:8]]
    slot_team = assign_thirds(top8, third_slots)

    def resolve(ref, winners):
        if ref in placements:
            return placements[ref]
        if ref.startswith("W"):
            return winners[int(ref[1:])]
        if ref.startswith("L"):
            return winners[("L", int(ref[1:]))]
        return None  # a third-place slot, handled below

    winners = {}
    for m in ko:
        num, rnd = m["num"], m["round"]
        t1 = resolve(m["ref1"], winners)
        t2 = resolve(m["ref2"], winners)
        if t1 is None:
            t1 = slot_team.get(f"{num}:1")
        if t2 is None:
            t2 = slot_team.get(f"{num}:2")
        if t1 is None or t2 is None:
            continue
        if num in ROUND_OF:
            tally[ROUND_OF[num]][t1] += 1
            tally[ROUND_OF[num]][t2] += 1
        if num in (73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88):
            r32_pairs[num][(t1, t2)] += 1
        gh, ga = sample_score(xg, rng, t1, t2)
        if gh > ga:
            w, loser = t1, t2
        elif ga > gh:
            w, loser = t2, t1
        else:  # shootout, weighted by relative strength
            p1 = xg[(t1, t2)] / (xg[(t1, t2)] + xg[(t2, t1)])
            w, loser = (t1, t2) if rng.random() < p1 else (t2, t1)
        winners[num] = w
        winners[("L", num)] = loser

    champ = winners.get(103)
    if champ:
        tally["champion"][champ] += 1


# ────────────────────────────────────────────────────────────────────
def main():
    print("Training v2 model…")
    hist = load_historical_from_db()
    hist, latest_elo = add_elo_columns(hist)
    rolling = compute_team_rolling_strengths(hist)
    feats = build_match_features(hist, rolling)
    model = PoissonGoalModel().fit(feats, sample_weight=feats["weight"].to_numpy())

    conn = get_connection()
    with conn.cursor() as cur:
        with open(MIGRATION) as f:
            cur.execute(f.read())
        conn.commit()
        cur.execute("SELECT id FROM model_runs ORDER BY run_at DESC LIMIT 1")
        row = cur.fetchone()
        model_run_id = row[0] if row else None

    # Groups, group fixtures, and display names from the DB
    df = pd.read_sql(
        """
        SELECT f.group_name,
               ht.fifa_code AS home_code, ht.name AS home_name,
               at.fifa_code AS away_code, at.name AS away_name
        FROM fixtures f
        LEFT JOIN teams ht ON ht.id = f.home_team_id
        LEFT JOIN teams at ON at.id = f.away_team_id
        WHERE f.stage = 'group'
        ORDER BY f.group_name
        """,
        conn,
    )
    groups = defaultdict(set)
    group_matches = defaultdict(list)
    names = {PLAYOFF: "Playoff Winner"}
    for _, r in df.iterrows():
        g = r["group_name"]
        h = r["home_code"] if pd.notna(r["home_code"]) else PLAYOFF
        a = r["away_code"] if pd.notna(r["away_code"]) else PLAYOFF
        if pd.notna(r["home_name"]):
            names[r["home_code"]] = r["home_name"]
        if pd.notna(r["away_name"]):
            names[r["away_code"]] = r["away_name"]
        groups[g].update([h, a])
        group_matches[g].append((h, a))

    teams = sorted({c for s in groups.values() for c in s})

    # Feature components per team (attack, defense, elo); playoff slot gets a
    # modest default profile.
    comp = {}
    for c in teams:
        if c == PLAYOFF:
            comp[c] = (1.0, 1.4, DEFAULT_ELO - 50)
            continue
        s = latest_strength(rolling, c)
        comp[c] = (s[0], s[1], latest_elo.get(c, DEFAULT_ELO)) if s else (1.1, 1.3, latest_elo.get(c, DEFAULT_ELO))

    print(f"{len(teams)} teams. Building expected-goals matrix…")
    xg = build_xg_matrix(model, comp, teams)
    ko, third_slots = parse_bracket()

    print(f"Simulating {N_SIMS:,} tournaments…")
    rng = np.random.default_rng()
    tally = {k: defaultdict(int) for k in
             ("group_winner", "r32", "r16", "qf", "sf", "final", "champion")}
    r32_pairs = defaultdict(Counter)
    for _ in range(N_SIMS):
        simulate_once(groups, group_matches, ko, third_slots, xg, rng, tally, r32_pairs)

    # Per-team probabilities
    team_odds = []
    for c in teams:
        team_odds.append({
            "code": c, "name": names.get(c, c),
            "champion": tally["champion"][c] / N_SIMS,
            "final": tally["final"][c] / N_SIMS,
            "semifinal": tally["sf"][c] / N_SIMS,
            "quarterfinal": tally["qf"][c] / N_SIMS,
            "r16": tally["r32"][c] / N_SIMS,  # reached the knockouts
            "group_winner": tally["group_winner"][c] / N_SIMS,
        })
    team_odds.sort(key=lambda t: t["champion"], reverse=True)

    bracket = build_predicted_bracket(ko, r32_pairs, xg, names)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tournament_sim (n_sims, model_run_id, team_odds, predicted_bracket) "
            "VALUES (%s, %s, %s, %s)",
            (N_SIMS, model_run_id, json.dumps(team_odds), json.dumps(bracket)),
        )
    conn.commit()
    conn.close()

    print("\nTop title contenders:")
    for t in team_odds[:8]:
        print(f"  {t['name']:18} champion {t['champion']*100:5.1f}%  "
              f"final {t['final']*100:5.1f}%")


def build_predicted_bracket(ko, r32_pairs, xg, names):
    """Single most-likely path: take the modal R32 matchup for each slot, then
    advance the favorite (higher expected goals) through to the final."""
    def fav(a, b):
        return a if xg[(a, b)] >= xg[(b, a)] else b

    def card(num, a, b):
        w = fav(a, b)
        total = xg[(a, b)] + xg[(b, a)]
        return {
            "num": num,
            "home": names.get(a, a), "away": names.get(b, b),
            "winner": names.get(w, w),
            "home_pct": round(xg[(a, b)] / total * 100),
            "away_pct": round(xg[(b, a)] / total * 100),
        }, w

    winners, rounds = {}, defaultdict(list)
    for m in ko:
        num, rnd = m["num"], m["round"]
        if num in r32_pairs and r32_pairs[num]:
            a, b = r32_pairs[num].most_common(1)[0][0]
        else:
            a = winners.get(_wnum(m["ref1"]))
            b = winners.get(_wnum(m["ref2"]))
        if a is None or b is None:
            continue
        c, w = card(num, a, b)
        winners[num] = w
        rounds[rnd].append(c)

    # stage_for() returns "f" for the Final
    order = ["r32", "r16", "qf", "sf", "f"]
    labels = {"r32": "Round of 32", "r16": "Round of 16", "qf": "Quarter-finals",
              "sf": "Semi-finals", "f": "Final"}
    champion = None
    if rounds["f"]:
        champion = rounds["f"][0]["winner"]
    return {
        "champion": champion,
        "rounds": [{"key": k, "label": labels[k], "matches": rounds[k]}
                   for k in order if rounds[k]],
    }


def _wnum(ref):
    return int(ref[1:]) if isinstance(ref, str) and ref.startswith("W") else None


if __name__ == "__main__":
    main()
