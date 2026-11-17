"use client";

import Link from "next/link";
import { BufferControl } from "@/components/controls/buffer-control";
import { CycleExposure } from "@/components/charts/cycle-exposure";
import { Empty, Loading, QueryError } from "@/components/feedback/query-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";
import { useEngines, useFleetSummary, useFlights, useMaintenancePlan } from "@/lib/api/queries";
import { JOB_TYPE_LABEL, localTime, utcTime } from "@/lib/format";
import { parseBuffer, useUrlState } from "@/lib/use-url-state";

export function OverviewView() {
  const { params, set } = useUrlState();
  const bufferParam = parseBuffer(params.get("buffer"));
  const summary = useFleetSummary(bufferParam);
  const engines = useEngines({ buffer: bufferParam, sort: "conservative_margin", page_size: 100 });
  const buffer = summary.data?.planning_buffer ?? bufferParam ?? 10;
  const dayEnd = summary.data
    ? new Date(Date.parse(summary.data.as_of) + 86_400_000).toISOString()
    : undefined;
  const flagged = useFlights({
    buffer: bufferParam,
    flagged: true,
    departure_to: dayEnd,
    page_size: 8,
  });
  const q = (path: string) =>
    bufferParam !== undefined
      ? `${path}${path.includes("?") ? "&" : "?"}buffer=${bufferParam}`
      : path;
  const mx = useMaintenancePlan(bufferParam);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Fleet health"
        actions={<BufferControl value={buffer} onChange={(v) => set({ buffer: v })} />}
      />

      {summary.isError ? (
        <QueryError error={summary.error} onRetry={() => void summary.refetch()} />
      ) : !summary.data ? (
        <Loading label="fleet summary" className="h-9" />
      ) : (
        <dl className="border-line flex flex-wrap items-baseline gap-x-6 gap-y-2 border-y py-2 text-xs">
          <Fact label="As of">{utcTime(summary.data.as_of)}</Fact>
          <Fact label="Horizon">to {utcTime(summary.data.horizon_end)}</Fact>
          <Fact label="Fleet">
            {summary.data.aircraft} ships · {summary.data.flights} legs
          </Fact>
          <Fact label="Model">{summary.data.model.version}</Fact>
          <div className="ml-auto flex items-baseline gap-4" aria-label="Planning status counts">
            {(["critical", "review", "ok"] as const).map((s) => (
              <Link
                key={s}
                href={`/engines?status=${s}${bufferParam !== undefined ? `&buffer=${bufferParam}` : ""}`}
                className="hover:text-fg flex items-baseline gap-1.5"
              >
                <span className="font-mono text-sm">{summary.data.status_counts[s]}</span>
                <StatusBadge status={s} />
              </Link>
            ))}
          </div>
        </dl>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Section
          title="Schedule exposure"
          aside={<span className="text-fg-subtle text-2xs">cycles · sorted by L − n</span>}
        >
          {engines.isError ? (
            <QueryError error={engines.error} onRetry={() => void engines.refetch()} />
          ) : !engines.data ? (
            <Loading label="engines" className="h-96" />
          ) : (
            <CycleExposure
              engines={engines.data.items}
              buffer={buffer}
              hrefFor={(id) => q(`/engines/${id}`)}
            />
          )}
        </Section>

        <div className="flex flex-col gap-6">
          <Section title="Requires review">
            {!engines.data ? (
              <Loading label="flagged engines" className="h-32" />
            ) : engines.data.items.filter((e) => e.planning.status !== "ok").length === 0 ? (
              <Empty>No engines below the buffer</Empty>
            ) : (
              <table className="w-full text-xs">
                <thead className="text-fg-subtle text-left">
                  <tr>
                    <th className="pb-1 font-normal">Engine</th>
                    <th className="pb-1 font-normal">Status</th>
                    <th className="pb-1 text-right font-normal">First flagged</th>
                  </tr>
                </thead>
                <tbody>
                  {engines.data.items
                    .filter((e) => e.planning.status !== "ok")
                    .map((e) => (
                      <tr key={e.id} className="border-line border-t">
                        <td className="py-1.5">
                          <Link
                            href={q(`/engines/${e.id}`)}
                            className="text-accent font-mono hover:underline"
                          >
                            {e.id}
                          </Link>
                        </td>
                        <td>
                          <StatusBadge status={e.planning.status} />
                        </td>
                        <td className="text-fg-muted text-right font-mono">
                          {e.planning.first_flagged_departure
                            ? utcTime(e.planning.first_flagged_departure)
                            : "now"}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </Section>

          <Section
            title="Next maintenance"
            aside={
              <Link href={q("/maintenance")} className="text-fg-subtle hover:text-fg text-2xs">
                Calendar
              </Link>
            }
          >
            {mx.isError ? (
              <QueryError error={mx.error} onRetry={() => void mx.refetch()} />
            ) : !mx.data ? (
              <Loading label="maintenance" className="h-24" />
            ) : mx.data.placements.length === 0 && mx.data.unscheduled.length === 0 ? (
              <Empty>No job cards</Empty>
            ) : (
              <ul className="flex flex-col text-xs">
                {mx.data.placements.slice(0, 6).map((p) => (
                  <li
                    key={p.job_id}
                    className="border-line flex items-baseline justify-between gap-2 border-t py-1.5"
                  >
                    <Link
                      href={q(`/maintenance?job=${p.job_id}`)}
                      className="text-accent font-mono hover:underline"
                    >
                      {p.engine_id ?? p.aircraft_id}
                    </Link>
                    <span className="text-fg-muted">
                      {JOB_TYPE_LABEL[p.job_type]} · {p.bay}
                    </span>
                    <span className="font-mono">{utcTime(p.start)}</span>
                  </li>
                ))}
                {mx.data.unscheduled.map((u) => (
                  <li
                    key={u.job_id}
                    className="border-line flex items-baseline justify-between gap-2 border-t py-1.5"
                  >
                    <span className="font-mono">{u.engine_id ?? u.aircraft_id}</span>
                    <span className="text-warn">Not placed</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Flagged departures · first 24 h">
            {flagged.isError ? (
              <QueryError error={flagged.error} onRetry={() => void flagged.refetch()} />
            ) : !flagged.data ? (
              <Loading label="flagged departures" className="h-32" />
            ) : flagged.data.items.length === 0 ? (
              <Empty>None</Empty>
            ) : (
              <ul className="flex flex-col text-xs">
                {flagged.data.items.map((f) => (
                  <li
                    key={f.id}
                    className="border-line flex items-baseline justify-between gap-2 border-t py-1.5"
                  >
                    <Link
                      href={q(`/flights?aircraft=${f.aircraft_id}&flight=${f.id}`)}
                      className="text-accent font-mono hover:underline"
                    >
                      {f.flight_number}
                    </Link>
                    <span className="text-fg-muted">
                      {f.origin}–{f.destination}
                    </span>
                    <span className="font-mono">
                      {localTime(f.departure_local, f.origin_tz, f.origin_tz_abbr)}
                    </span>
                  </li>
                ))}
                {flagged.data.total > flagged.data.items.length ? (
                  <li className="pt-1.5">
                    <Link href={q("/flights?flagged=1")} className="text-fg-subtle hover:text-fg">
                      {flagged.data.total - flagged.data.items.length} more
                    </Link>
                  </li>
                ) : null}
              </ul>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-fg-subtle">{label}</dt>
      <dd className="font-mono">{children}</dd>
    </div>
  );
}
