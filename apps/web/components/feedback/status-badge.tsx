import type { PlanningStatus } from "@/lib/api/schemas";
import { STATUS_LABEL } from "@/lib/format";

const DOT: Record<PlanningStatus, string> = {
  critical: "bg-crit",
  review: "bg-warn",
  ok: "bg-ok",
};

/** Status is always label + colour, never colour alone. */
export function StatusBadge({ status }: { status: PlanningStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs whitespace-nowrap">
      <span aria-hidden className={`size-2 rounded-full ${DOT[status]}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

export const STATUS_FILL: Record<PlanningStatus, string> = {
  critical: "var(--color-crit)",
  review: "var(--color-warn)",
  ok: "var(--color-fg-subtle)",
};
