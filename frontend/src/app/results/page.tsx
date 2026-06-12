import {
  getResultsLog,
  getCalibrationSummary,
  getPendingResults,
  type PendingMatch,
} from "@/lib/queries";
import { Flag } from "@/components/Flag";
import { predictedScore } from "@/lib/flags";
import { formatKickoff } from "@/lib/datetime";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Results Log - WC 2026 Forecasts",
  description:
    "Every played match: the prediction locked before kickoff next to what actually happened.",
};

function pct(v: string | null) {
  return v ? `${Math.round(parseFloat(v) * 100)}%` : "-";
}

function outcome(hg: number, ag: number): "H" | "D" | "A" {
  return hg > ag ? "H" : hg < ag ? "A" : "D";
}

/** Which outcome did the locked prediction favor? */
function pick(h: string | null, d: string | null, a: string | null): "H" | "D" | "A" | null {
  if (h == null || d == null || a == null) return null;
  const ph = parseFloat(h), pd = parseFloat(d), pa = parseFloat(a);
  if (ph >= pd && ph >= pa) return "H";
  if (pa >= pd) return "A";
  return "D";
}

export default async function ResultsPage() {
  const [rows, summary, pending] = await Promise.all([
    getResultsLog(),
    getCalibrationSummary(),
    getPendingResults(),
  ]);

  const withPick = rows.filter((r) => r.p_home_win != null);
  const outcomeHits = withPick.filter(
    (r) => pick(r.p_home_win, r.p_draw, r.p_away_win) === outcome(r.home_goals, r.away_goals),
  ).length;
  const exactHits = withPick.filter(
    (r) => predictedScore(r.xg_home, r.xg_away) === `${r.home_goals}-${r.away_goals}`,
  ).length;

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-3xl font-extrabold text-ink">Results Log</h1>
      <p className="mt-2 max-w-2xl text-mute">
        Every played match: the prediction that was locked before kickoff, next
        to what actually happened. Nothing here can be edited after the fact.
      </p>

      {pending.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-1 flex items-center gap-2 text-lg font-bold text-ink">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-sun" />
            Awaiting result
          </h2>
          <p className="mb-3 text-sm text-mute">
            These matches have kicked off. Scores come from a free,
            community-maintained feed that updates with a delay, so the result
            and Brier score will appear automatically once it publishes.
          </p>
          <div className="grid gap-2">
            {pending.map((m) => (
              <PendingRow key={m.fixture_id} m={m} />
            ))}
          </div>
        </section>
      )}

      {rows.length === 0 && pending.length === 0 ? (
        <p className="mt-8 text-mute">
          No matches played yet. The log starts filling in with the opening
          match.
        </p>
      ) : rows.length === 0 ? null : (
        <>
          <section className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Stat
              label="Outcome picks right"
              value={withPick.length ? `${Math.round((outcomeHits / withPick.length) * 100)}%` : "-"}
              hint={`${outcomeHits} of ${withPick.length}`}
            />
            <Stat
              label="Exact scores right"
              value={withPick.length ? `${Math.round((exactHits / withPick.length) * 100)}%` : "-"}
              hint={`${exactHits} of ${withPick.length}`}
            />
            <Stat
              label="Brier score"
              value={summary.mean_brier != null ? summary.mean_brier.toFixed(4) : "-"}
              hint="lower is better"
            />
          </section>

          <section className="mt-8 overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-mute/30 text-left text-xs uppercase tracking-wide text-mute">
                  <th className="py-2">Match</th>
                  <th className="py-2 text-center">Locked W/D/L</th>
                  <th className="py-2 text-center">Pred. score</th>
                  <th className="py-2 text-center">Actual</th>
                  <th className="py-2 text-center">Pick</th>
                  <th className="py-2 text-right">Brier</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const p = pick(r.p_home_win, r.p_draw, r.p_away_win);
                  const o = outcome(r.home_goals, r.away_goals);
                  const hit = p != null && p === o;
                  const ps = predictedScore(r.xg_home, r.xg_away);
                  const exact = ps === `${r.home_goals}-${r.away_goals}`;
                  return (
                    <tr key={r.fixture_id} className="border-b border-mute/15">
                      <td className="py-2">
                        <div className="flex items-center gap-2 font-semibold text-ink">
                          <Flag team={r.home_team} size={18} />
                          <span>{r.home_team}</span>
                          <span className="text-mute">vs</span>
                          <span>{r.away_team}</span>
                          <Flag team={r.away_team} size={18} />
                        </div>
                        <div className="text-[11px] text-mute">
                          {r.stage === "group" ? r.group_name : r.stage.toUpperCase()}
                          {" · "}
                          {formatKickoff(r.kickoff_utc)}
                        </div>
                      </td>
                      <td className="py-2 text-center tabular-nums">
                        {pct(r.p_home_win)} / {pct(r.p_draw)} / {pct(r.p_away_win)}
                      </td>
                      <td className={`py-2 text-center tabular-nums ${exact ? "font-bold text-tomato" : ""}`}>
                        {ps ?? "-"}
                      </td>
                      <td className="py-2 text-center text-base font-extrabold tabular-nums text-ink">
                        {r.home_goals}-{r.away_goals}
                      </td>
                      <td className="py-2 text-center">
                        {p == null ? (
                          <span className="text-mute">-</span>
                        ) : hit ? (
                          <span className="font-bold text-tomato">hit</span>
                        ) : (
                          <span className="text-mute">miss</span>
                        )}
                      </td>
                      <td className="py-2 text-right tabular-nums">
                        {r.brier_score ? parseFloat(r.brier_score).toFixed(3) : "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        </>
      )}
    </main>
  );
}

function PendingRow({ m }: { m: PendingMatch }) {
  const mins = Math.round(m.minutes_since_kickoff);
  // A match runs ~2 hours; before that it is likely still being played.
  const inProgress = mins < 120;
  const status = inProgress ? "In progress" : "Processing result";
  const waited =
    mins < 120 ? null : mins < 1440 ? `${Math.round(mins / 60)}h` : `${Math.round(mins / 1440)}d`;
  const ps = predictedScore(m.xg_home, m.xg_away);

  return (
    <article className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sun/50 bg-sun-50/60 p-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2 font-semibold text-ink">
          <Flag team={m.home_team} size={18} />
          <span className="truncate">{m.home_team}</span>
          <span className="text-mute">vs</span>
          <span className="truncate">{m.away_team}</span>
          <Flag team={m.away_team} size={18} />
        </div>
        <div className="text-[11px] text-mute">
          {m.stage === "group" ? m.group_name : m.stage.toUpperCase()}
          {" · "}
          {formatKickoff(m.kickoff_utc)}
        </div>
      </div>
      <div className="flex items-center gap-4 text-sm">
        {ps && (
          <span className="text-mute">
            predicted <span className="font-bold text-ink">{ps}</span>
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sun/20 px-2.5 py-1 text-xs font-semibold text-ink">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-sun" />
          {status}
          {waited && <span className="text-mute">· {waited} ago</span>}
        </span>
      </div>
    </article>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-mute/30 bg-paper p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-mute">{label}</p>
      <p className="mt-1 text-3xl font-extrabold tabular-nums text-tomato">{value}</p>
      <p className="text-xs text-mute">{hint}</p>
    </div>
  );
}
