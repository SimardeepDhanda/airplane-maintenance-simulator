import type { ReactNode } from "react";

/** Shared tooltip surface for charts. Text uses text tokens, never series colours. */
export function TooltipBox({ title, rows }: { title: ReactNode; rows: [string, ReactNode][] }) {
  return (
    <div className="border-line-strong bg-raised rounded-sm border px-2.5 py-2 text-xs shadow-lg">
      <div className="text-fg mb-1 font-medium">{title}</div>
      <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-fg-subtle">{k}</dt>
            <dd className="text-fg text-right font-mono">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export const AXIS = {
  stroke: "var(--color-line-strong)",
  tick: { fill: "var(--color-fg-subtle)", fontSize: 11 },
  tickLine: false,
} as const;

export const GRID = { stroke: "var(--color-line)", strokeDasharray: "0", vertical: false } as const;
