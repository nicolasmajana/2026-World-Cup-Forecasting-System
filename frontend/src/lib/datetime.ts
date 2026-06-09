// All match times and timestamps are shown in US Eastern time, regardless of
// where the server renders (Vercel runs in UTC). Eastern is EDT in summer
// (during the tournament) and EST in winter; the label reflects whichever
// applies.
const TZ = "America/New_York";

/** "Wed, Jun 11, 3:00 PM EDT" — for match cards. */
export function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: TZ,
    timeZoneName: "short",
  });
}

/** "Jun 11, 2026, 3:00 PM EDT" — for detail headers and run timestamps. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: TZ,
  });
}

/** "Jun 11, 2026" — for dates without a time. */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: TZ,
  });
}
