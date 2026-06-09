import type { ChampionHistory as Data } from "@/lib/queries";
import { Flag } from "./Flag";
import { formatDate } from "@/lib/datetime";

function cell(v: number | null): string {
  if (v == null) return "-";
  if (v === 0) return "0%";
  return v >= 0.1 ? `${Math.round(v * 100)}%` : `${(v * 100).toFixed(1)}%`;
}

/** Champion odds for the top contenders, one column per day. The last column
 * is today's run; earlier columns let you see the trend as results come in. */
export function ChampionHistory({ data }: { data: Data }) {
  if (data.teams.length === 0) return null;
  const last = data.columns.length - 1;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-sm">
        <thead>
          <tr className="border-b border-mute/30 text-xs uppercase tracking-wide text-mute">
            <th className="py-2 pr-3 text-left font-semibold">Team</th>
            {data.columns.map((c, i) => (
              <th
                key={c}
                className={`py-2 px-2 text-right font-semibold ${i === last ? "text-ink" : ""}`}
              >
                {formatDate(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.teams.map((t) => (
            <tr key={t.code} className="border-b border-mute/15">
              <td className="flex items-center gap-2 py-2 pr-3 font-semibold text-ink">
                <Flag team={t.name} size={20} /> {t.name}
              </td>
              {t.values.map((v, i) => (
                <td
                  key={i}
                  className={`py-2 px-2 text-right tabular-nums ${
                    i === last ? "font-extrabold text-tomato" : "text-mute"
                  }`}
                >
                  {cell(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.columns.length === 1 && (
        <p className="mt-2 text-xs text-mute">
          Only today&apos;s run so far. A new column appears each day, so the
          odds trend builds out as the tournament plays and results come in.
        </p>
      )}
    </div>
  );
}
