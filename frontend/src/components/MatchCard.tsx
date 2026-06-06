import type { MatchPrediction } from "@/lib/queries";
import { Flag } from "./Flag";

const COLOMBIA = "COL";

function pct(v: string | null): number {
  return v ? Math.round(parseFloat(v) * 100) : 0;
}

function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

/** Probability bar: home (tomato) / draw (sun) / away (slate). */
function ProbBar({ h, d, a }: { h: number; d: number; a: number }) {
  return (
    <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-mute-100">
      <div className="bg-tomato" style={{ width: `${h}%` }} />
      <div className="bg-sun" style={{ width: `${d}%` }} />
      <div className="bg-ink" style={{ width: `${a}%` }} />
    </div>
  );
}

export function MatchCard({ m }: { m: MatchPrediction }) {
  const h = pct(m.p_home_win);
  const d = pct(m.p_draw);
  const a = pct(m.p_away_win);
  const involvesColombia = m.home_code === COLOMBIA || m.away_code === COLOMBIA;
  const played = m.home_goals != null && m.away_goals != null;

  return (
    <article
      className={`rounded-xl border bg-paper p-4 shadow-sm transition hover:shadow-md ${
        involvesColombia ? "border-sun ring-1 ring-sun/40" : "border-mute/30"
      }`}
    >
      <div className="mb-3 flex items-center justify-between text-xs text-mute">
        <span className="font-semibold uppercase tracking-wide">
          {m.stage === "group" ? `Group ${m.group_name ?? ""}` : m.stage.toUpperCase()}
        </span>
        <span>{formatKickoff(m.kickoff_utc)}</span>
      </div>

      <div className="mb-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        {/* Home */}
        <div className="flex items-center gap-2">
          <Flag team={m.home_team} />
          <span
            className={`truncate text-sm font-bold ${
              m.home_code === COLOMBIA ? "text-tomato" : "text-ink"
            }`}
          >
            {m.home_team}
          </span>
        </div>

        {/* Center: score or xG */}
        <div className="px-2 text-center text-xs font-medium text-mute">
          {played ? (
            <span className="text-base font-extrabold text-ink">
              {m.home_goals}–{m.away_goals}
            </span>
          ) : (
            <>xG {m.xg_home}–{m.xg_away}</>
          )}
        </div>

        {/* Away */}
        <div className="flex items-center justify-end gap-2">
          <span
            className={`truncate text-right text-sm font-bold ${
              m.away_code === COLOMBIA ? "text-tomato" : "text-ink"
            }`}
          >
            {m.away_team}
          </span>
          <Flag team={m.away_team} />
        </div>
      </div>

      <ProbBar h={h} d={d} a={a} />

      <div className="mt-2 flex justify-between text-sm font-bold">
        <span className="text-tomato">{h}%</span>
        <span className="text-sun">{d}% draw</span>
        <span className="text-ink">{a}%</span>
      </div>

      <div className="mt-2 flex items-center justify-between text-[11px] text-mute">
        {m.locked_at && <span>🔒 Locked {new Date(m.locked_at).toLocaleDateString()}</span>}
        {played && m.brier_score && <span>Brier {parseFloat(m.brier_score).toFixed(3)}</span>}
      </div>
    </article>
  );
}
