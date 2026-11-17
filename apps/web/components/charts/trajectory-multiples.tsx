"use client";

import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ModelMetrics } from "@/lib/api/schemas";
import { cycles } from "@/lib/format";
import { AXIS, TooltipBox } from "./chart-tooltip";

type Row = { cycle: number; truth: number; estimate: number; band: [number, number] };

/** Selected official test engines over their whole observed history. */
export function TrajectoryMultiples({ items }: { items: ModelMetrics["test"]["trajectories"] }) {
  return (
    <div>
      <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        {items.map((t) => {
          const data: Row[] = t.cycle.map((c, i) => ({
            cycle: c,
            truth: t.true_rul[i] ?? 0,
            estimate: t.rul_point[i] ?? 0,
            band: [t.rul_lower[i] ?? 0, t.rul_upper[i] ?? 0],
          }));
          return (
            <figure key={t.unit_id} aria-label={`Test unit ${t.unit_id} trajectory`}>
              <figcaption className="text-fg-muted text-2xs mb-0.5">
                Test unit {t.unit_id} · true RUL at last cycle {t.true_rul.at(-1)}
              </figcaption>
              <div className="h-32">
                <ResponsiveContainer>
                  <ComposedChart data={data} margin={{ top: 2, right: 6, bottom: 0, left: -12 }}>
                    <XAxis
                      dataKey="cycle"
                      type="number"
                      domain={["dataMin", "dataMax"]}
                      {...AXIS}
                      tickCount={5}
                    />
                    <YAxis {...AXIS} width={40} />
                    <Area
                      dataKey="band"
                      stroke="none"
                      fill="var(--color-accent)"
                      fillOpacity={0.18}
                      isAnimationActive={false}
                    />
                    <Line
                      dataKey="truth"
                      stroke="var(--color-fg-muted)"
                      strokeWidth={1.5}
                      strokeDasharray="3 3"
                      dot={false}
                      isAnimationActive={false}
                    />
                    <Line
                      dataKey="estimate"
                      stroke="var(--color-accent)"
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                    />
                    <Tooltip
                      cursor={{ stroke: "var(--color-line-strong)" }}
                      content={({ active, payload }) => {
                        const p = payload?.[0]?.payload as Row | undefined;
                        return active && p ? (
                          <TooltipBox
                            title={`Cycle ${p.cycle}`}
                            rows={[
                              ["True", cycles(p.truth)],
                              ["Estimate", cycles(p.estimate)],
                              ["Interval", `${cycles(p.band[0])}–${cycles(p.band[1])}`],
                            ]}
                          />
                        ) : null;
                      }}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </figure>
          );
        })}
      </div>
      <div className="text-fg-subtle text-2xs mt-1 flex gap-4">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-accent h-0.5 w-4" />
          Estimate
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="bg-accent/20 h-2.5 w-4" />
          90% interval
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="border-fg-muted w-4 border-t-2 border-dashed" />
          True RUL
        </span>
      </div>
    </div>
  );
}
