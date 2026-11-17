import Link from "next/link";
import { ApiStatus } from "./api-status";
import { UtcClock } from "./utc-clock";

export function StatusRail() {
  return (
    <header className="border-line bg-surface flex h-10 shrink-0 items-center justify-between gap-4 border-b px-3">
      <Link href="/overview" className="flex items-baseline gap-2 rounded-sm">
        <span className="font-mono text-xs font-semibold tracking-[0.2em]">NORTHSTAR</span>
        <span className="text-fg-subtle hidden text-xs sm:inline">Maintenance Control</span>
      </Link>
      <div className="flex items-center gap-4">
        <Link
          href="/methodology"
          title="Engine data: NASA C-MAPSS (simulated). Airline, flights and costs: fictional."
          className="border-line-strong text-fg-muted hover:text-fg text-2xs rounded-sm border px-1.5 py-0.5 font-mono tracking-wider uppercase"
        >
          Simulation
        </Link>
        <ApiStatus />
        <UtcClock />
      </div>
    </header>
  );
}
