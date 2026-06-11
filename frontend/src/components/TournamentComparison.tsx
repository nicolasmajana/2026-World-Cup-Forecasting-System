import type { TournamentComparison as Data } from "@/lib/queries";
import { Flag } from "./Flag";
import { formatDate } from "@/lib/datetime";

/** The initial pre-tournament prediction scored against what actually
 * happened, round by round, with a headline success percentage. Fills in as
 * the bracket resolves; complete after the final. */
export function TournamentComparison({ data }: { data: Data }) {
  const resolvedRounds = data.rounds.filter((r) => r.resolved > 0);
  const totalHits = resolvedRounds.reduce((s, r) => s + r.hits, 0);
  const totalResolved = resolvedRounds.reduce((s, r) => s + r.resolved, 0);
  const overall =
    totalResolved > 0 ? Math.round((totalHits / totalResolved) * 100) : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div className="rounded-xl border border-mute/30 bg-paper p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-mute">
            Prediction success
          </p>
          <p className="mt-1 text-3xl font-extrabold tabular-nums text-tomato">
            {overall != null ? `${overall}%` : "-"}
          </p>
          <p className="text-xs text-mute">
            {totalResolved > 0
              ? `${totalHits} of ${totalResolved} resolved slots called`
              : "fills in as rounds resolve"}
          </p>
        </div>
        <div className="text-sm text-mute">
          <p>
            Scored against the prediction locked{" "}
            <span className="font-semibold text-ink">{formatDate(data.initial_at)}</span>,
            before the opening match.
          </p>
          <p className="mt-1">
            Initial predicted champion (highest title odds):{" "}
            <span className="inline-flex items-center gap-1 font-bold text-ink">
              <Flag team={data.predicted_champion ?? ""} size={16} />
              {data.predicted_champion ?? "-"}
            </span>
            {data.actual_champion && (
              <>
                {" · "}Actual champion:{" "}
                <span className="inline-flex items-center gap-1 font-bold text-tomato">
                  <Flag team={data.actual_champion} size={16} />
                  {data.actual_champion}
                </span>
              </>
            )}
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[460px] text-sm">
          <thead>
            <tr className="border-b border-mute/30 text-left text-xs uppercase tracking-wide text-mute">
              <th className="py-2">Round</th>
              <th className="py-2 text-center">Slots</th>
              <th className="py-2 text-center">Resolved</th>
              <th className="py-2 text-center">Called</th>
              <th className="py-2 text-right">Success</th>
            </tr>
          </thead>
          <tbody>
            {data.rounds.map((r) => {
              const rate =
                r.resolved > 0 ? `${Math.round((r.hits / r.resolved) * 100)}%` : "-";
              return (
                <tr key={r.key} className="border-b border-mute/15">
                  <td className="py-2 font-semibold text-ink">{r.label}</td>
                  <td className="py-2 text-center tabular-nums">{r.slots}</td>
                  <td className="py-2 text-center tabular-nums">
                    {r.resolved > 0 ? r.resolved : "-"}
                  </td>
                  <td className="py-2 text-center tabular-nums">
                    {r.resolved > 0 ? r.hits : "-"}
                  </td>
                  <td className="py-2 text-right font-bold tabular-nums text-tomato">
                    {rate}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-mute">
        A slot counts as called when the team that actually reached the round
        was among the initial prediction&apos;s most likely teams for it (top
        32 for the knockouts, top 8 for the quarter-finals, and so on).
      </p>
    </div>
  );
}
