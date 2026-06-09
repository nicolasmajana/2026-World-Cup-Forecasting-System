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
for (const w of WIRES)
  for (const r of [w.ref1, w.ref2])
    if (r.startsWith("W")) parent[Number(r.slice(1))] = w.num;

function half(num: number): "L" | "R" | "C" {
  if (num === 101) return "L";
  if (num === 102) return "R";
  if (num >= 103) return "C";
  const p = parent[num];
  return p ? half(p) : "C";
}

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

/** Resolver: given a slot ref, return the actual team name if known. */
export type SlotResolver = (ref: string) => string | null;

/** Build the bracket rounds. If `resolve` is given, slot refs that resolve to
 * a real team show the team; otherwise the slot label is shown. */
export function bracketRounds(resolve?: SlotResolver) {
  const order = ["r32", "r16", "qf", "sf", "f"];
  const byRound: Record<string, BracketMatch[]> = {};
  for (const w of WIRES) {
    const home = (resolve && resolve(w.ref1)) || label(w.ref1);
    const away = (resolve && resolve(w.ref2)) || label(w.ref2);
    (byRound[w.round] ??= []).push({
      num: w.num,
      half: half(w.num),
      home,
      away,
    });
  }
  return order
    .filter((k) => byRound[k]?.length)
    .map((k) => ({ key: k, label: LABELS[k], matches: byRound[k] }));
}
