import { MatchCard } from "@/components/MatchCard";
import {
  getUpcomingPredictions,
  getCalibrationSummary,
  getLatestModelRun,
} from "@/lib/queries";

// Always render with fresh data from the database.
export const dynamic = "force-dynamic";

export default async function Home() {
  const [matches, calibration, modelRun] = await Promise.all([
    getUpcomingPredictions(30),
    getCalibrationSummary(),
    getLatestModelRun(),
  ]);

  const brier =
    calibration.mean_brier != null
      ? calibration.mean_brier.toFixed(4)
      : "—";

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">
          World Cup 2026 — Live Forecasts
        </h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Every prediction is locked with a timestamp <em>before</em> kickoff and
          can never be changed afterward. This is a public record of what the
          model said — and how right it turns out to be.
        </p>
      </header>

      {/* Headline stats */}
      <section className="mb-10 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat label="Brier score" value={brier} hint="lower is better" />
        <Stat
          label="Matches scored"
          value={String(calibration.scored_matches)}
          hint="so far"
        />
        <Stat
          label="Predictions locked"
          value={String(matches.length)}
          hint="upcoming"
        />
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold">Upcoming matches</h2>
        {matches.length === 0 ? (
          <p className="text-slate-500">No locked predictions yet.</p>
        ) : (
          <div className="grid gap-3">
            {matches.map((m) => (
              <MatchCard key={m.fixture_id} m={m} />
            ))}
          </div>
        )}
      </section>

      <footer className="mt-12 border-t border-slate-200 pt-6 text-xs text-slate-400 dark:border-slate-800">
        {modelRun ? (
          <p>
            Model <code>{modelRun.model_version}</code> · trained on{" "}
            {modelRun.n_train_matches?.toLocaleString()} matches · hold-out Brier{" "}
            {modelRun.val_brier_score} ·{" "}
            {new Date(modelRun.run_at).toLocaleDateString()}
          </p>
        ) : (
          <p>No model run recorded yet.</p>
        )}
      </footer>
    </main>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
      <p className="text-xs text-slate-400">{hint}</p>
    </div>
  );
}
