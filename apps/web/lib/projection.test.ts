import { describe, expect, it } from "vitest";
import type { Flight } from "./api/schemas";
import { projectConsumption } from "./projection";

function flight(id: string, departure: string, cumulative: number): Flight {
  return {
    id,
    flight_number: id,
    aircraft_id: "N801AF",
    engine_id: "ENG-N801AF",
    origin: "ORD",
    destination: "DEN",
    departure,
    arrival: departure,
    departure_local: departure,
    arrival_local: departure,
    origin_tz: "America/Chicago",
    destination_tz: "America/Denver",
    origin_tz_abbr: "CST",
    destination_tz_abbr: "MST",
    status: "scheduled",
    cycles: 1,
    cumulative_cycles: cumulative,
    conservative_margin_after: null,
    flagged: false,
  };
}

describe("projectConsumption", () => {
  it("subtracts cumulative cycles from estimate and lower bound, in departure order", () => {
    const points = projectConsumption(150, 30, 12, [
      flight("B", "2027-03-11T18:00:00Z", 2),
      flight("A", "2027-03-11T12:00:00Z", 1),
    ]);
    expect(points.map((p) => p.flightId)).toEqual(["A", "B"]);
    expect(points[0]).toMatchObject({ cycle: 151, estimate: 29, lower: 11 });
    expect(points[1]).toMatchObject({ cycle: 152, estimate: 28, lower: 10 });
  });

  it("does not mutate the input and handles no flights", () => {
    const input = [flight("B", "2027-03-12T00:00:00Z", 1), flight("A", "2027-03-11T00:00:00Z", 2)];
    projectConsumption(0, 1, 0, input);
    expect(input[0]?.id).toBe("B");
    expect(projectConsumption(10, 5, 2, [])).toEqual([]);
  });
});
