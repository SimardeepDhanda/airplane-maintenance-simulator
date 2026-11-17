"use client";

import type { Flight, PlanningStatus } from "@/lib/api/schemas";
import { localTime, utcDay } from "@/lib/format";

const BAR: Record<"flagged-critical" | "flagged-review" | "normal", string> = {
  "flagged-critical": "bg-crit",
  "flagged-review": "bg-warn",
  normal: "bg-fg-subtle/70 hover:bg-fg-muted",
};

/**
 * Rows = ships, x = UTC time across the horizon. Each bar is one leg; flagged legs take the
 * engine's planning-status colour. Gaps between bars are ground time.
 */
export function RotationTimeline({
  flights,
  start,
  end,
  statusByAircraft,
  selectedId,
  onSelect,
}: {
  flights: readonly Flight[];
  start: string;
  end: string;
  statusByAircraft: Record<string, PlanningStatus>;
  selectedId: string | null;
  onSelect: (flight: Flight) => void;
}) {
  const t0 = Date.parse(start);
  const t1 = Date.parse(end);
  const span = t1 - t0;
  const pct = (iso: string) => ((Date.parse(iso) - t0) / span) * 100;
  const ships = [...new Set(flights.map((f) => f.aircraft_id))].sort();
  const days: Date[] = [];
  for (
    let d = new Date(
      Date.UTC(
        new Date(t0).getUTCFullYear(),
        new Date(t0).getUTCMonth(),
        new Date(t0).getUTCDate() + 1,
      ),
    );
    d.getTime() < t1;
    d = new Date(d.getTime() + 86_400_000)
  ) {
    days.push(d);
  }

  return (
    <figure aria-label="Aircraft rotations" className="relative overflow-x-auto">
      <div className="min-w-[720px]">
        <div className="grid grid-cols-[3.5rem_1fr] pb-1">
          <span className="text-fg-subtle text-2xs">Ship</span>
          <div className="text-fg-subtle text-2xs relative h-4">
            {days.map((d) => (
              <span
                key={d.toISOString()}
                className="absolute pl-1 whitespace-nowrap"
                style={{ left: `${((d.getTime() - t0) / span) * 100}%` }}
              >
                {utcDay(d)}
              </span>
            ))}
          </div>
        </div>
        {ships.map((ship) => (
          <div key={ship} className="grid grid-cols-[3.5rem_1fr] items-center">
            <span className="text-fg-muted font-mono text-xs">{ship}</span>
            <div className="border-line relative h-5 border-b">
              {days.map((d) => (
                <span
                  key={d.toISOString()}
                  aria-hidden
                  className="bg-line absolute top-0 h-full w-px"
                  style={{ left: `${((d.getTime() - t0) / span) * 100}%` }}
                />
              ))}
              {flights
                .filter((f) => f.aircraft_id === ship)
                .map((f) => {
                  const kind = f.flagged
                    ? statusByAircraft[ship] === "critical"
                      ? "flagged-critical"
                      : "flagged-review"
                    : "normal";
                  const selected = f.id === selectedId;
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => onSelect(f)}
                      aria-label={`${f.id} ${f.origin}–${f.destination}${f.flagged ? ", flagged" : ""}`}
                      aria-pressed={selected}
                      title={`${f.flight_number} ${f.origin}–${f.destination}\n${localTime(f.departure_local, f.origin_tz, f.origin_tz_abbr)} → ${localTime(f.arrival_local, f.destination_tz, f.destination_tz_abbr)}\nCumulative ${f.cumulative_cycles} cyc${f.flagged ? " · flagged" : ""}`}
                      className={`absolute top-1 h-3 min-w-[3px] rounded-[2px] ${BAR[kind]} ${
                        selected
                          ? "ring-fg ring-2 ring-offset-1 ring-offset-[var(--color-canvas)]"
                          : ""
                      }`}
                      style={{
                        left: `${pct(f.departure)}%`,
                        width: `calc(${pct(f.arrival) - pct(f.departure)}% - 2px)`,
                      }}
                    />
                  );
                })}
            </div>
          </div>
        ))}
      </div>
      <figcaption className="text-fg-subtle text-2xs mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-fg-subtle/70 h-2.5 w-4 rounded-[2px]" /> Leg
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-warn h-2.5 w-4 rounded-[2px]" /> Flagged, review
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-crit h-2.5 w-4 rounded-[2px]" /> Flagged, critical
        </span>
        <span>Time axis UTC</span>
      </figcaption>
    </figure>
  );
}
