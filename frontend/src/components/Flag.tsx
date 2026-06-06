import { flagUrl } from "@/lib/flags";

/** Small country flag with a subtle border. Falls back to nothing if unknown. */
export function Flag({
  team,
  size = 24,
}: {
  team: string;
  size?: number;
}) {
  const url = flagUrl(team, 40);
  if (!url) {
    return (
      <span
        className="inline-block rounded-sm bg-mute-100"
        style={{ width: size, height: size * 0.67 }}
        aria-hidden
      />
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={`${team} flag`}
      width={size}
      height={size * 0.67}
      className="rounded-sm border border-black/10 object-cover"
      style={{ width: size, height: size * 0.67 }}
    />
  );
}
