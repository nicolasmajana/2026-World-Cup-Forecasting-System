import { notFound } from "next/navigation";
import { getMatchDetail, getOddsHistory } from "@/lib/queries";
import { Flag } from "@/components/Flag";
import { OddsChart } from "@/components/OddsChart";

export const dynamic = "force-dynamic";

function pct(v: string | null) {
  return v ? Math.round(parseFloat(v) * 100) : null;
}

export default async function MatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const fixtureId = Number(id);
  if (!Number.isFinite(fixtureId)) notFound();

  const [m, history] = await Promise.all([
    getMatchDetail(fixtureId),
    getOddsHistory(fixtureId),
  ]);
  if (!m) notFound();

  const h = pct(m.p_home_win);
  const d = pct(m.p_draw);
  const a = pct(m.p_away_win);
  const played = m.home_goals != null && m.away_goals != null;
  const home = m.home_team ?? "TBD";
  const away = m.away_team ?? "TBD";

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <p className="text-sm font-semibold uppercase tracking-wide text-mute">
        {m.stage === "group" ? `Group ${m.group_name ?? ""}` : m.stage.toUpperCase()}
        {" · "}
        {new Date(m.kickoff_utc).toLocaleString("en-US", {
          dateStyle: "medium",
          timeStyle: "short",
        })}
      </p>

      {/* Scoreline / teams */}
      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-4 rounded-2xl border border-mute/30 bg-paper p-6 shadow-sm">
        <div className="flex flex-col items-center gap-2 text-center">
          <Flag team={home} size={56} />
          <span className="text-lg font-extrabold text-ink">{home}</span>
        </div>
        <div className="text-center">
          {played ? (
            <span className="text-3xl font-extrabold text-ink">
              {m.home_goals}–{m.away_goals}
            </span>
          ) : (
            <span className="text-sm font-semibold text-mute">
              xG {m.xg_home ?? "—"}–{m.xg_away ?? "—"}
            </span>
          )}
        </div>
        <div className="flex flex-col items-center gap-2 text-center">
          <Flag team={away} size={56} />
          <span className="text-lg font-extrabold text-ink">{away}</span>
        </div>
      </div>

      {/* Probabilities */}
      {h != null ? (
        <div className="mt-6 grid grid-cols-3 gap-3 text-center">
          <Prob label={`${home} win`} value={h} color="text-tomato" />
          <Prob label="Draw" value={d!} color="text-sun" />
          <Prob label={`${away} win`} value={a!} color="text-ink" />
        </div>
      ) : (
        <p className="mt-6 text-mute">No locked prediction for this match yet.</p>
      )}

      {/* Odds drift chart */}
      <section className="mt-8 rounded-2xl border border-mute/30 bg-paper p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-bold text-ink">How the odds moved</h2>
        <OddsChart history={history} homeTeam={home} awayTeam={away} />
      </section>

      {/* Qualitative context (injuries, suspensions) — populated later */}
      {(() => {
        const notes = history
          .filter((s) => s.note)
          .map((s) => ({ when: s.captured_at, note: s.note as string }));
        if (notes.length === 0) return null;
        return (
          <section className="mt-6 rounded-2xl border border-sun/40 bg-sun-50 p-6">
            <h2 className="mb-3 text-lg font-bold text-ink">Context notes</h2>
            <ul className="space-y-2 text-sm text-ink/90">
              {notes.map((n, i) => (
                <li key={i}>
                  <span className="font-semibold">
                    {new Date(n.when).toLocaleDateString()}:
                  </span>{" "}
                  {n.note}
                </li>
              ))}
            </ul>
          </section>
        );
      })()}
    </main>
  );
}

function Prob({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-xl border border-mute/30 bg-paper p-4 shadow-sm">
      <p className={`text-3xl font-extrabold ${color}`}>{value}%</p>
      <p className="mt-1 text-xs font-semibold text-mute">{label}</p>
    </div>
  );
}
