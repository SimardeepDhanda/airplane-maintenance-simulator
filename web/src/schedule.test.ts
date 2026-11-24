import { describe, expect, it } from "vitest";
import { dueDay, flightsLost, schedule, type Engine } from "./schedule";

const engine = (tail: string, rul: number, fpd = 4): Engine => ({
  tail,
  engine: tail,
  cycles_flown: 100,
  flights_per_day: fpd,
  predicted_rul: rul,
  actual_rul: rul,
  history: [],
});

describe("dueDay", () => {
  it("counts whole days of flying above the buffer", () => {
    expect(dueDay(engine("A", 30, 4), 10)).toBe(5);
    expect(dueDay(engine("A", 5, 4), 10)).toBe(0);
  });
});

describe("schedule", () => {
  it("skips engines that last past the window", () => {
    expect(schedule([engine("A", 500)], 1, 0)).toEqual([]);
  });

  it("uses the due day when a bay is free", () => {
    const [job] = schedule([engine("A", 20)], 1, 0);
    expect(job).toMatchObject({ day: 5, late: false });
  });

  it("never puts more jobs on a day than there are bays", () => {
    const fleet = ["A", "B", "C", "D", "E"].map((t) => engine(t, 8));
    const jobs = schedule(fleet, 2, 0);
    const perDay: Record<number, number> = {};
    for (const j of jobs) perDay[j.day!] = (perDay[j.day!] ?? 0) + 1;
    expect(Math.max(...Object.values(perDay))).toBeLessThanOrEqual(2);
  });

  it("pushes a job past its due day when the hangar is full", () => {
    const jobs = schedule([engine("A", 0), engine("B", 0)], 1, 0);
    expect(jobs.map((j) => [j.day, j.late])).toEqual([[0, false], [1, true]]);
    expect(flightsLost(jobs, [engine("A", 0), engine("B", 0)])).toBe(4 + 8);
  });
});
