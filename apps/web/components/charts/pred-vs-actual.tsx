"use client";

import {
  CartesianGrid,
  ErrorBar,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ModelMetrics } from "@/lib/api/schemas";
import { cycles } from "@/lib/format";
import { AXIS, GRID, TooltipBox } from "./chart-tooltip";

type Point = ModelMetrics["test"]["per_engine"][number] & { err: [number, number] };

/** Official test engines at their last observed cycle: true vs predicted RUL with interval. */
export function PredVsActual({
  rows,
  cap,
}: {
  rows: ModelMetrics["test"]["per_engine"];
  cap: number | null;
}) {
  const data: Point[] = rows.map((r) => ({
    ...r,
    err: [r.rul_point - r.rul_lower, r.rul_upper - r.rul_point],
  }));
  const max = Math.ceil(Math.max(...rows.map((r) => Math.max(r.true_rul, r.rul_upper))) / 25) * 25;
  const ticks = Array.from({ length: max / 25 + 1 }, (_, i) => i * 25);
  return (
    <figure aria-label="Predicted versus true RUL on official test engines">
      <div className="h-72">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: -4 }}>
            <CartesianGrid {...GRID} vertical />
            <XAxis
              dataKey="true_rul"
              type="number"
              domain={[0, max]}
              ticks={ticks}
              allowDataOverflow
              name="True RUL"
              {...AXIS}
              label={{
                value: "True RUL (cycles)",
                position: "insideBottom",
                offset: -8,
                fill: "var(--color-fg-subtle)",
                fontSize: 11,
              }}
            />
            <YAxis
              dataKey="rul_point"
              type="number"
              domain={[0, max]}
              ticks={ticks}
              allowDataOverflow
              name="Predicted"
              {...AXIS}
              width={48}
              label={{
                value: "Predicted",
                angle: -90,
                position: "insideLeft",
                offset: 16,
                fill: "var(--color-fg-subtle)",
                fontSize: 11,
              }}
            />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: max, y: max },
              ]}
              stroke="var(--color-line-strong)"
              strokeDasharray="4 3"
            />
            {cap !== null ? (
              <ReferenceLine
                y={cap}
                stroke="var(--color-line-strong)"
                label={{
                  value: `Cap ${cap}`,
                  position: "insideBottomRight",
                  fill: "var(--color-fg-subtle)",
                  fontSize: 11,
                }}
              />
            ) : null}
            <Scatter
              data={data}
              fill="var(--color-accent)"
              isAnimationActive={false}
              shape={<Dot />}
            >
              <ErrorBar
                dataKey="err"
                direction="y"
                stroke="var(--color-accent)"
                strokeOpacity={0.35}
                width={0}
              />
            </Scatter>
            <Tooltip
              cursor={false}
              content={({ active, payload }) => {
                const p = payload?.[0]?.payload as Point | undefined;
                return active && p ? (
                  <TooltipBox
                    title={`Test unit ${p.unit_id}`}
                    rows={[
                      ["True", cycles(p.true_rul)],
                      ["Predicted", cycles(p.rul_point)],
                      ["Interval", `${cycles(p.rul_lower)}–${cycles(p.rul_upper)}`],
                      ["Observed cycles", String(p.observed_cycles)],
                    ]}
                  />
                ) : null;
              }}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

function Dot(props: { cx?: number; cy?: number }) {
  const { cx = 0, cy = 0 } = props;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill="var(--color-accent)"
      stroke="var(--color-surface)"
      strokeWidth={2}
    />
  );
}
