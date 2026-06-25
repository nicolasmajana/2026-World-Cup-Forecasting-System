import type { BracketMatch } from "@/components/CenteredBracket";

// The fixed 2026 knockout wiring (from openfootball). Each match references the
// group finishes (1A = winner Group A, 2B = runner-up, 3A/B/C/D/F = a
// third-place team from one of those groups) or a previous match (W74 = winner
// of match 74). This is the real bracket structure; teams fill in as the
// tournament resolves.
const WIRES: { num: number; round: string; ref1: string; ref2: string }[] = [
  { num: 73, round: "r32", ref1: "2A", ref2: "2B" },
  { num: 74, round: "r32", ref1: "1E", ref2: "3A/B/C/D/F" },
  { num: 75, round: "r32", ref1: "1F", ref2: "2C" },
  { num: 76, round: "r32", ref1: "1C", ref2: "2F" },
  { num: 77, round: "r32", ref1: "1I", ref2: "3C/D/F/G/H" },
  { num: 78, round: "r32", ref1: "2E", ref2: "2I" },
  { num: 79, round: "r32", ref1: "1A", ref2: "3C/E/F/H/I" },
  { num: 80, round: "r32", ref1: "1L", ref2: "3E/H/I/J/K" },
  { num: 81, round: "r32", ref1: "1D", ref2: "3B/E/F/I/J" },
  { num: 82, round: "r32", ref1: "1G", ref2: "3A/E/H/I/J" },
  { num: 83, round: "r32", ref1: "2K", ref2: "2L" },
  { num: 84, round: "r32", ref1: "1H", ref2: "2J" },
  { num: 85, round: "r32", ref1: "1B", ref2: "3E/F/G/I/J" },
  { num: 86, round: "r32", ref1: "1J", ref2: "2H" },
  { num: 87, round: "r32", ref1: "1K", ref2: "3D/E/I/J/L" },
  { num: 88, round: "r32", ref1: "2D", ref2: "2G" },
  { num: 89, round: "r16", ref1: "W74", ref2: "W77" },
  { num: 90, round: "r16", ref1: "W73", ref2: "W75" },
  { num: 91, round: "r16", ref1: "W76", ref2: "W78" },
  { num: 92, round: "r16", ref1: "W79", ref2: "W80" },
  { num: 93, round: "r16", ref1: "W83", ref2: "W84" },
  { num: 94, round: "r16", ref1: "W81", ref2: "W82" },
  { num: 95, round: "r16", ref1: "W86", ref2: "W88" },
  { num: 96, round: "r16", ref1: "W85", ref2: "W87" },
  { num: 97, round: "qf", ref1: "W89", ref2: "W90" },
  { num: 98, round: "qf", ref1: "W93", ref2: "W94" },
  { num: 99, round: "qf", ref1: "W91", ref2: "W92" },
  { num: 100, round: "qf", ref1: "W95", ref2: "W96" },
  { num: 101, round: "sf", ref1: "W97", ref2: "W98" },
  { num: 102, round: "sf", ref1: "W99", ref2: "W100" },
  { num: 103, round: "f", ref1: "W101", ref2: "W102" },
];

const parent: Record<number, number> = {};
const children: Record<number, number[]> = {};
for (const w of WIRES)
  for (const r of [w.ref1, w.ref2])
    if (r.startsWith("W")) {
      const c = Number(r.slice(1));
      parent[c] = w.num;
      (children[w.num] ??= []).push(c);
    }

function half(num: number): "L" | "R" | "C" {
  if (num === 101) return "L";
  if (num === 102) return "R";
  if (num >= 103) return "C";
  const p = parent[num];
  return p ? half(p) : "C";
}

// Vertical layout order: in-order traversal of the bracket tree assigns each
// Round-of-32 match (a leaf) a slot top-to-bottom; every later match sits at
// the mid-point of its two feeders. Ordering rounds by this (NOT by match
// number) is what makes the tree line up: the wiring pairs non-adjacent
// numbers (R16 #89 = winners of #74 and #77).
const leafIndex: Record<number, number> = {};
let _li = 0;
function assignLeaves(num: number) {
  const ch = children[num];
  if (!ch) {
    leafIndex[num] = _li++;
    return;
  }
  ch.forEach(assignLeaves);
}
assignLeaves(103);

export const ORDER: Record<number, number> = {};
function pos(num: number): number {
  const ch = children[num];
  if (!ch) return leafIndex[num];
  return ch.reduce((s, c) => s + pos(c), 0) / ch.length;
}
for (const w of WIRES) ORDER[w.num] = pos(w.num);

function label(ref: string): string {
  if (/^1[A-L]$/.test(ref)) return `Winner ${ref[1]}`;
  if (/^2[A-L]$/.test(ref)) return `Runner-up ${ref[1]}`;
  if (ref.startsWith("3")) return `3rd: ${ref.slice(1)}`;
  if (ref.startsWith("W")) return `Winner of ${ref.slice(1)}`;
  if (ref.startsWith("L")) return `Loser of ${ref.slice(1)}`;
  return ref;
}

const LABELS: Record<string, string> = {
  r32: "Round of 32",
  r16: "Round of 16",
  qf: "Quarter-finals",
  sf: "Semi-finals",
  f: "Final",
};

/** A resolved knockout fixture: the real teams in each slot (null until the
 * bracket resolves) and the score once it has been played. */
export type SlotResult = {
  match_num: number;
  home_team: string | null;
  away_team: string | null;
  home_goals: number | null;
  away_goals: number | null;
};

/** Build the bracket rounds. Given the resolved knockout fixtures, each slot
 * label ("Winner A", "Winner of 74") is replaced by the real team as soon as
 * it is known, and the winner of a decided match is highlighted and pushed
 * forward into the next round even before the upstream feed relabels it. */
export function bracketRounds(slots?: SlotResult[]) {
  const byNum: Record<number, SlotResult> = {};
  for (const s of slots ?? []) byNum[s.match_num] = s;

  // ref -> real team name, built as results come in. Group/runner-up/third
  // refs come straight from the resolved fixture slots; W#/L# refs are derived
  // from decided match results so later rounds fill in immediately.
  const refTeam: Record<string, string> = {};
  for (const w of WIRES) {
    const s = byNum[w.num];
    if (s?.home_team) refTeam[w.ref1] = s.home_team;
    if (s?.away_team) refTeam[w.ref2] = s.away_team;
  }

  const winnerOf: Record<number, string | null> = {};
  for (const w of WIRES) {
    const s = byNum[w.num];
    if (!s || s.home_goals == null || s.away_goals == null) continue;
    if (s.home_goals === s.away_goals) continue; // shootout: winner not in score
    const won = s.home_goals > s.away_goals ? s.home_team : s.away_team;
    const lost = s.home_goals > s.away_goals ? s.away_team : s.home_team;
    winnerOf[w.num] = won;
    if (won) refTeam[`W${w.num}`] = won;
    if (lost) refTeam[`L${w.num}`] = lost;
  }

  const order = ["r32", "r16", "qf", "sf", "f"];
  const byRound: Record<string, BracketMatch[]> = {};
  for (const w of WIRES) {
    const home = refTeam[w.ref1] ?? label(w.ref1);
    const away = refTeam[w.ref2] ?? label(w.ref2);
    (byRound[w.round] ??= []).push({
      num: w.num,
      half: half(w.num),
      home,
      away,
      winner: winnerOf[w.num] ?? null,
    });
  }
  return order
    .filter((k) => byRound[k]?.length)
    .map((k) => ({ key: k, label: LABELS[k], matches: byRound[k] }));
}
