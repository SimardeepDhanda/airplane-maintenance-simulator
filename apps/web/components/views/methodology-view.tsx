"use client";

import { HBars } from "@/components/charts/hbars";
import { PredVsActual } from "@/components/charts/pred-vs-actual";
import { TrajectoryMultiples } from "@/components/charts/trajectory-multiples";
import { Loading, QueryError } from "@/components/feedback/query-state";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";
import { useModelMetrics } from "@/lib/api/queries";
import { cycles, percent } from "@/lib/format";

const MODEL_NAME: Record<string, string> = {
  constant: "Constant (mean)",
  cycle_linear: "Linear on cycle",
  ridge: "Ridge",
  hgb: "Gradient boosting",
};

export function MethodologyView() {
  const metrics = useModelMetrics();

  return (
    <div className="flex max-w-6xl flex-col gap-6">
      <PageHeader title="Methodology" />

      <Section title="Data">
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-xs md:grid-cols-2">
          <Fact term="Engine data">
            NASA C-MAPSS FD001: simulated turbofan run-to-failure trajectories (NASA PCoE
            repository). Not airline telemetry.
          </Fact>
          <Fact term="Airline">
            Northstar Air is fictional. Ships, routes, schedules and costs are generated from a
            fixed seed. Airport codes are real; no real airline data.
          </Fact>
          <Fact term="Mapping">
            Each ship carries one monitored engine, drawn from NASA FD001 test engines the model
            never trained on. Real narrowbodies have two engines.
          </Fact>
          <Fact term="Cycles">
            One flight leg = one engine cycle. Cycles are not hours or distance.
          </Fact>
          <Fact term="RUL">
            Estimated cycles to simulated failure. A modelling target, not a maintenance limit.
          </Fact>
          <Fact term="Planning flag">
            Lower-bound RUL minus scheduled cycles (L − n) compared with a user-set buffer.
            Critical: L − n &lt; 0. Review: below buffer. A hypothetical policy, not an inspection
            requirement or a clearance decision.
          </Fact>
        </dl>
      </Section>

      {metrics.isError ? (
        <QueryError error={metrics.error} onRetry={() => void metrics.refetch()} />
      ) : !metrics.data ? (
        <Loading label="model metrics" className="h-96" />
      ) : (
        <MetricsSections m={metrics.data} />
      )}
    </div>
  );
}

function MetricsSections({ m }: { m: NonNullable<ReturnType<typeof useModelMetrics>["data"]> }) {
  const cap = m.selection.selected.target_cap;
  const iv = m.test.intervals;
  return (
    <>
      {m.model.data_kind !== "nasa_cmapss" ? (
        <p role="alert" className="border-warn/50 text-fg rounded-sm border px-3 py-2 text-xs">
          This model was trained on a synthetic test fixture. Its metrics are not NASA results.
        </p>
      ) : null}

      <Section
        title="Model comparison · official test split"
        aside={<span className="text-fg-subtle text-2xs font-mono">{m.model.version}</span>}
      >
        <div className="relative overflow-x-auto" tabIndex={0}>
          <table className="w-full min-w-[640px] text-xs">
            <thead className="text-fg-subtle">
              <tr className="border-line-strong border-b">
                <th scope="col" className="px-2 py-1.5 text-left font-normal">
                  Model
                </th>
                <th scope="col" className="px-2 py-1.5 text-left font-normal">
                  Target
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  RMSE
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  MAE
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  Bias
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  PHM08
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  CV RMSE*
                </th>
              </tr>
            </thead>
            <tbody>
              {m.test.comparison.map((r) => {
                const cv = m.selection.results.find(
                  (c) => c.model === r.model && c.target_cap === r.target_cap,
                );
                return (
                  <tr
                    key={`${r.model}-${r.target_cap}`}
                    className={`border-line border-b ${r.selected ? "text-fg" : "text-fg-muted"}`}
                  >
                    <td className="px-2 py-1">
                      {MODEL_NAME[r.model] ?? r.model}
                      {r.selected ? (
                        <span className="text-accent text-2xs ml-2">selected</span>
                      ) : null}
                    </td>
                    <td className="px-2 py-1">
                      {r.target_cap !== null ? `capped ${r.target_cap}` : "uncapped"}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {r.last_cycle.rmse.toFixed(2)}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {r.last_cycle.mae.toFixed(2)}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {r.last_cycle.bias.toFixed(2)}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {Math.round(r.last_cycle.phm08_score).toLocaleString("en-US")}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {cv ? cv.rmse_vs_capped_truth.toFixed(2) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="text-fg-subtle text-2xs mt-2">
          Last observed cycle of {m.test.n_engines} test engines, cycles. *Selection metric:{" "}
          {m.selection.cv}, vs. truth capped at {cap ?? "—"}. Test split not used for any choice.
        </p>
      </Section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Section title="Predicted vs true">
          <PredVsActual rows={m.test.per_engine} cap={cap} />
        </Section>
        <div className="flex flex-col gap-6">
          <Section title="Error by true RUL · selected model">
            <HBars
              label="RMSE by true RUL bin"
              rows={m.test.selected_by_true_rul_bin.map((b) => ({
                key: b.true_rul,
                label: `${b.true_rul} (n=${b.n})`,
                value: b.rmse,
                note: `MAE ${b.mae.toFixed(2)}, bias ${b.bias.toFixed(2)}`,
              }))}
              format={(v) => v.toFixed(1)}
            />
            <p className="text-fg-subtle text-2xs mt-2">
              RMSE, cycles. Predictions cap at {cap ?? "—"}, so 125+ is under-estimated.
            </p>
          </Section>
          <Section title="Interval calibration">
            <table className="w-full text-xs">
              <thead className="text-fg-subtle">
                <tr className="border-line-strong border-b">
                  <th scope="col" className="py-1.5 text-left font-normal">
                    Held-out data
                  </th>
                  <th scope="col" className="py-1.5 text-right font-normal">
                    Coverage
                  </th>
                  <th scope="col" className="py-1.5 text-right font-normal">
                    Lower holds
                  </th>
                  <th scope="col" className="py-1.5 text-right font-normal">
                    Width
                  </th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["Last cycle", iv.last_cycle],
                    ["All cycles", iv.all_cycles],
                  ] as const
                ).map(([label, c]) => (
                  <tr key={label} className="border-line border-b">
                    <td className="py-1">
                      {label} (n={c.n.toLocaleString("en-US")})
                    </td>
                    <td className="py-1 text-right font-mono">{percent(c.coverage)}</td>
                    <td className="py-1 text-right font-mono">{percent(c.lower_bound_coverage)}</td>
                    <td className="py-1 text-right font-mono">{cycles(c.mean_width)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-fg-subtle text-2xs mt-2">
              Split conformal, nominal {percent(iv.nominal_coverage, 0)}, calibrated on{" "}
              {m.split.calibration_units.length} held-out training engines. Cycles within an engine
              are dependent, so coverage is measured, not guaranteed.
            </p>
          </Section>
        </div>
      </div>

      <Section title="Test trajectories">
        <TrajectoryMultiples items={m.test.trajectories} />
      </Section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Section title="Model influence">
          <HBars
            label="Permutation importance"
            rows={m.permutation_importance.features.slice(0, 10).map((f) => ({
              key: f.feature,
              label: f.feature.replace("sensor_", "S"),
              value: f.mean,
            }))}
            format={(v) => `+${v.toFixed(1)}`}
          />
          <p className="text-fg-subtle text-2xs mt-2">
            RMSE increase when a feature is shuffled ({m.permutation_importance.data}). Describes
            what the model uses, not physical cause. Sensor indices are NASA&apos;s; meanings are
            not defined in the dataset.
          </p>
        </Section>
        <Section title="Features and split">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
            <dt className="text-fg-subtle">Sensors used</dt>
            <dd className="font-mono">
              {m.features.sensors.map((s) => s.replace("sensor_", "S")).join(" ")}
            </dd>
            <dt className="text-fg-subtle">Dropped</dt>
            <dd className="font-mono">
              {m.features.dropped_channels.map((s) => s.replace("sensor_", "S")).join(" ")}
            </dd>
            <dt className="text-fg-subtle">Per sensor</dt>
            <dd>
              value, {m.features.window}-cycle mean and std, drift from first{" "}
              {m.features.baseline_cycles} cycles
            </dd>
            <dt className="text-fg-subtle">Split</dt>
            <dd>
              {m.split.fit_units.length} fit / {m.split.calibration_units.length} calibration
              training engines, by engine
            </dd>
          </dl>
        </Section>
      </div>
    </>
  );
}

function Fact({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-3">
      <dt className="text-fg-subtle">{term}</dt>
      <dd className="text-fg-muted">{children}</dd>
    </div>
  );
}
