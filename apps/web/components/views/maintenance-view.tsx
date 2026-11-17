"use client";

import Link from "next/link";
import { MaintenanceGantt } from "@/components/charts/maintenance-gantt";
import { BufferControl } from "@/components/controls/buffer-control";
import { Segmented } from "@/components/controls/segmented";
import { Select } from "@/components/controls/select";
import { Empty, Loading, QueryError } from "@/components/feedback/query-state";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";
import {
  useFleetSummary,
  useMaintenancePlan,
  useMaintenanceResources,
  useScenario,
  useScenarios,
} from "@/lib/api/queries";
import type { MaintenanceResources, Plan } from "@/lib/api/schemas";
import { JOB_TYPE_LABEL, integer, utcTime, zonedTime } from "@/lib/format";
import { parseBuffer, useUrlState } from "@/lib/use-url-state";
import { PlanStatus } from "./plan-status";

const METHODS = [
  { value: "baseline", label: "Baseline" },
  { value: "optimized", label: "Optimized" },
] as const;

export function MaintenanceView() {
  const { params, set } = useUrlState();
  const bufferParam = parseBuffer(params.get("buffer"));
  const scenarioId = params.get("scenario") ? Number(params.get("scenario")) : undefined;
  const method = params.get("method") === "baseline" ? "baseline" : "optimized";
  const selectedJob = params.get("job");

  const resources = useMaintenanceResources();
  const current = useMaintenancePlan(bufferParam, scenarioId === undefined);
  const scenario = useScenario(scenarioId);
  const scenarios = useScenarios();
  const summary = useFleetSummary(bufferParam);

  const plan: Plan | null | undefined =
    scenarioId === undefined ? current.data : scenario.data ? scenario.data[method] : undefined;
  const error = scenarioId === undefined ? current.error : scenario.error;
  const refetch = () => void (scenarioId === undefined ? current.refetch() : scenario.refetch());
  const solving = scenario.data && ["queued", "running"].includes(scenario.data.status);

  const sources = [
    ...(scenarios.data ?? [])
      .filter((s) => s.status === "solved")
      .map((s) => ({ value: String(s.id), label: `#${s.id} ${s.name}` })),
  ];
  if (scenarioId !== undefined && !sources.some((s) => s.value === String(scenarioId))) {
    sources.unshift({ value: String(scenarioId), label: `#${scenarioId}` });
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Maintenance planning"
        actions={
          scenarioId === undefined ? (
            <BufferControl
              value={bufferParam ?? summary.data?.planning_buffer ?? 10}
              onChange={(v) => set({ buffer: v })}
            />
          ) : null
        }
      />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Select
          label="Plan"
          value={scenarioId !== undefined ? String(scenarioId) : ""}
          allLabel="Open job cards · baseline"
          options={sources}
          onChange={(v) => set({ scenario: v || null, job: null, method: null })}
        />
        {scenarioId !== undefined ? (
          <Segmented
            label="Method"
            value={method}
            options={METHODS}
            onChange={(v) => set({ method: v === "optimized" ? null : v, job: null })}
          />
        ) : null}
        {scenarioId !== undefined ? (
          <Link
            href={`/scenarios?id=${scenarioId}`}
            className="text-fg-subtle hover:text-fg text-xs"
          >
            Scenario #{scenarioId}
          </Link>
        ) : null}
      </div>

      {error ? (
        <QueryError error={error} onRetry={refetch} />
      ) : !resources.data || plan === undefined || solving ? (
        <Loading label={solving ? "solver" : "maintenance plan"} className="h-80" />
      ) : plan === null ? (
        <Empty>Not solved yet</Empty>
      ) : (
        <PlanBody
          plan={plan}
          resources={resources.data}
          selectedJob={selectedJob}
          onSelect={(id) => set({ job: id === selectedJob ? null : id })}
          bufferParam={bufferParam}
        />
      )}

      {resources.data ? <ResourceTables resources={resources.data} /> : null}
    </div>
  );
}

function PlanBody({
  plan,
  resources,
  selectedJob,
  onSelect,
  bufferParam,
}: {
  plan: Plan;
  resources: MaintenanceResources;
  selectedJob: string | null;
  onSelect: (jobId: string) => void;
  bufferParam: number | undefined;
}) {
  const tz = Object.fromEntries(resources.facilities.map((f) => [f.code, f.timezone]));
  const selected = plan.placements.find((p) => p.job_id === selectedJob) ?? null;
  const q = bufferParam !== undefined ? `?buffer=${bufferParam}` : "";
  const m = plan.metrics;

  return (
    <>
      <dl className="border-line flex flex-wrap gap-x-6 gap-y-2 border-y py-2 text-xs">
        <Stat label="Solver">
          <PlanStatus plan={plan} />
        </Stat>
        {m ? (
          <>
            <Stat label="Jobs placed">
              {m.jobs_scheduled}/{m.jobs_total}
            </Stat>
            <Stat label="Thresholds missed">{m.thresholds_missed}</Stat>
            <Stat label="Cancelled legs">{m.cancelled_legs}</Stat>
            <Stat label="Cost">{plan.costs ? integer(plan.costs.total) : "—"}</Stat>
          </>
        ) : null}
      </dl>

      {plan.explanations.length ? (
        <div role="alert" className="border-warn/50 rounded-sm border px-3 py-2 text-xs">
          <p className="text-fg mb-1 font-medium">
            {plan.status === "INFEASIBLE" ? "No feasible plan" : "No plan found"}
          </p>
          <ul className="text-fg-muted flex flex-col gap-1">
            {plan.explanations.map((e, i) => (
              <li key={i}>
                <span className="text-fg-subtle mr-2 font-mono">{e.code}</span>
                {e.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {plan.placements.length ? (
        <Section title="Calendar">
          <MaintenanceGantt
            facilities={resources.facilities}
            placements={plan.placements}
            start={resources.horizon_start}
            end={resources.horizon_end}
            selectedId={selectedJob}
            onSelect={onSelect}
          />
        </Section>
      ) : plan.jobs.length === 0 ? (
        <Empty>No open job cards at this buffer</Empty>
      ) : null}

      {plan.jobs.length ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <Section title="Jobs">
            <div className="relative overflow-x-auto" tabIndex={0}>
              <table className="w-full min-w-[720px] text-xs">
                <thead className="text-fg-subtle">
                  <tr className="border-line-strong border-b text-left">
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Engine
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Job
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Bay
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Start
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      End
                    </th>
                    <th scope="col" className="px-2 py-1.5 text-right font-normal">
                      Cancels
                    </th>
                    <th scope="col" className="px-2 py-1.5 text-right font-normal">
                      Past thr.
                    </th>
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Spare
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {plan.placements.map((p) => {
                    const on = p.job_id === selectedJob;
                    return (
                      <tr
                        key={p.job_id}
                        aria-selected={on}
                        className={`border-line border-b ${on ? "bg-accent-muted" : ""}`}
                      >
                        <td className="px-2 py-1 font-mono">
                          <button
                            type="button"
                            aria-pressed={on}
                            aria-label={`Select ${p.job_id}`}
                            onClick={() => onSelect(p.job_id)}
                            className="hover:text-fg text-accent"
                          >
                            {p.engine_id ?? p.aircraft_id}
                          </button>
                        </td>
                        <td className="px-2 py-1">{JOB_TYPE_LABEL[p.job_type]}</td>
                        <td className="px-2 py-1 font-mono">{p.bay}</td>
                        <td className="px-2 py-1 font-mono whitespace-nowrap">
                          {zonedTime(p.start, tz[p.facility] ?? "UTC")}
                        </td>
                        <td className="px-2 py-1 font-mono whitespace-nowrap">
                          {zonedTime(p.end, tz[p.facility] ?? "UTC")}
                        </td>
                        <td className="px-2 py-1 text-right font-mono">
                          {p.cancelled_flights.length}
                        </td>
                        <td
                          className={`px-2 py-1 text-right font-mono ${p.cycles_over ? "text-warn" : ""}`}
                        >
                          {p.cycles_over}
                        </td>
                        <td className="px-2 py-1 font-mono">
                          {p.part_from
                            ? p.part_from === p.facility
                              ? p.part_from
                              : `${p.part_from}→${p.facility}`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {plan.unscheduled.map((u) => (
                    <tr key={u.job_id} className="border-line text-fg-muted border-b">
                      <td className="px-2 py-1 font-mono">{u.engine_id ?? u.aircraft_id}</td>
                      <td className="px-2 py-1">{JOB_TYPE_LABEL[u.job_type]}</td>
                      <td className="text-warn px-2 py-1" colSpan={4}>
                        Not placed: {u.why}
                      </td>
                      <td className="px-2 py-1 text-right font-mono">{u.cycles_over}</td>
                      <td className="px-2 py-1">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section title={selected ? (selected.engine_id ?? selected.job_id) : "Placement"}>
            {selected ? (
              <div className="flex flex-col gap-3 text-xs">
                <p className="text-fg-muted">
                  {JOB_TYPE_LABEL[selected.job_type]} · ship {selected.aircraft_id} · {selected.bay}{" "}
                  · {utcTime(selected.start)}–{utcTime(selected.end)} · {selected.labor_hours}{" "}
                  tech-h
                </p>
                <ul className="flex list-disc flex-col gap-1 pl-4">
                  {selected.why.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
                {selected.cancelled_flights.length ? (
                  <div>
                    <p className="text-fg-subtle mb-1">Cancelled legs</p>
                    <div className="flex flex-wrap gap-1.5 font-mono">
                      {selected.cancelled_flights.map((id) => (
                        <Link
                          key={id}
                          href={`/flights?aircraft=${selected.aircraft_id}&flight=${id}`}
                          className="text-accent hover:underline"
                        >
                          {id.split("-")[0]}
                          <span className="text-fg-subtle">/{id.slice(-2)}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                ) : null}
                {selected.engine_id ? (
                  <Link
                    href={`/engines/${selected.engine_id}${q}`}
                    className="text-fg-subtle hover:text-fg"
                  >
                    Engine detail
                  </Link>
                ) : null}
              </div>
            ) : (
              <p className="text-fg-subtle text-xs">Select a job</p>
            )}
          </Section>
        </div>
      ) : null}
    </>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2">
      <dt className="text-fg-subtle">{label}</dt>
      <dd className="font-mono">{children}</dd>
    </div>
  );
}

function ResourceTables({ resources }: { resources: MaintenanceResources }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Section title="Facilities">
        <div className="relative overflow-x-auto" tabIndex={0}>
          <table className="w-full text-xs">
            <thead className="text-fg-subtle">
              <tr className="border-line-strong border-b text-left">
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Station
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  Bays
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Work
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Technicians (local)
                </th>
              </tr>
            </thead>
            <tbody>
              {resources.facilities.map((f) => (
                <tr key={f.code} className="border-line border-b">
                  <td className="px-2 py-1 font-mono">
                    {f.code} <span className="text-fg-subtle font-sans">{f.kind}</span>
                  </td>
                  <td className="px-2 py-1 text-right font-mono">{f.bays.length}</td>
                  <td className="px-2 py-1">
                    {f.supports.map((s) => JOB_TYPE_LABEL[s]).join(", ")}
                  </td>
                  <td className="px-2 py-1 font-mono whitespace-nowrap">
                    {f.shifts
                      .map(
                        (s) =>
                          `${s.start_local.slice(0, 5)}–${s.end_local.slice(0, 5)} ${s.technicians}`,
                      )
                      .join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section title="Spare engines">
        <div className="relative overflow-x-auto" tabIndex={0}>
          <table className="w-full text-xs">
            <thead className="text-fg-subtle">
              <tr className="border-line-strong border-b text-left">
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Lot
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  At
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  Qty
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Available
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  Transfer
                </th>
              </tr>
            </thead>
            <tbody>
              {resources.parts.map((p) => (
                <tr key={p.id} className="border-line border-b">
                  <td className="px-2 py-1 font-mono">{p.id}</td>
                  <td className="px-2 py-1 font-mono">{p.location}</td>
                  <td className="px-2 py-1 text-right font-mono">{p.quantity}</td>
                  <td className="px-2 py-1 font-mono">{utcTime(p.available_at)}</td>
                  <td className="px-2 py-1 text-right font-mono">{p.transfer_lead_hours} h</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
