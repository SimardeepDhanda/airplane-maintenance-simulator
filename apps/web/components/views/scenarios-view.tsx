"use client";

import Link from "next/link";
import { useState } from "react";
import { BufferControl } from "@/components/controls/buffer-control";
import { Segmented } from "@/components/controls/segmented";
import { Select } from "@/components/controls/select";
import { Empty, Loading, QueryError } from "@/components/feedback/query-state";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";
import { ApiError } from "@/lib/api/client";
import {
  useEngines,
  useMaintenanceResources,
  useRunScenario,
  useScenario,
  useScenarios,
} from "@/lib/api/queries";
import type { Assumptions, JobType, Plan, Scenario } from "@/lib/api/schemas";
import { JOB_TYPE_LABEL, integer, utcTime } from "@/lib/format";
import { useUrlState } from "@/lib/use-url-state";
import { PlanStatus } from "./plan-status";

const DEFAULTS: Assumptions = {
  buffer: 10,
  threshold_policy: "penalty",
  bay_changes: {},
  part_delay_hours: 0,
  grounded_aircraft: [],
  added_jobs: [],
  time_limit_s: 10,
};

const PRESETS: { label: string; assumptions: Partial<Assumptions> }[] = [
  { label: "Default week", assumptions: {} },
  { label: "Inbound spare +24 h", assumptions: { part_delay_hours: 24 } },
  { label: "DEN bay out", assumptions: { bay_changes: { DEN: -1 } } },
  {
    label: "Hard threshold, DEN bay out",
    assumptions: { threshold_policy: "hard", bay_changes: { DEN: -1 } },
  },
];

const POLICIES = [
  { value: "penalty", label: "Penalty" },
  { value: "hard", label: "Hard" },
] as const;

export function ScenariosView() {
  const { params, set } = useUrlState();
  const id = params.get("id") ? Number(params.get("id")) : undefined;
  const scenario = useScenario(id);
  const scenarios = useScenarios();
  const [draft, setDraft] = useState<Assumptions>(DEFAULTS);
  const [name, setName] = useState("");
  const run = useRunScenario();

  const submit = () =>
    run.mutate(
      { assumptions: draft, ...(name.trim() ? { name: name.trim() } : {}) },
      { onSuccess: (newId) => set({ id: newId }) },
    );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Scenarios" />
      <div className="grid gap-6 lg:grid-cols-[19rem_minmax(0,1fr)]">
        <Section title="Assumptions">
          <AssumptionForm
            draft={draft}
            onChange={setDraft}
            name={name}
            onName={setName}
            onSubmit={submit}
            pending={run.isPending}
            error={run.error}
          />
        </Section>
        <div className="flex min-w-0 flex-col gap-6">
          {id === undefined ? (
            <Empty>Run a scenario or pick one below</Empty>
          ) : scenario.isError ? (
            <QueryError error={scenario.error} onRetry={() => void scenario.refetch()} />
          ) : !scenario.data ? (
            <Loading label="scenario" className="h-64" />
          ) : (
            <Result
              s={scenario.data}
              onEdit={() => {
                setDraft(scenario.data.assumptions);
                setName("");
              }}
            />
          )}
          <Section title="Recent">
            {scenarios.data?.length ? (
              <div className="relative overflow-x-auto">
                <table className="w-full min-w-[520px] text-xs">
                  <thead className="text-fg-subtle">
                    <tr className="border-line-strong border-b text-left">
                      <th scope="col" className="px-2 py-1.5 font-normal">
                        #
                      </th>
                      <th scope="col" className="px-2 py-1.5 font-normal">
                        Scenario
                      </th>
                      <th scope="col" className="px-2 py-1.5 font-normal">
                        Baseline
                      </th>
                      <th scope="col" className="px-2 py-1.5 font-normal">
                        Optimized
                      </th>
                      <th scope="col" className="px-2 py-1.5 font-normal">
                        Created
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarios.data.map((s) => (
                      <tr
                        key={s.id}
                        className={`border-line border-b ${s.id === id ? "bg-accent-muted" : ""}`}
                      >
                        <td className="px-2 py-1 font-mono">
                          <Link href={`/scenarios?id=${s.id}`} className="text-accent">
                            {s.id}
                          </Link>
                        </td>
                        <td className="px-2 py-1">{s.name}</td>
                        <td className="px-2 py-1 font-mono">{s.baseline_status ?? s.status}</td>
                        <td className="px-2 py-1 font-mono">{s.optimized_status ?? s.status}</td>
                        <td className="text-fg-subtle px-2 py-1 font-mono">
                          {utcTime(s.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : scenarios.isError ? (
              <QueryError error={scenarios.error} onRetry={() => void scenarios.refetch()} />
            ) : (
              <p className="text-fg-subtle text-xs">None yet</p>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

function AssumptionForm({
  draft,
  onChange,
  name,
  onName,
  onSubmit,
  pending,
  error,
}: {
  draft: Assumptions;
  onChange: (a: Assumptions) => void;
  name: string;
  onName: (v: string) => void;
  onSubmit: () => void;
  pending: boolean;
  error: Error | null;
}) {
  const resources = useMaintenanceResources();
  const engines = useEngines({ page_size: 100, sort: "id" });
  const ships = (engines.data?.items ?? [])
    .map((e) => e.aircraft_id)
    .filter((s): s is string => s !== null);
  const patch = (p: Partial<Assumptions>) => onChange({ ...draft, ...p });
  const added = draft.added_jobs[0];

  return (
    <form
      className="flex flex-col gap-3 text-xs"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Presets">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => onChange({ ...DEFAULTS, ...p.assumptions })}
            className="border-line-strong text-fg-muted hover:text-fg rounded-sm border px-2 py-0.5"
          >
            {p.label}
          </button>
        ))}
      </div>

      <BufferControl
        label="Planning buffer"
        className="justify-between"
        value={draft.buffer}
        onChange={(v) => patch({ buffer: v })}
      />
      <Row label="Threshold">
        <Segmented
          label="Threshold policy"
          value={draft.threshold_policy}
          options={POLICIES}
          onChange={(v) => patch({ threshold_policy: v })}
        />
      </Row>
      {(resources.data?.facilities ?? []).map((f) => {
        const delta = draft.bay_changes[f.code] ?? 0;
        const count = f.bays.length + delta;
        const change = (d: number) => {
          const next = { ...draft.bay_changes, [f.code]: delta + d };
          if (next[f.code] === 0) delete next[f.code];
          patch({ bay_changes: next });
        };
        return (
          <Row key={f.code} label={`${f.code} bays`}>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label={`Remove ${f.code} bay`}
                disabled={count <= 0}
                onClick={() => change(-1)}
                className="border-line-strong hover:bg-raised size-6 rounded-sm border disabled:opacity-40"
              >
                −
              </button>
              <span
                className={`w-6 text-center font-mono ${delta ? "text-accent" : ""}`}
                aria-live="polite"
              >
                {count}
              </span>
              <button
                type="button"
                aria-label={`Add ${f.code} bay`}
                disabled={delta >= 3}
                onClick={() => change(1)}
                className="border-line-strong hover:bg-raised size-6 rounded-sm border disabled:opacity-40"
              >
                +
              </button>
            </div>
          </Row>
        );
      })}
      <Row label="Inbound spare delay">
        <Select
          label="Inbound spare delay"
          hideLabel
          value={String(draft.part_delay_hours)}
          allLabel="None"
          options={[12, 24, 48, 72].map((h) => ({ value: String(h), label: `${h} h` }))}
          onChange={(v) => patch({ part_delay_hours: v ? Number(v) : 0 })}
        />
      </Row>
      <Row label="Ground ship">
        <Select
          label="Ground ship"
          hideLabel
          value={draft.grounded_aircraft[0] ?? ""}
          allLabel="None"
          options={ships.map((s) => ({ value: s, label: s }))}
          onChange={(v) => patch({ grounded_aircraft: v ? [v] : [] })}
        />
      </Row>
      <Row label="Add job">
        <div className="flex gap-1.5">
          <Select
            label="Add job: ship"
            hideLabel
            value={added?.aircraft_id ?? ""}
            allLabel="None"
            options={ships.map((s) => ({ value: s, label: s }))}
            onChange={(v) =>
              patch({
                added_jobs: v ? [{ aircraft_id: v, job_type: added?.job_type ?? "borescope" }] : [],
              })
            }
          />
          {added ? (
            <Select
              label="Add job: type"
              hideLabel
              value={added.job_type}
              allLabel="Borescope"
              options={[{ value: "engine_change", label: "Engine change" }]}
              onChange={(v) =>
                patch({
                  added_jobs: [
                    { aircraft_id: added.aircraft_id, job_type: (v || "borescope") as JobType },
                  ],
                })
              }
            />
          ) : null}
        </div>
      </Row>
      <Row label="Time limit">
        <Select
          label="Time limit"
          hideLabel
          value={String(draft.time_limit_s)}
          allLabel="10 s"
          options={[2, 5, 30].map((t) => ({ value: String(t), label: `${t} s` }))}
          onChange={(v) => patch({ time_limit_s: v ? Number(v) : 10 })}
        />
      </Row>
      <label className="text-fg-muted flex items-center justify-between gap-2">
        Name
        <input
          value={name}
          onChange={(e) => onName(e.target.value)}
          maxLength={80}
          placeholder="auto"
          className="border-line-strong bg-surface text-fg w-40 rounded-sm border px-2 py-1"
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="bg-accent text-canvas rounded-sm px-3 py-1.5 font-medium disabled:opacity-60"
      >
        {pending ? "Starting…" : "Run scenario"}
      </button>
      {error ? (
        <p role="alert" className="text-crit">
          {error instanceof ApiError ? `${error.message} (${error.code})` : "Request failed"}
        </p>
      ) : null}
    </form>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-fg-muted">{label}</span>
      {children}
    </div>
  );
}

// Count units (jobs, legs, moves) are implied by the label.
const SHOWN_UNITS = new Set(["cyc", "h", "%", "units", "ms"]);

function fmt(value: number | null, unit: string): string {
  if (value === null) return "—";
  if (unit === "%") return `${value.toFixed(1)}%`;
  return integer(value);
}

function Result({ s, onEdit }: { s: Scenario; onEdit: () => void }) {
  const solving = s.status === "queued" || s.status === "running";
  return (
    <Section
      title={`#${s.id} ${s.name}`}
      aside={
        <button type="button" onClick={onEdit} className="text-fg-subtle hover:text-fg text-2xs">
          Edit as new
        </button>
      }
    >
      {solving ? (
        <Loading label="solver" className="h-48" />
      ) : s.status === "failed" ? (
        <p role="alert" className="border-crit/40 rounded-sm border px-3 py-2 text-xs">
          Solve failed: {s.error}
        </p>
      ) : s.status === "created" ? (
        <Empty>Not solved</Empty>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
            {([s.baseline, s.optimized] as const).map((p, i) =>
              p ? (
                <div key={p.method} className="flex flex-wrap items-baseline gap-2">
                  <span className="text-fg-subtle w-20">{i === 0 ? "Baseline" : "Optimized"}</span>
                  <PlanStatus plan={p} />
                  {p.placements.length ? (
                    <Link
                      href={`/maintenance?scenario=${s.id}${p.method === "baseline" ? "&method=baseline" : ""}`}
                      className="text-accent"
                    >
                      Calendar
                    </Link>
                  ) : null}
                </div>
              ) : null,
            )}
          </div>

          <Explanations plans={[s.baseline, s.optimized]} />

          {s.baseline?.metrics || s.optimized?.metrics ? (
            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[480px] text-xs" aria-label="Baseline vs optimized">
                <thead className="text-fg-subtle">
                  <tr className="border-line-strong border-b text-left">
                    <th scope="col" className="px-2 py-1.5 font-normal">
                      Metric
                    </th>
                    <th scope="col" className="px-2 py-1.5 text-right font-normal">
                      Baseline
                    </th>
                    <th scope="col" className="px-2 py-1.5 text-right font-normal">
                      Optimized
                    </th>
                    <th scope="col" className="px-2 py-1.5 text-right font-normal">
                      Change
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {s.comparison.map((r) => {
                    const improved =
                      r.delta !== null &&
                      r.delta !== 0 &&
                      r.better !== null &&
                      (r.better === "lower" ? r.delta < 0 : r.delta > 0);
                    const worse =
                      r.delta !== null && r.delta !== 0 && r.better !== null && !improved;
                    return (
                      <tr key={r.key} className="border-line border-b">
                        <td className="px-2 py-1">
                          {r.label}
                          {SHOWN_UNITS.has(r.unit) ? (
                            <span className="text-fg-subtle"> {r.unit}</span>
                          ) : null}
                        </td>
                        <td className="px-2 py-1 text-right font-mono">
                          {fmt(r.baseline, r.unit)}
                        </td>
                        <td className="px-2 py-1 text-right font-mono">
                          {fmt(r.optimized, r.unit)}
                        </td>
                        <td
                          className={`px-2 py-1 text-right font-mono ${improved ? "text-ok" : worse ? "text-warn" : "text-fg-subtle"}`}
                        >
                          {r.delta === null
                            ? "—"
                            : r.delta === 0
                              ? "0"
                              : `${r.delta > 0 ? "+" : "−"}${fmt(Math.abs(r.delta), r.unit)}${
                                  r.pct_change !== null && r.unit !== "%" && r.better !== null
                                    ? ` (${r.pct_change > 0 ? "+" : "−"}${Math.abs(r.pct_change * 100).toFixed(0)}%)`
                                    : ""
                                }`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {s.baseline?.costs && s.optimized?.costs ? (
            <CostTable baseline={s.baseline} optimized={s.optimized} />
          ) : null}
          {s.baseline?.placements.length || s.optimized?.placements.length ? (
            <PlacementDiff baseline={s.baseline} optimized={s.optimized} />
          ) : null}
        </div>
      )}
    </Section>
  );
}

function Explanations({ plans }: { plans: (Plan | null)[] }) {
  const items = plans.flatMap((p) =>
    p ? p.explanations.map((e) => ({ method: p.method, ...e })) : [],
  );
  if (!items.length) return null;
  return (
    <div role="alert" className="border-warn/50 rounded-sm border px-3 py-2 text-xs">
      <ul className="flex flex-col gap-1.5">
        {items.map((e, i) => (
          <li key={i}>
            <span className="text-fg-subtle mr-2">
              {e.method === "baseline" ? "Baseline" : "Optimizer"}
            </span>
            {e.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

const COSTS = [
  ["cancellations", "Cancelled legs"],
  ["threshold", "Past threshold"],
  ["unscheduled", "Unplaced jobs"],
  ["labor", "Labour"],
  ["transfers", "Part moves"],
] as const;

function CostTable({ baseline, optimized }: { baseline: Plan; optimized: Plan }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[480px] text-xs" aria-label="Cost components">
        <thead className="text-fg-subtle">
          <tr className="border-line-strong border-b text-left">
            <th scope="col" className="px-2 py-1.5 font-normal">
              Cost component <span className="text-fg-subtle">units</span>
            </th>
            {COSTS.map(([, label]) => (
              <th key={label} scope="col" className="px-2 py-1.5 text-right font-normal">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[baseline, optimized].map((p) => (
            <tr key={p.method} className="border-line border-b">
              <td className="px-2 py-1">{p.method === "baseline" ? "Baseline" : "Optimized"}</td>
              {COSTS.map(([key]) => (
                <td key={key} className="px-2 py-1 text-right font-mono">
                  {p.costs ? integer(p.costs[key]) : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PlacementDiff({ baseline, optimized }: { baseline: Plan | null; optimized: Plan | null }) {
  const jobs = optimized?.jobs ?? baseline?.jobs ?? [];
  if (!jobs.length) return null;
  const at = (p: Plan | null, jobId: string) => {
    const pl = p?.placements.find((x) => x.job_id === jobId);
    if (pl)
      return {
        text: `${pl.bay} ${utcTime(pl.start)}`,
        extra: `${pl.cancelled_flights.length} legs${pl.cycles_over ? ` · +${pl.cycles_over} cyc` : ""}`,
      };
    if (p?.unscheduled.some((u) => u.job_id === jobId)) return { text: "Not placed", extra: "" };
    return { text: "—", extra: "" };
  };
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[560px] text-xs" aria-label="Job placements">
        <thead className="text-fg-subtle">
          <tr className="border-line-strong border-b text-left">
            <th scope="col" className="px-2 py-1.5 font-normal">
              Job
            </th>
            <th scope="col" className="px-2 py-1.5 font-normal">
              Baseline
            </th>
            <th scope="col" className="px-2 py-1.5 font-normal">
              Optimized
            </th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => {
            const b = at(baseline, j.id);
            const o = at(optimized, j.id);
            const changed = b.text !== o.text;
            return (
              <tr key={j.id} className="border-line border-b">
                <td className="px-2 py-1">
                  <span className="font-mono">{j.engine_id ?? j.aircraft_id}</span>{" "}
                  <span className="text-fg-subtle">{JOB_TYPE_LABEL[j.job_type]}</span>
                </td>
                <td className="px-2 py-1 font-mono">
                  {b.text} <span className="text-fg-subtle">{b.extra}</span>
                </td>
                <td className={`px-2 py-1 font-mono ${changed ? "text-accent" : ""}`}>
                  {o.text} <span className="text-fg-subtle">{o.extra}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
