"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { BufferControl } from "@/components/controls/buffer-control";
import { Select } from "@/components/controls/select";
import { RotationTimeline } from "@/components/charts/rotation-timeline";
import { Empty, Loading, QueryError } from "@/components/feedback/query-state";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";
import { useAirports, useEngines, useFleetSummary, useFlights } from "@/lib/api/queries";
import type { Flight, PlanningStatus } from "@/lib/api/schemas";
import { cycles, localTime, utcDay, utcTime } from "@/lib/format";
import { parseBuffer, useUrlState } from "@/lib/use-url-state";

export function FlightsView() {
  const { params, set } = useUrlState();
  const bufferParam = parseBuffer(params.get("buffer"));
  const aircraft = params.get("aircraft") ?? "";
  const origin = params.get("origin") ?? "";
  const day = params.get("day") ?? "";
  const flaggedOnly = params.get("flagged") === "1";
  const selectedId = params.get("flight");

  const summary = useFleetSummary(bufferParam);
  const engines = useEngines({ buffer: bufferParam, page_size: 100 });
  const airports = useAirports();
  const dayStart = day ? `${day}T00:00:00Z` : undefined;
  const dayEnd = day
    ? new Date(Date.parse(`${day}T00:00:00Z`) + 86_400_000).toISOString()
    : undefined;
  const flights = useFlights({
    buffer: bufferParam,
    aircraft_id: aircraft || undefined,
    origin: origin || undefined,
    departure_from: dayStart,
    departure_to: dayEnd,
    flagged: flaggedOnly ? true : undefined,
    page_size: 1000,
  });

  const statusByAircraft = useMemo(() => {
    const out: Record<string, PlanningStatus> = {};
    for (const e of engines.data?.items ?? [])
      if (e.aircraft_id) out[e.aircraft_id] = e.planning.status;
    return out;
  }, [engines.data]);

  const days = useMemo(() => {
    if (!summary.data) return [];
    const out: string[] = [];
    const end = Date.parse(summary.data.horizon_end);
    const s = new Date(summary.data.as_of);
    for (
      let t = Date.UTC(s.getUTCFullYear(), s.getUTCMonth(), s.getUTCDate());
      t < end;
      t += 86_400_000
    ) {
      out.push(new Date(t).toISOString().slice(0, 10));
    }
    return out;
  }, [summary.data]);

  const rowRef = useRef<HTMLTableRowElement | null>(null);
  useEffect(() => {
    rowRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedId, flights.data]);

  const items = flights.data?.items ?? [];
  const select = (f: Flight) => set({ flight: f.id === selectedId ? null : f.id });
  const buffer = summary.data?.planning_buffer ?? bufferParam ?? 10;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Flight schedule" />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Select
          label="Ship"
          value={aircraft}
          options={Object.keys(statusByAircraft)
            .sort()
            .map((a) => ({ value: a, label: a }))}
          onChange={(v) => set({ aircraft: v || null, flight: null })}
        />
        <Select
          label="Origin"
          value={origin}
          options={(airports.data ?? []).map((a) => ({ value: a.code, label: a.code }))}
          onChange={(v) => set({ origin: v || null, flight: null })}
        />
        <Select
          label="Day (UTC)"
          value={day}
          allLabel="Full horizon"
          options={days.map((d) => ({ value: d, label: utcDay(`${d}T00:00:00Z`) }))}
          onChange={(v) => set({ day: v || null, flight: null })}
        />
        <label className="text-fg-muted flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => set({ flagged: e.target.checked ? "1" : null, flight: null })}
            className="accent-[var(--color-accent)]"
          />
          Flagged only
        </label>
        <BufferControl value={buffer} onChange={(v) => set({ buffer: v })} />
        <span className="text-fg-subtle ml-auto text-xs" aria-live="polite">
          {flights.data
            ? flights.data.total > flights.data.items.length
              ? `first ${flights.data.items.length} of ${flights.data.total} legs`
              : `${flights.data.total} legs`
            : ""}
        </span>
      </div>

      {flights.isError ? (
        <QueryError error={flights.error} onRetry={() => void flights.refetch()} />
      ) : !flights.data || !summary.data ? (
        <Loading label="flights" className="h-96" />
      ) : items.length === 0 ? (
        <Empty>No legs match these filters</Empty>
      ) : (
        <>
          <Section title="Rotations">
            <RotationTimeline
              flights={items}
              start={dayStart ?? summary.data.as_of}
              end={dayEnd ?? summary.data.horizon_end}
              statusByAircraft={statusByAircraft}
              selectedId={selectedId}
              onSelect={select}
            />
          </Section>
          <Section
            title="Legs"
            aside={<span className="text-fg-subtle text-2xs">times local to each airport</span>}
          >
            <div className="max-h-[28rem] overflow-auto">
              <table className="w-full min-w-[820px] text-xs">
                <thead className="bg-canvas text-fg-subtle sticky top-0">
                  <tr className="border-line-strong border-b text-left">
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Flight
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Ship
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Engine
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Route
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Departs
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Arrives
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      UTC
                    </th>
                    <th scope="col" className="px-2 py-1.5 text-right font-normal">
                      Cum. cyc
                    </th>
                    <th scope="col" className="px-2 py-1.5 text-right font-normal">
                      L after
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((f) => {
                    const selected = f.id === selectedId;
                    return (
                      <tr
                        key={f.id}
                        ref={selected ? rowRef : undefined}
                        aria-selected={selected}
                        onClick={() => select(f)}
                        className={`border-line cursor-pointer border-b ${
                          selected ? "bg-accent-muted" : "hover:bg-raised/60"
                        } ${f.flagged ? "" : "text-fg-muted"}`}
                      >
                        <td className="px-2 py-1 font-mono">
                          <button
                            type="button"
                            aria-pressed={selected}
                            aria-label={`Select ${f.id}`}
                            onClick={(ev) => {
                              ev.stopPropagation();
                              select(f);
                            }}
                            className="hover:text-fg"
                          >
                            {f.flight_number}
                          </button>
                          {f.flagged ? (
                            <span
                              className={`ml-1.5 inline-block size-1.5 rounded-full ${
                                statusByAircraft[f.aircraft_id] === "critical"
                                  ? "bg-crit"
                                  : "bg-warn"
                              }`}
                              role="img"
                              aria-label="flagged"
                            />
                          ) : null}
                        </td>
                        <td className="px-2 py-1 font-mono">{f.aircraft_id}</td>
                        <td className="px-2 py-1 font-mono">
                          {f.engine_id ? (
                            <Link
                              href={`/engines/${f.engine_id}${bufferParam !== undefined ? `?buffer=${bufferParam}` : ""}`}
                              className="text-accent hover:underline"
                              onClick={(ev) => ev.stopPropagation()}
                            >
                              {f.engine_id}
                            </Link>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-2 py-1">
                          {f.origin}–{f.destination}
                        </td>
                        <td className="px-2 py-1 font-mono">
                          {localTime(f.departure_local, f.origin_tz, f.origin_tz_abbr)}
                        </td>
                        <td className="px-2 py-1 font-mono">
                          {localTime(f.arrival_local, f.destination_tz, f.destination_tz_abbr)}
                        </td>
                        <td className="text-fg-subtle px-2 py-1 font-mono">
                          {utcTime(f.departure)}
                        </td>
                        <td className="px-2 py-1 text-right font-mono">{f.cumulative_cycles}</td>
                        <td className="px-2 py-1 text-right font-mono">
                          {f.conservative_margin_after !== null
                            ? cycles(f.conservative_margin_after)
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
