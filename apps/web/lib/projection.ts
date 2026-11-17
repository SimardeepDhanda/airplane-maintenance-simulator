import type { Flight } from "@/lib/api/schemas";

export type ProjectionPoint = {
  cycle: number;
  estimate: number;
  lower: number;
  flightId: string;
  departure: string;
  departureLocal: string;
};

/**
 * Forward projection of predicted cycles as scheduled legs are flown.
 * Leg k (1-based, cumulative cycles c_k) leaves estimate R − c_k and lower bound L − c_k.
 * The model is not re-run: this is schedule consumption against the latest prediction.
 */
export function projectConsumption(
  observedCycle: number,
  rulPoint: number,
  rulLower: number,
  flights: readonly Flight[],
): ProjectionPoint[] {
  return [...flights]
    .sort((a, b) => a.departure.localeCompare(b.departure))
    .map((f) => ({
      cycle: observedCycle + f.cumulative_cycles,
      estimate: rulPoint - f.cumulative_cycles,
      lower: rulLower - f.cumulative_cycles,
      flightId: f.id,
      departure: f.departure,
      departureLocal: f.departure_local,
    }));
}
