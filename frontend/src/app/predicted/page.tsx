import { getTournamentSim } from "@/lib/queries";
import { Flag } from "@/components/Flag";
import { GroupStandings } from "@/components/GroupStandings";
import { CenteredBracket } from "@/components/CenteredBracket";
import { formatDateTime } from "@/lib/datetime";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Predicted Tournament, WC 2026",
  description:
    "The whole World Cup simulated thousands of times: title odds and the single most likely path to the final.",
};

function pct(v: number) {
  return v >= 0.1 ? `${Math.round(v * 100)}%` : `${(v * 100).toFixed(1)}%`;
}

export default async function PredictedPage() {
  const sim = await getTournamentSim();

  if (!sim) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-extrabold text-ink">Predicted Tournament</h1>
        <p className="mt-3 text-mute">
          The simulation has not run yet. Check back shortly.
        </p>
      </main>
    );
  }

  const champion = sim.predicted_bracket.champion;
  const top = sim.team_odds.slice(0, 12);
  const maxChamp = Math.max(...top.map((t) => t.champion), 0.01);

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-3xl font-extrabold text-ink">Predicted Tournament</h1>
      <p className="mt-2 max-w-2xl text-mute">
        We simulated all 104 matches {sim.n_sims.toLocaleString()} times, playing
        out the groups, the third-place race, and every knockout round. Here are
        the title odds and the single most likely path to the final.
      </p>

      {champion && (
        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-sun bg-sun-50 p-5">
          <Flag team={champion} size={44} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-mute">
              Most likely champion
            </p>
            <p className="text-2xl font-extrabold text-ink">{champion}</p>
          </div>
        </div>
      )}

      {/* Title odds */}
      <section className="mt-8">
        <h2 className="mb-4 text-xl font-bold text-ink">Title odds</h2>
        <div className="space-y-1.5">
          {top.map((t) => (
            <div key={t.code} className="flex items-center gap-3">
              <span className="flex w-44 shrink-0 items-center gap-2">
                <Flag team={t.name} size={22} />
                <span className="truncate text-sm font-semibold text-ink">
                  {t.name}
                </span>
              </span>
              <div className="relative h-6 flex-1 overflow-hidden rounded-md bg-mute-100">
                <div
                  className="h-full rounded-md bg-tomato"
                  style={{ width: `${(t.champion / maxChamp) * 100}%` }}
                />
                <span className="absolute inset-y-0 left-2 flex items-center text-xs font-bold text-ink">
                  {pct(t.champion)}
                </span>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-mute">
          Bar length is relative to the favorite. Reach-the-final and
          reach-the-semis odds are in the table below.
        </p>
      </section>

      {/* Round-by-round table */}
      <section className="mt-8 overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-mute/30 text-left text-xs uppercase tracking-wide text-mute">
              <th className="py-2">Team</th>
              <th className="py-2 text-right">Win group</th>
              <th className="py-2 text-right">Reach R16</th>
              <th className="py-2 text-right">Reach QF</th>
              <th className="py-2 text-right">Reach SF</th>
              <th className="py-2 text-right">Final</th>
              <th className="py-2 text-right">Champion</th>
            </tr>
          </thead>
          <tbody>
            {sim.team_odds.slice(0, 16).map((t) => (
              <tr key={t.code} className="border-b border-mute/15">
                <td className="flex items-center gap-2 py-2 font-semibold text-ink">
                  <Flag team={t.name} size={20} /> {t.name}
                </td>
                <td className="py-2 text-right tabular-nums">{pct(t.group_winner)}</td>
                <td className="py-2 text-right tabular-nums">{pct(t.r16)}</td>
                <td className="py-2 text-right tabular-nums">{pct(t.quarterfinal)}</td>
                <td className="py-2 text-right tabular-nums">{pct(t.semifinal)}</td>
                <td className="py-2 text-right tabular-nums">{pct(t.final)}</td>
                <td className="py-2 text-right font-bold tabular-nums text-tomato">
                  {pct(t.champion)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Predicted group standings */}
      {sim.predicted_bracket.groups?.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-2 text-xl font-bold text-ink">
            Predicted group standings
          </h2>
          <p className="mb-4 text-sm text-mute">
            How the model expects each group to finish, which determines who
            feeds into the bracket below.
          </p>
          <GroupStandings groups={sim.predicted_bracket.groups} />
        </section>
      )}

      {/* Predicted bracket */}
      <section className="mt-12">
        <h2 className="mb-2 text-xl font-bold text-ink">
          Most likely path to the final
        </h2>
        <p className="mb-4 text-sm text-mute">
          The favorite advances at each step. Percentages are that team&apos;s
          win chance in the matchup.
        </p>
        <CenteredBracket rounds={sim.predicted_bracket.rounds} />
      </section>

      <p className="mt-8 text-xs text-mute">
        Simulated {formatDateTime(sim.simulated_at)} ET.
      </p>
    </main>
  );
}
