"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { BufferControl } from "@/components/controls/buffer-control";
import { Segmented } from "@/components/controls/segmented";
import { Select } from "@/components/controls/select";
import { RangeCell } from "@/components/charts/range-cell";
import { Empty, Loading, QueryError } from "@/components/feedback/query-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { useAirports, useEngines } from "@/lib/api/queries";
import type { EngineSummary, PlanningStatus } from "@/lib/api/schemas";
import { cycles, signedCycles } from "@/lib/format";
import { parseBuffer, useUrlState } from "@/lib/use-url-state";

type SortKey = "id" | "rul_point" | "rul_lower" | "conservative_margin" | "observed_cycles";
const SORTABLE: Record<string, SortKey> = {
  id: "id",
  rul: "rul_point",
  lower: "rul_lower",
  margin: "conservative_margin",
  observed: "observed_cycles",
};
const STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "critical", label: "Critical" },
  { value: "review", label: "Review" },
  { value: "ok", label: "OK" },
] as const;

const col = createColumnHelper<EngineSummary>();

export function EnginesView() {
  const router = useRouter();
  const { params, set } = useUrlState();
  const bufferParam = parseBuffer(params.get("buffer"));
  const status = (params.get("status") ?? "all") as PlanningStatus | "all";
  const station = params.get("station") ?? "";
  const sort = (params.get("sort") as SortKey | null) ?? "conservative_margin";
  const order = params.get("order") === "desc" ? "desc" : "asc";

  const engines = useEngines({
    buffer: bufferParam,
    status: status === "all" ? undefined : status,
    station: station || undefined,
    sort,
    order,
    page_size: 100,
  });
  const airports = useAirports();
  const items = useMemo(() => engines.data?.items ?? [], [engines.data]);
  const scaleMax = Math.max(125, ...items.map((e) => e.prediction.rul_upper));
  const buffer = items[0]?.planning.buffer ?? bufferParam ?? 10;
  const detailHref = (id: string) =>
    `/engines/${id}${bufferParam !== undefined ? `?buffer=${bufferParam}` : ""}`;

  const columns = useMemo(
    () => [
      col.accessor("id", {
        id: "id",
        header: "Engine",
        cell: (c) => (
          <Link href={detailHref(c.getValue())} className="text-accent font-mono hover:underline">
            {c.getValue()}
          </Link>
        ),
      }),
      col.accessor("aircraft_id", {
        header: "Ship",
        cell: (c) => <span className="font-mono">{c.getValue() ?? "—"}</span>,
      }),
      col.accessor("station", { header: "Station", cell: (c) => c.getValue() ?? "—" }),
      col.accessor("observed_cycles", {
        id: "observed",
        header: "Cycles",
        meta: { numeric: true },
        cell: (c) => <span className="font-mono">{c.getValue()}</span>,
      }),
      col.accessor((e) => e.prediction.rul_point, {
        id: "rul",
        header: "RUL est. · 90% int.",
        cell: (c) => (
          <RangeCell
            point={c.row.original.prediction.rul_point}
            lower={c.row.original.prediction.rul_lower}
            upper={c.row.original.prediction.rul_upper}
            max={scaleMax}
          />
        ),
      }),
      col.accessor((e) => e.prediction.rul_lower, {
        id: "lower",
        header: "Lower",
        meta: { numeric: true },
        cell: (c) => <span className="font-mono">{cycles(c.getValue())}</span>,
      }),
      col.accessor((e) => e.planning.forecast_cycles, {
        id: "legs",
        header: "Sched. cyc",
        meta: { numeric: true },
        cell: (c) => <span className="font-mono">{c.getValue()}</span>,
      }),
      col.accessor((e) => e.planning.conservative_margin, {
        id: "margin",
        header: "L − n",
        meta: { numeric: true },
        cell: (c) => <span className="font-mono">{signedCycles(c.getValue())}</span>,
      }),
      col.accessor((e) => e.planning.status, {
        id: "status",
        header: "Status",
        cell: (c) => <StatusBadge status={c.getValue()} />,
      }),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scaleMax, bufferParam],
  );

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table returns unstable functions by design; the view is not memoized.
  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
  });

  const toggleSort = (columnId: string) => {
    const key = SORTABLE[columnId];
    if (!key) return;
    set({ sort: key, order: key === sort && order === "asc" ? "desc" : "asc" });
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Engines" />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Segmented
          label="Planning status"
          value={status}
          options={STATUS_OPTIONS}
          onChange={(v) => set({ status: v === "all" ? null : v })}
        />
        <Select
          label="Station"
          value={station}
          options={(airports.data ?? []).map((a) => ({ value: a.code, label: a.code }))}
          onChange={(v) => set({ station: v || null })}
        />
        <BufferControl value={buffer} onChange={(v) => set({ buffer: v })} />
        <span className="text-fg-subtle ml-auto text-xs" aria-live="polite">
          {engines.data ? `${engines.data.total} engines` : ""}
        </span>
      </div>

      {engines.isError ? (
        <QueryError error={engines.error} onRetry={() => void engines.refetch()} />
      ) : !engines.data ? (
        <Loading label="engines" className="h-96" />
      ) : items.length === 0 ? (
        <Empty>No engines match these filters</Empty>
      ) : (
        <div className="relative overflow-x-auto" tabIndex={0}>
          <table className="w-full min-w-[760px] text-xs">
            <thead>
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id} className="border-line-strong border-b">
                  {group.headers.map((header) => {
                    const key = SORTABLE[header.column.id];
                    const active = key === sort;
                    const numeric = (
                      header.column.columnDef.meta as { numeric?: boolean } | undefined
                    )?.numeric;
                    return (
                      <th
                        key={header.id}
                        scope="col"
                        aria-sort={
                          active ? (order === "asc" ? "ascending" : "descending") : undefined
                        }
                        className={`text-fg-subtle px-2 py-1.5 font-normal ${numeric ? "text-right" : "text-left"}`}
                      >
                        {key ? (
                          <button
                            type="button"
                            onClick={() => toggleSort(header.column.id)}
                            className={`hover:text-fg inline-flex items-center gap-1 ${active ? "text-fg" : ""}`}
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            <span aria-hidden className="w-2">
                              {active ? (order === "asc" ? "↑" : "↓") : ""}
                            </span>
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={(e) => {
                    if ((e.target as HTMLElement).closest("a,button")) return;
                    router.push(detailHref(row.original.id));
                  }}
                  className="border-line hover:bg-raised/60 cursor-pointer border-b"
                >
                  {row.getVisibleCells().map((cell) => {
                    const numeric = (
                      cell.column.columnDef.meta as { numeric?: boolean } | undefined
                    )?.numeric;
                    return (
                      <td key={cell.id} className={`px-2 py-1.5 ${numeric ? "text-right" : ""}`}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
