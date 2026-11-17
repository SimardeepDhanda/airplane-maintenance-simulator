"use client";

import Link from "next/link";
import type { EngineSummary } from "@/lib/api/schemas";
import { cycles, signedCycles } from "@/lib/format";

const FILL = { critical: "bg-crit", review: "bg-warn", ok: "bg-accent/60" } as const;

/**
 * Bullet rows: bar = lower-bound RUL (cycles), tick = cycles the schedule consumes in the horizon.
 * A tick past the bar means the conservative estimate runs out before the schedule does.
 */
export function CycleExposure({
  engines,
  buffer,
  hrefFor,
}: {
  engines: readonly EngineSummary[];
  buffer: number;
  hrefFor: (id: string) => string;
}) {
  const max = Math.max(
    25,
    ...engines.map((e) => Math.max(e.prediction.rul_lower, e.planning.forecast_cycles + buffer)),
  );
  const domain = Math.ceil(max / 25) * 25;
  const ticks = Array.from({ length: domain / 25 + 1 }, (_, i) => i * 25);
  const pct = (v: number) => `${(Math.max(0, Math.min(v, domain)) / domain) * 100}%`;

  return (
    <figure aria-label="Lower-bound RUL against scheduled cycles per engine">
      <div className="grid grid-cols-[7.5rem_1fr_4rem] items-end gap-x-3 pb-1">
        <span />
        <div className="text-fg-subtle text-2xs relative h-4">
          {ticks.map((t) => (
            <span key={t} className="absolute -translate-x-1/2 font-mono" style={{ left: pct(t) }}>
              {t}
            </span>
          ))}
        </div>
        <span className="text-fg-subtle text-2xs text-right">L − n</span>
      </div>
      <ul className="flex flex-col">
        {engines.map((e) => {
          const flagged = e.planning.status !== "ok";
          return (
            <li key={e.id}>
              <Link
                href={hrefFor(e.id)}
                className="hover:bg-raised/60 grid grid-cols-[7.5rem_1fr_4rem] items-center gap-x-3 rounded-sm py-[3px]"
                title={`${e.id}: lower bound ${cycles(e.prediction.rul_lower)} cyc, scheduled ${e.planning.forecast_cycles} cyc`}
              >
                <span className="flex items-baseline gap-2 text-xs">
                  <span className="font-mono">{e.id}</span>
                  <span className="text-fg-subtle">{e.aircraft_id}</span>
                </span>
                <span className="relative h-3">
                  {ticks.map((t) => (
                    <span
                      key={t}
                      aria-hidden
                      className="bg-line absolute top-0 h-full w-px"
                      style={{ left: pct(t) }}
                    />
                  ))}
                  <span
                    aria-hidden
                    className={`absolute top-0.5 left-0 h-2 rounded-r-[3px] ${FILL[e.planning.status]}`}
                    style={{ width: pct(e.prediction.rul_lower) }}
                  />
                  <span
                    aria-hidden
                    className="bg-fg absolute -top-0.5 h-4 w-0.5"
                    style={{ left: pct(e.planning.forecast_cycles) }}
                  />
                </span>
                <span
                  className={`text-right font-mono text-xs ${flagged ? "text-fg" : "text-fg-muted"}`}
                >
                  {signedCycles(e.planning.conservative_margin)}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      <figcaption className="text-fg-subtle text-2xs mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-accent/60 h-2 w-4 rounded-r-[3px]" />
          Lower-bound RUL
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-fg h-3 w-0.5" />
          Scheduled cycles (horizon)
        </span>
        <span>Bar colour = planning status</span>
      </figcaption>
    </figure>
  );
}
