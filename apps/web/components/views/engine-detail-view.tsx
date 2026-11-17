"use client";

import Link from "next/link";
import { useState } from "react";
import { BufferControl } from "@/components/controls/buffer-control";
import { HBars } from "@/components/charts/hbars";
import { RulChart } from "@/components/charts/rul-chart";
import { SensorMultiples } from "@/components/charts/sensor-multiples";
import { Loading, QueryError } from "@/components/feedback/query-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Section } from "@/components/layout/section";
import {
  useEngine,
  useEngineHistory,
  useMaintenancePlan,
  useModelMetrics,
} from "@/lib/api/queries";
import {
  JOB_TYPE_LABEL,
  cycles,
  localTime,
  sensorLabel,
  signedCycles,
  utcTime,
} from "@/lib/format";
import type { Plan } from "@/lib/api/schemas";
import { parseBuffer, useUrlState } from "@/lib/use-url-state";

const DEFAULT_SENSORS = 4;

export function EngineDetailView({ id }: { id: string }) {
  const { params, set } = useUrlState();
  const bufferParam = parseBuffer(params.get("buffer"));
  const engine = useEngine(id, bufferParam);
  const history = useEngineHistory(id);
  const metrics = useModelMetrics();
  const mx = useMaintenancePlan(bufferParam);
  const [chosen, setChosen] = useState<string[] | null>(null);

  if (engine.isError) {
    return <QueryError error={engine.error} onRetry={() => void engine.refetch()} />;
  }
  if (!engine.data) return <Loading label="engine" className="h-[32rem]" />;

  const e = engine.data;
  const p = e.prediction;
  const kept = metrics.data?.features.sensors ?? [];
  const ranked = (metrics.data?.permutation_importance.features ?? [])
    .map((f) => f.feature.split("_").slice(0, 2).join("_"))
    .filter((s, i, all) => s.startsWith("sensor_") && all.indexOf(s) === i);
  const sensors = chosen ?? ranked.slice(0, DEFAULT_SENSORS);
  const toggle = (s: string) =>
    setChosen((cur) => {
      const base = cur ?? sensors;
      return base.includes(s) ? base.filter((x) => x !== s) : [...base, s];
    });
  const firstFlagged = e.planning.first_flagged_flight_id;
  const q = bufferParam !== undefined ? `&buffer=${bufferParam}` : "";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <Link
            href={`/engines${bufferParam !== undefined ? `?buffer=${bufferParam}` : ""}`}
            className="text-fg-subtle hover:text-fg text-xs"
          >
            Engines /
          </Link>
          <h1 className="font-mono text-base font-semibold">{e.id}</h1>
          <span className="text-fg-muted text-xs">
            Ship {e.aircraft_id ?? "—"} · {e.fleet_type} · {e.station}
          </span>
          <StatusBadge status={e.planning.status} />
        </div>
        <BufferControl value={e.planning.buffer} onChange={(v) => set({ buffer: v })} />
      </div>

      <dl className="border-line grid grid-cols-2 gap-x-6 gap-y-2 border-y py-2 text-xs sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="RUL estimate" value={`${cycles(p.rul_point)} cyc`} />
        <Metric label="90% interval" value={`${cycles(p.rul_lower)}–${cycles(p.rul_upper)}`} />
        <Metric label="Observed cycles" value={String(e.observed_cycles)} />
        <Metric label="Scheduled (7 d)" value={`${e.planning.forecast_cycles} cyc`} />
        <Metric label="R − n" value={signedCycles(e.planning.margin)} />
        <Metric label="L − n" value={signedCycles(e.planning.conservative_margin)} strong />
      </dl>
      <MaintenanceLine plan={mx.data} engineId={e.id} bufferParam={bufferParam} />

      <Section
        title="Cycles remaining"
        aside={<span className="text-fg-subtle text-2xs">{p.model_version}</span>}
      >
        {history.isError ? (
          <QueryError error={history.error} onRetry={() => void history.refetch()} />
        ) : !history.data ? (
          <Loading label="prediction history" className="h-64" />
        ) : (
          <RulChart
            history={history.data}
            flights={e.flights}
            rulPoint={p.rul_point}
            rulLower={p.rul_lower}
            buffer={e.planning.buffer}
          />
        )}
      </Section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Section
          title="Sensor history"
          aside={<span className="text-fg-subtle text-2xs">NASA C-MAPSS, raw</span>}
        >
          <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label="Sensors shown">
            {kept.map((s) => {
              const on = sensors.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(s)}
                  className={`text-2xs rounded-sm border px-1.5 py-0.5 font-mono ${
                    on
                      ? "border-accent text-fg bg-accent-muted"
                      : "border-line-strong text-fg-subtle hover:text-fg"
                  }`}
                >
                  {sensorLabel(s)}
                </button>
              );
            })}
          </div>
          {history.data ? (
            sensors.length ? (
              <SensorMultiples history={history.data} sensors={sensors} />
            ) : (
              <p className="text-fg-subtle text-xs">Select a sensor</p>
            )
          ) : (
            <Loading label="sensors" className="h-48" />
          )}
        </Section>

        <div className="flex flex-col gap-6">
          <Section
            title="Model influence"
            aside={<span className="text-fg-subtle text-2xs">all engines</span>}
          >
            {metrics.data ? (
              <HBars
                label="Permutation importance"
                rows={metrics.data.permutation_importance.features.slice(0, 8).map((f) => ({
                  key: f.feature,
                  label: f.feature.replace("sensor_", "S"),
                  value: f.mean,
                  note: `RMSE +${f.mean.toFixed(2)} when shuffled`,
                }))}
                format={(v) => `+${v.toFixed(1)}`}
              />
            ) : (
              <Loading label="model influence" className="h-40" />
            )}
            <p className="text-fg-subtle text-2xs mt-2">
              RMSE increase when shuffled. Not a fault diagnosis.
            </p>
          </Section>

          <Section title="Provenance">
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
              <dt className="text-fg-subtle">Source</dt>
              <dd>
                {e.provenance.dataset} {e.provenance.subset} {e.provenance.split} unit{" "}
                {e.provenance.unit_id}
              </dd>
              <dt className="text-fg-subtle">Data</dt>
              <dd>
                {e.provenance.data_kind === "nasa_cmapss"
                  ? "Simulated (NASA)"
                  : "Synthetic fixture"}
              </dd>
              <dt className="text-fg-subtle">Aircraft link</dt>
              <dd>Fictional</dd>
              {e.provenance.eval_true_rul !== null ? (
                <>
                  <dt
                    className="text-fg-subtle"
                    title="NASA ground truth. Evaluation context only; not used for planning."
                  >
                    True RUL (eval)
                  </dt>
                  <dd className="font-mono">{e.provenance.eval_true_rul}</dd>
                </>
              ) : null}
            </dl>
          </Section>
        </div>
      </div>

      <Section
        title="Scheduled legs"
        aside={
          <Link
            href={`/flights?aircraft=${e.aircraft_id ?? ""}${q}`}
            className="text-fg-subtle hover:text-fg text-2xs"
          >
            Rotation view
          </Link>
        }
      >
        <div className="relative overflow-x-auto" tabIndex={0}>
          <table className="w-full min-w-[640px] text-xs">
            <thead className="text-fg-subtle">
              <tr className="border-line-strong border-b text-left">
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Flight
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Route
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Departs (local)
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  Arrives (local)
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  Cum. cyc
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  L after
                </th>
                <th scope="col" className="px-2 py-1.5 font-normal">
                  <span className="sr-only">Flag</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {e.flights.map((f) => (
                <tr
                  key={f.id}
                  className={`border-line border-b ${f.id === firstFlagged ? "border-t-warn border-t-2" : ""} ${f.flagged ? "" : "text-fg-muted"}`}
                >
                  <td className="px-2 py-1 font-mono">
                    <Link
                      href={`/flights?aircraft=${f.aircraft_id}&flight=${f.id}${q}`}
                      className="hover:underline"
                    >
                      {f.flight_number}
                    </Link>
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
                  <td className="px-2 py-1 text-right font-mono">{f.cumulative_cycles}</td>
                  <td className="px-2 py-1 text-right font-mono">
                    {f.conservative_margin_after !== null
                      ? cycles(f.conservative_margin_after)
                      : "—"}
                  </td>
                  <td className="px-2 py-1 text-xs">
                    {f.flagged ? <span className="text-fg">Below buffer</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

function Metric({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-fg-subtle">{label}</dt>
      <dd className={`font-mono ${strong ? "text-fg text-sm font-semibold" : "text-sm"}`}>
        {value}
      </dd>
    </div>
  );
}

function MaintenanceLine({
  plan,
  engineId,
  bufferParam,
}: {
  plan: Plan | undefined;
  engineId: string;
  bufferParam: number | undefined;
}) {
  if (!plan) return null;
  const placed = plan.placements.find((p) => p.engine_id === engineId);
  const unplaced = plan.unscheduled.find((u) => u.engine_id === engineId);
  if (!placed && !unplaced) return null;
  const buffer = bufferParam !== undefined ? `&buffer=${bufferParam}` : "";
  return (
    <p className="-mt-3 text-xs">
      <span className="text-fg-subtle mr-2">Maintenance (baseline)</span>
      {placed ? (
        <Link
          href={`/maintenance?job=${placed.job_id}${buffer}`}
          className="text-accent hover:underline"
        >
          {JOB_TYPE_LABEL[placed.job_type]} · {placed.bay} · {utcTime(placed.start)}
          {placed.cycles_over ? ` · ${placed.cycles_over} cyc past threshold` : ""}
        </Link>
      ) : (
        <span className="text-warn">Not placed: {unplaced?.why}</span>
      )}
    </p>
  );
}
