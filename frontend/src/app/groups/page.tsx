import { getGroupMatches, type FixtureRow } from "@/lib/queries";
import { MatchCard } from "@/components/MatchCard";
import { Flag } from "@/components/Flag";

export const dynamic = "force-dynamic";

function teamsInGroup(matches: FixtureRow[]): string[] {
  const set = new Set<string>();
  for (const m of matches) {
    if (m.home_team) set.add(m.home_team);
    if (m.away_team) set.add(m.away_team);
  }
  return [...set].sort();
}

export default async function GroupsPage() {
  const all = await getGroupMatches();

  // group by group_name
  const groups = new Map<string, FixtureRow[]>();
  for (const m of all) {
    const key = m.group_name ?? "—";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }
  const sortedGroups = [...groups.entries()].sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-3xl font-extrabold text-ink">Group Stage</h1>
      <p className="mt-2 text-mute">
        48 teams · 12 groups · top two plus the eight best third-place teams
        advance to the Round of 32. Probabilities are the model&apos;s locked
        forecasts.
      </p>

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        {sortedGroups.map(([name, matches]) => (
          <section
            key={name}
            className="rounded-2xl border border-mute/30 bg-paper p-5 shadow-sm"
          >
            <div className="mb-3 flex items-center gap-2">
              <span className="inline-flex h-7 items-center rounded-md bg-ink px-2 text-sm font-bold text-paper">
                {name}
              </span>
            </div>

            {/* Teams in this group */}
            <ul className="mb-4 grid grid-cols-2 gap-2">
              {teamsInGroup(matches).map((t) => (
                <li key={t} className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <Flag team={t} size={22} />
                  <span className="truncate">{t}</span>
                </li>
              ))}
            </ul>

            {/* Matches */}
            <div className="grid gap-3">
              {matches.map((m) => (
                <MatchCard
                  key={m.fixture_id}
                  m={{
                    ...m,
                    home_team: m.home_team ?? "TBD",
                    home_code: m.home_code ?? "",
                    away_team: m.away_team ?? "TBD",
                    away_code: m.away_code ?? "",
                    group_name: m.group_name,
                    stage: m.stage,
                    locked_at: null,
                    brier_score: null,
                  }}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
