"use client";

import { useSyncExternalStore } from "react";

function subscribe(onTick: () => void) {
  const id = window.setInterval(onTick, 1_000);
  return () => window.clearInterval(id);
}

function formatUtc(): string {
  return new Date().toISOString().slice(11, 16);
}

/** Operations run on UTC ("Zulu"). Rendered client-side only to avoid hydration drift. */
export function UtcClock() {
  const time = useSyncExternalStore(subscribe, formatUtc, () => null);
  return (
    <span className="text-fg-muted font-mono text-xs" aria-label="Current UTC time">
      {time ?? "--:--"}
      <span className="text-fg-subtle">Z</span>
    </span>
  );
}
