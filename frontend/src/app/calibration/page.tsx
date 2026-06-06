import {
  getReliabilityBins,
  getCalibrationSummary,
  type ReliabilityBin,
} from "@/lib/queries";

export const dynamic = "force-dynamic";

const SIZE = 360;
const PAD = 36;

function ReliabilityDiagram({ bins }: { bins: ReliabilityBin[] }) {
  const plot = SIZE - PAD * 2;
  const x = (p: number) => PAD + p * plot;
  const y = (p: number) => SIZE - PAD - p * plot;

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full max-w-md" role="img">
      {/* axes */}
      <line x1={PAD} y1={SIZE - PAD} x2={SIZE - PAD} y2={SIZE - PAD} stroke="var(--color-mute)" />
      <line x1={PAD} y1={PAD} x2={PAD} y2={SIZE - PAD} stroke="var(--color-mute)" />
      {/* perfect-calibration diagonal */}
      <line
        x1={x(0)}
        y1={y(0)}
        x2={x(1)}
        y2={y(1)}
        stroke="var(--color-mute)"
        strokeDasharray="4 4"
        strokeOpacity={0.6}
      />
      {/* points */}
      {bins.map((b) => (
        <circle
          key={b.bucket}
          cx={x(b.mean_predicted)}
          cy={y(b.observed_freq)}
          r={Math.max(3, Math.min(10, Math.sqrt(b.n)))}
          fill="var(--color-tomato)"
          fillOpacity={0.75}
        />
      ))}
      <text x={SIZE / 2} y={SIZE - 6} fontSize={11} textAnchor="middle" fill="var(--color-mute)">
        Predicted home-win probability
      </text>
      <text
        x={12}
        y={SIZE / 2}
        fontSize={11}
        textAnchor="middle"
        fill="var(--color-mute)"
        transform={`rotate(-90 12 ${SIZE / 2})`}
      >
        Observed frequency
      </text>
    </svg>
  );
}

export default async function CalibrationPage() {
  const [bins, summary] = await Promise.all([
    getReliabilityBins(),
    getCalibrationSummary(),
  ]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-extrabold text-ink">Calibration</h1>
      <p className="mt-2 max-w-2xl text-mute">
        A forecast is well-calibrated when events it calls 70% likely happen
        about 70% of the time. Points on the dashed line are perfectly
        calibrated; above it the model was too cautious, below it too confident.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat
          label="Brier score"
          value={summary.mean_brier != null ? summary.mean_brier.toFixed(4) : "—"}
          hint="lower is better"
        />
        <Stat label="Matches scored" value={String(summary.scored_matches)} hint="so far" />
      </div>

      <section className="mt-8 rounded-2xl border border-mute/30 bg-paper p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-bold text-ink">Reliability diagram</h2>
        {bins.length === 0 ? (
          <p className="text-sm text-mute">
            No completed matches yet — the diagram fills in once results start
            coming in and predictions get scored.
          </p>
        ) : (
          <ReliabilityDiagram bins={bins} />
        )}
      </section>
    </main>
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
