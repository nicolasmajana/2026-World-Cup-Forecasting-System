import type { ChampionHistory } from "@/lib/queries";
import { Flag } from "./Flag";
import { formatDate } from "@/lib/datetime";

const W = 640;
const H = 280;
const PAD = { top: 16, right: 16, bottom: 30, left: 40 };
const MAX_LINES = 8;

// Brand-adjacent palette: tomato, sun, ink, mute, then earthy variants that
// stay readable against each other.
const COLORS = [
  "#ff4b01", "#faa000", "#3e4749", "#879499",
  "#a83200", "#8a7100", "#2e6e72", "#8c5a2b",
];

/** Champion odds over time as a line chart, one line per top contender.
 * Same visual language as the per-match odds chart; updates daily. */
export function ChampionChart({ data }: { data: ChampionHistory }) {
  const n = data.columns.length;
  if (n === 0 || data.teams.length === 0) return null;

  // Top contenders by the latest day's odds.
  const teams = [...data.teams]
    .sort((a, b) => (b.values[n - 1] ?? 0) - (a.values[n - 1] ?? 0))
    .slice(0, MAX_LINES);

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const maxVal = Math.max(
    0.05,
    ...teams.flatMap((t) => t.values.map((v) => v ?? 0)),
  );
  // headroom, rounded up to the next 5%
  const yMax = Math.ceil((maxVal * 1.15) * 20) / 20;

  const x = (i: number) => (n === 1 ? PAD.left : PAD.left + (i / (n - 1)) * plotW);
  const y = (p: number) => PAD.top + (1 - p / yMax) * plotH;

  // gridlines every 5% (or 10% if the scale is tall)
  const step = yMax > 0.3 ? 0.1 : 0.05;
  const grid: number[] = [];
  for (let g = 0; g <= yMax + 1e-9; g += step) grid.push(g);

  // x labels: first, last, and the middle column when there is room
  const labelIdx = n <= 2 ? [...Array(n).keys()] : [0, Math.floor((n - 1) / 2), n - 1];

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {grid.map((g) => (
          <g key={g}>
            <line
              x1={PAD.left} x2={W - PAD.right} y1={y(g)} y2={y(g)}
              stroke="var(--color-mute)" strokeOpacity={0.2}
            />
            <text x={4} y={y(g) + 4} fontSize={10} fill="var(--color-mute)">
              {Math.round(g * 100)}%
            </text>
          </g>
        ))}

        {labelIdx.map((i) => (
          <text
            key={i} x={x(i)} y={H - 8} fontSize={10}
            fill="var(--color-mute)"
            textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}
          >
            {formatDate(data.columns[i])}
          </text>
        ))}

        {teams.map((t, ti) => {
          const pts = t.values
            .map((v, i) => (v == null ? null : `${x(i)},${y(v)}`))
            .filter(Boolean) as string[];
          return (
            <g key={t.code}>
              {pts.length > 1 && (
                <polyline
                  points={pts.join(" ")} fill="none"
                  stroke={COLORS[ti]} strokeWidth={2.5}
                />
              )}
              {t.values.map((v, i) =>
                v == null ? null : (
                  <circle key={i} cx={x(i)} cy={y(v)} r={3} fill={COLORS[ti]} />
                ),
              )}
            </g>
          );
        })}
      </svg>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs font-semibold sm:grid-cols-4">
        {teams.map((t, ti) => (
          <span key={t.code} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: COLORS[ti] }}
            />
            <Flag team={t.name} size={16} />
            <span className="truncate">{t.name}</span>
            <span className="ml-auto tabular-nums text-mute">
              {((t.values[n - 1] ?? 0) * 100).toFixed(1)}%
            </span>
          </span>
        ))}
      </div>
      {n === 1 && (
        <p className="mt-2 text-xs text-mute">
          One simulation day so far; the lines build out as the tournament
          plays and the model re-simulates each morning.
        </p>
      )}
    </div>
  );
}
