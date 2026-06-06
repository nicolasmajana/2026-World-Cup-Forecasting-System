import type { OddsSnapshot } from "@/lib/queries";

const W = 640;
const H = 240;
const PAD = { top: 16, right: 16, bottom: 28, left: 36 };

type Series = { key: "p_home_win" | "p_draw" | "p_away_win"; color: string; label: string };

const SERIES: Series[] = [
  { key: "p_home_win", color: "var(--color-tomato)", label: "Home win" },
  { key: "p_draw", color: "var(--color-sun)", label: "Draw" },
  { key: "p_away_win", color: "var(--color-ink)", label: "Away win" },
];

export function OddsChart({
  history,
  homeTeam,
  awayTeam,
}: {
  history: OddsSnapshot[];
  homeTeam: string;
  awayTeam: string;
}) {
  if (history.length === 0) {
    return (
      <p className="text-sm text-mute">No odds history recorded yet.</p>
    );
  }

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const n = history.length;

  // x position for snapshot i (single point sits at left edge)
  const x = (i: number) => (n === 1 ? PAD.left : PAD.left + (i / (n - 1)) * plotW);
  const y = (p: number) => PAD.top + (1 - p) * plotH; // 0..1 -> bottom..top

  const labels = SERIES.map((s) => ({
    ...s,
    home: homeTeam,
    away: awayTeam,
  }));

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* gridlines at 0/25/50/75/100% */}
        {[0, 0.25, 0.5, 0.75, 1].map((g) => (
          <g key={g}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(g)}
              y2={y(g)}
              stroke="var(--color-mute)"
              strokeOpacity={0.2}
            />
            <text x={4} y={y(g) + 4} fontSize={10} fill="var(--color-mute)">
              {g * 100}%
            </text>
          </g>
        ))}

        {SERIES.map((s) => {
          const pts = history.map(
            (h, i) => `${x(i)},${y(parseFloat(h[s.key]))}`,
          );
          return (
            <g key={s.key}>
              {n > 1 && (
                <polyline
                  points={pts.join(" ")}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2.5}
                />
              )}
              {history.map((h, i) => (
                <circle
                  key={i}
                  cx={x(i)}
                  cy={y(parseFloat(h[s.key]))}
                  r={n === 1 ? 4 : 3}
                  fill={s.color}
                />
              ))}
            </g>
          );
        })}
      </svg>

      <div className="mt-2 flex flex-wrap gap-4 text-xs font-semibold">
        {labels.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: s.color }}
            />
            {s.key === "p_home_win"
              ? `${homeTeam} win`
              : s.key === "p_away_win"
                ? `${awayTeam} win`
                : "Draw"}
          </span>
        ))}
      </div>
      {n === 1 && (
        <p className="mt-2 text-xs text-mute">
          Only one snapshot so far — the line builds out as the model
          re-evaluates this match each day.
        </p>
      )}
    </div>
  );
}
