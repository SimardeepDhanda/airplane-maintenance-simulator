"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EngineHistory } from "@/lib/api/schemas";
import { sensorLabel } from "@/lib/format";
import { AXIS, TooltipBox } from "./chart-tooltip";

/** One small chart per sensor: each has its own scale, so no shared axis is implied. */
export function SensorMultiples({
  history,
  sensors,
}: {
  history: EngineHistory;
  sensors: readonly string[];
}) {
  const series = history.sensors.filter((s) => sensors.includes(s.name));
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {series.map((s) => {
        const data = history.cycles.map((c, i) => ({ cycle: c, value: s.values[i] ?? 0 }));
        return (
          <figure key={s.name} aria-label={`${s.name} by cycle`}>
            <figcaption className="text-fg-muted text-2xs mb-0.5 font-mono">
              {sensorLabel(s.name)}
            </figcaption>
            <div className="h-24">
              <ResponsiveContainer>
                <LineChart data={data} margin={{ top: 2, right: 6, bottom: 0, left: -6 }}>
                  <XAxis
                    dataKey="cycle"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    {...AXIS}
                    tickCount={5}
                  />
                  <YAxis {...AXIS} width={52} domain={["auto", "auto"]} tickCount={3} />
                  <Line
                    dataKey="value"
                    stroke="var(--color-fg-muted)"
                    strokeWidth={1.25}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Tooltip
                    cursor={{ stroke: "var(--color-line-strong)" }}
                    content={({ active, payload }) => {
                      const p = payload?.[0]?.payload as
                        { cycle: number; value: number } | undefined;
                      return active && p ? (
                        <TooltipBox
                          title={`Cycle ${p.cycle}`}
                          rows={[[sensorLabel(s.name), p.value.toFixed(2)]]}
                        />
                      ) : null;
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </figure>
        );
      })}
    </div>
  );
}
