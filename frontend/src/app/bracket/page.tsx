import { getKnockoutMatches, type FixtureRow } from "@/lib/queries";
import { Flag } from "@/components/Flag";

export const dynamic = "force-dynamic";

const ROUND_ORDER = ["r32", "r16", "qf", "sf", "f"] as const;
const ROUND_LABEL: Record<string, string> = {
  r32: "Round of 32",
  r16: "Round of 16",
  qf: "Quarter-finals",
  sf: "Semi-finals",
  f: "Final",
};

function TeamSlot({
  name,
  prob,
  favored,
}: {
  name: string | null;
  prob: number | null;
  favored: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-2 px-2 py-1.5 ${
        favored ? "bg-tomato-50" : ""
      }`}
    >
      <span className="flex items-center gap-2 truncate">
        {name ? <Flag team={name} size={20} /> : <span className="text-mute">·</span>}
        <span
          className={`truncate text-sm ${
            name ? "font-semibold text-ink" : "italic text-mute"
          }`}
        >
          {name ?? "TBD"}
        </span>
      </span>
      {prob != null && (
        <span className="shrink-0 text-xs font-bold text-tomato">{prob}%</span>
      )}
    </div>
  );
}

function BracketMatch({ m }: { m: FixtureRow }) {
  const h = m.p_home_win ? Math.round(parseFloat(m.p_home_win) * 100) : null;
  const a = m.p_away_win ? Math.round(parseFloat(m.p_away_win) * 100) : null;
  const homeFav = h != null && a != null && h >= a;
  return (
    <div className="divide-y divide-mute/20 overflow-hidden rounded-lg border border-mute/30 bg-paper shadow-sm">
      <TeamSlot name={m.home_team} prob={h} favored={homeFav} />
      <TeamSlot name={m.away_team} prob={a} favored={a != null && !homeFav} />
    </div>
  );
}

export default async function BracketPage() {
  const all = await getKnockoutMatches();
  const byRound = new Map<string, FixtureRow[]>();
  for (const m of all) {
    if (!byRound.has(m.stage)) byRound.set(m.stage, []);
    byRound.get(m.stage)!.push(m);
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-3xl font-extrabold text-ink">Knockout Bracket</h1>
      <p className="mt-2 text-mute">
        The path to the final. Teams fill in as the group stage resolves; once a
        matchup is set, the model posts win probabilities.
      </p>

      <div className="mt-8 flex gap-5 overflow-x-auto pb-4">
        {ROUND_ORDER.filter((r) => byRound.has(r)).map((round) => (
          <section key={round} className="min-w-[230px] flex-1">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-mute">
              {ROUND_LABEL[round]}
            </h2>
            <div className="grid gap-3">
              {byRound.get(round)!.map((m) => (
                <BracketMatch key={m.fixture_id} m={m} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
