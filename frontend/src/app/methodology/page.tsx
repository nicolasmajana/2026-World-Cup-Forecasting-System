import { getLatestModelRun } from "@/lib/queries";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Methodology, WC 2026 Forecasts",
  description:
    "How the model turns 150 years of football results into probabilities, explained plainly, then in technical depth.",
};

export default async function MethodologyPage() {
  const run = await getLatestModelRun();

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-4xl font-extrabold tracking-tight text-ink">
        How this works
      </h1>
      <p className="mt-3 text-lg text-mute">
        No crystal ball, just goals, history, and honest accounting. Here&apos;s
        the whole method, first in plain language, then for the technically
        curious.
      </p>

      {/* Plain-language */}
      <Section title="The plain version">
        <p>
          Football is mostly about goals, and goals arrive somewhat randomly. A
          team that creates a lot and concedes little will <em>tend</em> to score
          more, but any single match can swing on a deflection or a red card.
        </p>
        <p>
          So instead of predicting one scoreline, the model estimates how many
          goals each team is <strong>likely</strong> to score, then plays the
          match out <strong>10,000 times</strong> on a computer. Maybe Brazil
          wins 6,200 of those, draws 1,900, loses 1,900, that becomes{" "}
          <span className="font-semibold text-tomato">62% / 19% / 19%</span>.
          Probabilities, not certainties.
        </p>
      </Section>

      <Section title="What the model looks at">
        <ul className="list-inside list-disc space-y-1">
          <li>Recent attacking and defensive form (last 10 matches)</li>
          <li>Long-run team strength (Elo rating)</li>
          <li>Home / away / neutral venue</li>
          <li>The opponent&apos;s defensive strength</li>
        </ul>
        <p>
          It learned these patterns from <strong>49,000+ international matches
          going back to 1872</strong>.
        </p>
      </Section>

      <Section title="Why you can trust the number">
        <p>
          Every prediction is written to a database and{" "}
          <strong>locked with a timestamp before kickoff</strong>. After the
          match starts, it physically cannot be edited, that rule is enforced by
          the database itself, not just a promise. So this is a public record:
          you can always check what the model said <em>before</em> the ball was
          kicked.
        </p>
        <p>
          And it&apos;s graded honestly. The headline metric isn&apos;t
          &quot;accuracy&quot; (a vanity number) but the{" "}
          <strong>Brier score</strong>, which rewards being well-calibrated:
          your 70% calls actually happening about 70% of the time. See the{" "}
          <a href="/calibration" className="font-semibold text-tomato hover:underline">
            calibration page
          </a>
          .
        </p>
      </Section>

      {/* Technical depth */}
      <Section title="The technical version">
        <p>
          The model is a two-stage Poisson process. Stage one is a{" "}
          <strong>Poisson regression</strong> predicting each team&apos;s
          expected goals (λ) from the features above. Stage two is a{" "}
          <strong>Monte Carlo simulation</strong>: draw each side&apos;s goals
          from Poisson(λ) ten thousand times and count outcomes.
        </p>
        <p>
          Trained on all internationals before 2024 and validated on 2024-2025
          as a true hold-out. It currently posts a{" "}
          <strong>
            Brier score of {run?.val_brier_score ?? "≈0.19"}
          </strong>{" "}
          on that hold-out, beating a base-rate baseline by ~9%. Deliberately
          simple for v1; bivariate Poisson (correlated scoring) and gradient
          boosting are the planned next steps.
        </p>
        <p className="text-sm text-mute">
          Stack: Python (pandas, scikit-learn) · PostgreSQL · FastAPI ·
          Next.js · automated daily via GitHub Actions.
        </p>
      </Section>

      {run && (
        <p className="mt-10 border-t border-mute/20 pt-6 text-xs text-mute">
          Current model: <code>{run.model_version}</code>, trained on{" "}
          {run.n_train_matches?.toLocaleString()} matches, last run{" "}
          {new Date(run.run_at).toLocaleDateString()}.
        </p>
      )}
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-xl font-bold text-ink">{title}</h2>
      <div className="space-y-3 leading-relaxed text-ink/90">{children}</div>
    </section>
  );
}
