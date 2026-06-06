"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Periodically re-fetches the current (dynamic) server route so locked
 * predictions, live scores, and the Brier score update on their own -
 * no manual reload. Default every 60s.
 */
export function AutoRefresh({ intervalMs = 60_000 }: { intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(id);
  }, [router, intervalMs]);
  return null;
}
