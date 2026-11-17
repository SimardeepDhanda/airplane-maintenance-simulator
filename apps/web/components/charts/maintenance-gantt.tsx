"use client";

import type { MaintenanceResources, PlacementT } from "@/lib/api/schemas";
import { utcDay, utcTime } from "@/lib/format";
import { dayStarts, nightBands } from "@/lib/timeline";

const JOB_LABEL = { engine_change: "Engine change", borescope: "Borescope" } as const;

/**
 * Rows = maintenance bays grouped by facility; x = UTC across the horizon. Shaded bands are each
 * facility's night shift (local time, so they move with DST). Bars are jobs; amber bars start
 * after the engine has flown past its planning threshold.
 */
export function MaintenanceGantt({
  facilities,
  placements,
  start,
  end,
  selectedId,
  onSelect,
}: {
  facilities: MaintenanceResources["facilities"];
  placements: readonly PlacementT[];
  start: string;
  end: string;
  selectedId: string | null;
  onSelect: (jobId: string) => void;
}) {
  const t0 = Date.parse(start);
  const t1 = Date.parse(end);
  const span = t1 - t0;
  const x = (t: number) => ((t - t0) / span) * 100;
  const days = dayStarts(t0, t1);

  // Scenario bay additions appear as extra rows (e.g. DEN-3).
  const rows = facilities.flatMap((f) => {
    const named = f.bays.map((b) => b.id);
    const extra = [
      ...new Set(placements.filter((p) => p.facility === f.code).map((p) => p.bay)),
    ].filter((b) => !named.includes(b));
    return [...named, ...extra.sort()].map((bay) => ({ facility: f, bay }));
  });

  return (
    <figure aria-label="Maintenance calendar" className="relative overflow-x-auto">
      <div className="min-w-[720px]">
        <div className="grid grid-cols-[4.5rem_1fr] pb-1">
          <span className="text-fg-subtle text-2xs">Bay</span>
          <div className="text-fg-subtle text-2xs relative h-4">
            {days.map((d) => (
              <span
                key={d.toISOString()}
                className="absolute pl-1 whitespace-nowrap"
                style={{ left: `${x(d.getTime())}%` }}
              >
                {utcDay(d)}
              </span>
            ))}
          </div>
        </div>
        {rows.map(({ facility, bay }, i) => {
          const first = i === 0 || rows[i - 1]?.facility.code !== facility.code;
          const bands = nightBands(facility.shifts, facility.timezone, t0, t1);
          return (
            <div
              key={bay}
              className={`grid grid-cols-[4.5rem_1fr] items-center ${first && i > 0 ? "mt-1.5" : ""}`}
            >
              <span className="text-fg-muted font-mono text-xs">{bay}</span>
              <div className="border-line relative h-7 border-b">
                {bands.map(([a, b]) => (
                  <span
                    key={a}
                    aria-hidden
                    className="bg-raised absolute top-0 h-full"
                    style={{ left: `${x(a)}%`, width: `${x(b) - x(a)}%` }}
                  />
                ))}
                {days.map((d) => (
                  <span
                    key={d.toISOString()}
                    aria-hidden
                    className="bg-line absolute top-0 h-full w-px"
                    style={{ left: `${x(d.getTime())}%` }}
                  />
                ))}
                {placements
                  .filter((p) => p.bay === bay)
                  .map((p) => {
                    const selected = p.job_id === selectedId;
                    const late = p.cycles_over > 0;
                    return (
                      <button
                        key={p.job_id}
                        type="button"
                        onClick={() => onSelect(p.job_id)}
                        aria-pressed={selected}
                        aria-label={`${p.engine_id ?? p.aircraft_id} ${JOB_LABEL[p.job_type]} ${p.bay} ${utcTime(p.start)}${late ? ", past threshold" : ""}`}
                        title={`${p.engine_id ?? p.aircraft_id} · ${JOB_LABEL[p.job_type]}\n${utcTime(p.start)} → ${utcTime(p.end)}\n${p.cancelled_flights.length} cancelled legs${late ? ` · ${p.cycles_over} cyc past threshold` : ""}`}
                        className={`text-2xs absolute top-1 flex h-5 items-center overflow-hidden rounded-[2px] px-1 font-mono whitespace-nowrap ${
                          late ? "bg-warn text-canvas" : "bg-accent text-canvas"
                        } ${p.job_type === "borescope" ? "opacity-80" : ""} ${
                          selected
                            ? "ring-fg ring-2 ring-offset-1 ring-offset-[var(--color-canvas)]"
                            : ""
                        }`}
                        style={{
                          left: `${x(Date.parse(p.start))}%`,
                          width: `calc(${x(Date.parse(p.end)) - x(Date.parse(p.start))}% - 2px)`,
                        }}
                      >
                        {p.engine_id ?? p.aircraft_id}
                      </button>
                    );
                  })}
              </div>
            </div>
          );
        })}
      </div>
      <figcaption className="text-fg-subtle text-2xs mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-accent h-2.5 w-4 rounded-[2px]" /> Before threshold
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-warn h-2.5 w-4 rounded-[2px]" /> Past threshold
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-raised border-line-strong h-2.5 w-4 border" /> Night shift
          (local)
        </span>
        <span>Time axis UTC</span>
      </figcaption>
    </figure>
  );
}
