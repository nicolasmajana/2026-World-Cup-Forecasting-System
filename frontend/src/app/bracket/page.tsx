import { CenteredBracket } from "@/components/CenteredBracket";
import { bracketRounds } from "@/lib/bracket2026";
import { getKnockoutSlots } from "@/lib/queries";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Bracket - WC 2026 Forecasts",
  description: "The 2026 World Cup knockout bracket, from the Round of 32 to the Final.",
};

export default async function BracketPage() {
  const slots = await getKnockoutSlots();
  const rounds = bracketRounds(slots);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-3xl font-extrabold text-ink">Knockout Bracket</h1>
      <p className="mt-2 max-w-2xl text-mute">
        The path to the final. Slots show where each group&apos;s finishers feed
        in; real teams and winners fill in automatically as results come in. For
        the model&apos;s projected matchups and winners, see the{" "}
        <a href="/predicted" className="font-semibold text-tomato hover:underline">
          Predicted Tournament
        </a>
        .
      </p>

      <div className="mt-8">
        <CenteredBracket rounds={rounds} />
      </div>
    </main>
  );
}
