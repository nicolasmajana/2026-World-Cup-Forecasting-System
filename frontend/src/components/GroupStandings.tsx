import type { PredictedGroup } from "@/lib/queries";
import { Flag } from "./Flag";

/** Predicted final group standings (expected record), with the two automatic
 * qualifiers and any best-third-place qualifier highlighted. */
export function GroupStandings({ groups }: { groups: PredictedGroup[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {groups.map((g) => (
        <div
          key={g.name}
          className="overflow-hidden rounded-xl border border-mute/30 bg-paper shadow-sm"
        >
          <div className="flex items-center justify-between bg-ink px-3 py-1.5">
            <span className="text-sm font-bold text-paper">{g.name}</span>
            <span className="text-[10px] uppercase tracking-wide text-paper/60">
              Pts
            </span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-mute">
                <th className="py-1 pl-2 text-left font-semibold">#</th>
                <th className="py-1 text-left font-semibold">Team</th>
                <th className="py-1 text-center font-semibold">W</th>
                <th className="py-1 text-center font-semibold">D</th>
                <th className="py-1 text-center font-semibold">L</th>
                <th className="py-1 text-center font-semibold">GD</th>
                <th className="py-1 pr-2 text-right font-semibold">Pts</th>
              </tr>
            </thead>
            <tbody>
              {g.teams.map((t) => (
                <tr
                  key={t.code}
                  className={`border-t border-mute/15 ${
                    t.qualified
                      ? "bg-tomato-50"
                      : t.third
                        ? "bg-sun-50"
                        : ""
                  }`}
                >
                  <td className="py-1.5 pl-2 font-bold text-mute">{t.pos}</td>
                  <td className="py-1.5">
                    <span className="flex items-center gap-1.5">
                      <Flag team={t.name} size={18} />
                      <span className="truncate font-semibold text-ink">
                        {t.name}
                      </span>
                    </span>
                  </td>
                  <td className="py-1.5 text-center tabular-nums">{t.w}</td>
                  <td className="py-1.5 text-center tabular-nums">{t.d}</td>
                  <td className="py-1.5 text-center tabular-nums">{t.l}</td>
                  <td className="py-1.5 text-center tabular-nums">
                    {t.gd > 0 ? `+${t.gd}` : t.gd}
                  </td>
                  <td className="py-1.5 pr-2 text-right font-extrabold tabular-nums text-ink">
                    {t.pts}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      <p className="col-span-full text-xs text-mute">
        <span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-tomato-50 align-middle ring-1 ring-tomato/40" />
        top two advance automatically
        <span className="ml-4 mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-sun-50 align-middle ring-1 ring-sun/50" />
        best-third-place qualifier. Records are expected values from the
        simulation, so a 3-game total may round to fewer than 3.
      </p>
    </div>
  );
}
