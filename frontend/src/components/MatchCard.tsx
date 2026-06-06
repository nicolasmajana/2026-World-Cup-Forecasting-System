import type { MatchPrediction } from "@/lib/queries";

const COLOMBIA = "COL";

function pct(v: string | null): number {
  return v ? Math.round(parseFloat(v) * 100) : 0;
}

function formatKickoff(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

/** A horizontal probability bar: home / draw / away. */
function ProbBar({ h, d, a }: { h: number; d: number; a: number }) {
  return (
    <div className="flex h-2.5 w-full overflow-hidden rounded-full">
      <div className="bg-emerald-500" style={{ width: `${h}%` }} />
      <div className="bg-slate-400" style={{ width: `${d}%` }} />
      <div className="bg-sky-500" style={{ width: `${a}%` }} />
    </div>
  );
}

export function MatchCard({ m }: { m: MatchPrediction }) {
  const h = pct(m.p_home_win);
  const d = pct(m.p_draw);
  const a = pct(m.p_away_win);
  const involvesColombia =
    m.home_code === COLOMBIA || m.away_code === COLOMBIA;

  return (
    <article
      className={`rounded-xl border p-4 shadow-sm transition hover:shadow-md ${
        involvesColombia
          ? "border-amber-400 bg-amber-50/60 dark:bg-amber-950/20"
          : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
      }`}
    >
      <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
        <span className="font-medium uppercase tracking-wide">
          {m.stage === "group" ? `Group ${m.group_name ?? ""}` : m.stage}
        </span>
        <span>{formatKickoff(m.kickoff_utc)}</span>
      </div>

      <div className="mb-3 flex items-center justify-between">
        <TeamLabel name={m.home_team} highlight={m.home_code === COLOMBIA} />
        <span className="px-2 text-xs text-slate-400">
          xG {m.xg_home} – {m.xg_away}
        </span>
        <TeamLabel
          name={m.away_team}
          highlight={m.away_code === COLOMBIA}
          alignRight
        />
      </div>

      <ProbBar h={h} d={d} a={a} />

      <div className="mt-2 flex justify-between text-sm font-semibold">
        <span className="text-emerald-600 dark:text-emerald-400">{h}%</span>
        <span className="text-slate-500">{d}% draw</span>
        <span className="text-sky-600 dark:text-sky-400">{a}%</span>
      </div>

      {m.locked_at && (
        <p className="mt-2 text-[11px] text-slate-400">
          🔒 Locked {new Date(m.locked_at).toLocaleDateString()}
        </p>
      )}
    </article>
  );
}

function TeamLabel({
  name,
  highlight,
  alignRight,
}: {
  name: string;
  highlight?: boolean;
  alignRight?: boolean;
}) {
  return (
    <span
      className={`flex-1 truncate text-sm font-semibold ${
        alignRight ? "text-right" : ""
      } ${highlight ? "text-amber-600 dark:text-amber-400" : ""}`}
    >
      {name}
    </span>
  );
}
