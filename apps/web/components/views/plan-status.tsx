import type { Plan } from "@/lib/api/schemas";

const TEXT: Record<Plan["status"], string> = {
  OPTIMAL: "Optimal",
  FEASIBLE: "Feasible",
  INFEASIBLE: "Infeasible",
  UNKNOWN: "No solution in time limit",
  NO_SOLUTION: "No plan found",
};

const TONE: Record<Plan["status"], string> = {
  OPTIMAL: "bg-ok",
  FEASIBLE: "bg-ok",
  INFEASIBLE: "bg-crit",
  UNKNOWN: "bg-warn",
  NO_SOLUTION: "bg-crit",
};

/** Solver status with what it does and does not prove. */
export function PlanStatus({ plan }: { plan: Plan }) {
  const note =
    plan.method === "baseline"
      ? "EDD heuristic"
      : plan.status === "OPTIMAL"
        ? "CP-SAT, proven"
        : plan.status === "FEASIBLE"
          ? "CP-SAT, not proven optimal"
          : "CP-SAT";
  return (
    <span className="inline-flex items-center gap-1.5 font-sans whitespace-nowrap">
      <span aria-hidden className={`size-2 rounded-full ${TONE[plan.status]}`} />
      {TEXT[plan.status]}
      <span className="text-fg-subtle">
        {note} · {plan.wall_ms} ms
        {plan.placements.length ? (plan.verified ? " · checked" : " · CHECK FAILED") : ""}
      </span>
    </span>
  );
}
