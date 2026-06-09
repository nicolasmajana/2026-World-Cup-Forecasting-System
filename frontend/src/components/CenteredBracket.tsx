import { Flag } from "./Flag";
import { flagUrl } from "@/lib/flags";

const BOX_W = 150;
const STUB = 14;
const COL_W = BOX_W + STUB * 2;
const LINE = "var(--color-mute)";

// Generic bracket match: home/away may be team names OR slot labels
// ("Winner A"). pct is hidden when null; the flag shows only for real teams.
export type BracketMatch = {
  num: number;
  half: "L" | "R" | "C";
  home: string;
  away: string;
  winner?: string | null;
  home_pct?: number | null;
  away_pct?: number | null;
};

type Round = { key: string; label: string; matches: BracketMatch[] };

function half(matches: BracketMatch[], side: "L" | "R") {
  return matches.filter((m) => m.half === side).sort((a, b) => a.num - b.num);
}

function Row({ name, pct, win }: { name: string; pct?: number | null; win: boolean }) {
  const hasFlag = flagUrl(name) != null;
  return (
    <div className={`flex items-center justify-between gap-1.5 px-1.5 py-1 ${win ? "bg-tomato-50" : ""}`}>
      <span className="flex min-w-0 items-center gap-1.5">
        {hasFlag && <Flag team={name} size={16} />}
        <span
          className={`truncate text-[11px] ${
            win ? "font-bold text-ink" : hasFlag ? "text-mute" : "italic text-mute/80"
          }`}
        >
          {name}
        </span>
      </span>
      {pct != null && (
        <span className="shrink-0 text-[10px] font-bold text-tomato">{pct}%</span>
      )}
    </div>
  );
}

function MatchBox({ m }: { m: BracketMatch }) {
  const homeWin = !!m.winner && m.winner === m.home;
  const awayWin = !!m.winner && m.winner === m.away;
  return (
    <div
      className="overflow-hidden rounded-md border border-mute/30 bg-paper shadow-sm"
      style={{ width: BOX_W }}
    >
      <Row name={m.home} pct={m.home_pct} win={homeWin} />
      <div className="border-t border-mute/15" />
      <Row name={m.away} pct={m.away_pct} win={awayWin} />
    </div>
  );
}

/** Connector lines for one match toward the next (more central) round.
 * `single` = the column has one match (semifinal -> final): just a straight line. */
function Connector({ side, even, single }: { side: "L" | "R"; even: boolean; single: boolean }) {
  const x = side === "L" ? BOX_W + STUB : undefined;
  const xr = side === "R" ? BOX_W + STUB : undefined;

  if (single) {
    // one straight horizontal line across the whole connector gap
    return (
      <span
        className="absolute h-px"
        style={{
          top: "50%",
          width: STUB * 2,
          left: side === "L" ? BOX_W : undefined,
          right: side === "R" ? BOX_W : undefined,
          background: LINE,
        }}
      />
    );
  }

  const stubStyle: React.CSSProperties =
    side === "L"
      ? { left: BOX_W, top: "50%", width: STUB }
      : { right: BOX_W, top: "50%", width: STUB };

  return (
    <>
      <span className="absolute h-px" style={{ ...stubStyle, background: LINE }} />
      {even && (
        <>
          {/* vertical line joining this match's centre to its pair's centre */}
          <span
            className="absolute w-px"
            style={{ top: "50%", height: "100%", left: x, right: xr, background: LINE }}
          />
          {/* stub from the pair mid-point into the next round */}
          <span
            className="absolute h-px"
            style={{ top: "100%", width: STUB, left: x, right: xr, background: LINE }}
          />
        </>
      )}
    </>
  );
}

function Column({
  matches,
  side,
  withConnector,
}: {
  matches: BracketMatch[];
  side: "L" | "R" | "C";
  withConnector: boolean;
}) {
  return (
    <div className="flex flex-col" style={{ width: COL_W }}>
      {matches.map((m, i) => (
        <div
          key={m.num}
          className={`relative flex flex-1 items-center ${side === "R" ? "justify-end" : "justify-start"}`}
        >
          <MatchBox m={m} />
          {withConnector && side !== "C" && (
            <Connector side={side} even={i % 2 === 0} single={matches.length === 1} />
          )}
        </div>
      ))}
    </div>
  );
}

export function CenteredBracket({ rounds }: { rounds: Round[] }) {
  const byKey: Record<string, BracketMatch[]> = {};
  for (const r of rounds) byKey[r.key] = r.matches;
  const order = ["r32", "r16", "qf", "sf"];
  const left = order.map((k) => half(byKey[k] ?? [], "L"));
  // right side mirrors: semifinal closest to the final, round of 32 outermost
  const right = [...order].reverse().map((k) => half(byKey[k] ?? [], "R"));
  const finalMatch = (byKey["f"] ?? [])[0];

  // container height scales with the widest round (R32 half = 8 matches)
  const maxRows = Math.max(...left.map((c) => c.length), 1);
  const height = Math.max(maxRows * 64, 360);

  return (
    <div className="overflow-x-auto pb-4">
      <div className="flex items-stretch" style={{ minHeight: height }}>
        {left.map((matches, idx) => (
          <Column key={`L${idx}`} matches={matches} side="L" withConnector />
        ))}
        {/* centre: the final */}
        <div className="flex flex-col justify-center px-2" style={{ width: COL_W }}>
          {finalMatch && (
            <div className="flex flex-col items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wide text-mute">
                Final
              </span>
              <MatchBox m={finalMatch} />
            </div>
          )}
        </div>
        {right.map((matches, idx) => (
          <Column key={`R${idx}`} matches={matches} side="R" withConnector />
        ))}
      </div>
    </div>
  );
}
