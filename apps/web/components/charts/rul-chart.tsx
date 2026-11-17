"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EngineHistory, Flight } from "@/lib/api/schemas";
import { cycles } from "@/lib/format";
import { projectConsumption } from "@/lib/projection";
import { AXIS, GRID, TooltipBox } from "./chart-tooltip";

type Row = {
  cycle: number;
  estimate?: number;
  band?: [number, number];
  projEstimate?: number;
  projLower?: number;
  flightId?: string;
};

/**
 * Past: model estimate with 90% interval at each observed cycle.
 * Future: the latest estimate and lower bound minus scheduled legs (one cycle per leg).
 */
export function RulChart({
  history,
  flights,
  rulPoint,
  rulLower,
  buffer,
}: {
  history: EngineHistory;
  flights: readonly Flight[];
  rulPoint: number;
  rulLower: number;
  buffer: number;
}) {
  const observed = history.cycles.at(-1) ?? 0;
  const rows: Row[] = history.cycles.map((c, i) => ({
    cycle: c,
    estimate: history.rul_point[i] ?? 0,
    band: [history.rul_lower[i] ?? 0, history.rul_upper[i] ?? 0],
  }));
  const last = rows.at(-1);
  if (last) {
    last.projEstimate = rulPoint;
    last.projLower = rulLower;
  }
  for (const p of projectConsumption(observed, rulPoint, rulLower, flights)) {
    rows.push({
      cycle: p.cycle,
      projEstimate: p.estimate,
      projLower: p.lower,
      flightId: p.flightId,
    });
  }

  return (
    <figure aria-label="Predicted RUL by cycle with scheduled consumption">
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid {...GRID} />
            <XAxis
              dataKey="cycle"
              type="number"
              domain={["dataMin", "dataMax"]}
              {...AXIS}
              tickCount={8}
            />
            <YAxis {...AXIS} width={44} allowDecimals={false} />
            <ReferenceLine
              y={buffer}
              stroke="var(--color-warn)"
              strokeDasharray="4 3"
              label={{
                value: `Buffer ${buffer}`,
                position: "insideTopRight",
                fill: "var(--color-fg-muted)",
                fontSize: 11,
              }}
            />
            <ReferenceLine y={0} stroke="var(--color-line-strong)" />
            <ReferenceLine
              x={observed}
              stroke="var(--color-fg-subtle)"
              label={{
                value: "Now",
                position: "insideTopLeft",
                fill: "var(--color-fg-muted)",
                fontSize: 11,
              }}
            />
            <Area
              dataKey="band"
              stroke="none"
              fill="var(--color-accent)"
              fillOpacity={0.18}
              isAnimationActive={false}
              name="90% interval"
            />
            <Line
              dataKey="estimate"
              stroke="var(--color-accent)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              name="Estimate"
            />
            <Line
              dataKey="projEstimate"
              stroke="var(--color-accent)"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              isAnimationActive={false}
              name="Estimate after scheduled legs"
            />
            <Line
              dataKey="projLower"
              stroke="var(--color-fg-muted)"
              strokeWidth={2}
              strokeDasharray="2 3"
              dot={false}
              isAnimationActive={false}
              name="Lower bound after scheduled legs"
            />
            <Tooltip
              cursor={{ stroke: "var(--color-line-strong)" }}
              content={({ active, payload }) => {
                const row = payload?.[0]?.payload as Row | undefined;
                if (!active || !row) return null;
                const rowsOut: [string, string][] = [];
                if (row.estimate !== undefined) rowsOut.push(["Estimate", cycles(row.estimate)]);
                if (row.band)
                  rowsOut.push(["90% interval", `${cycles(row.band[0])}–${cycles(row.band[1])}`]);
                if (row.flightId && row.projEstimate !== undefined) {
                  rowsOut.push(["After leg", row.flightId]);
                  rowsOut.push(["Estimate", cycles(row.projEstimate)]);
                  rowsOut.push(["Lower bound", cycles(row.projLower ?? 0)]);
                }
                return <TooltipBox title={`Cycle ${row.cycle}`} rows={rowsOut} />;
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="text-fg-subtle text-2xs mt-1 flex flex-wrap gap-x-4 gap-y-1">
        <Key swatch={<span className="bg-accent h-0.5 w-4" />}>Estimate</Key>
        <Key swatch={<span className="bg-accent/20 h-2.5 w-4" />}>90% interval</Key>
        <Key swatch={<span className="border-accent w-4 border-t-2 border-dashed" />}>
          Estimate − scheduled legs
        </Key>
        <Key swatch={<span className="border-fg-muted w-4 border-t-2 border-dotted" />}>
          Lower bound − scheduled legs
        </Key>
        <span>y: cycles · x: engine cycle</span>
      </figcaption>
    </figure>
  );
}

function Key({ swatch, children }: { swatch: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden className="flex items-center">
        {swatch}
      </span>
      {children}
    </span>
  );
}
