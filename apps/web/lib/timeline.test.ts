import { describe, expect, it } from "vitest";
import { dayStarts, nightBands } from "./timeline";

const SHIFTS = [
  { start_local: "06:00:00", end_local: "18:00:00", is_night: false },
  { start_local: "18:00:00", end_local: "06:00:00", is_night: true },
];

describe("dayStarts", () => {
  it("lists UTC midnights inside the range", () => {
    const days = dayStarts(Date.parse("2027-03-11T10:00:00Z"), Date.parse("2027-03-13T10:00:00Z"));
    expect(days.map((d) => d.toISOString())).toEqual([
      "2027-03-12T00:00:00.000Z",
      "2027-03-13T00:00:00.000Z",
    ]);
  });
});

describe("nightBands", () => {
  it("follows local time and shifts by an hour across DST", () => {
    const t0 = Date.parse("2027-03-13T10:00:00Z");
    const t1 = Date.parse("2027-03-15T10:00:00Z");
    const bands = nightBands(SHIFTS, "America/Chicago", t0, t1);
    // Chicago night 18:00-06:00 local: CST (UTC-6) on 13 Mar, CDT (UTC-5) from 14 Mar.
    expect(bands.map(([a, b]) => [new Date(a).toISOString(), new Date(b).toISOString()])).toEqual([
      ["2027-03-13T10:00:00.000Z", "2027-03-13T12:00:00.000Z"], // 04:00-06:00 CST
      ["2027-03-14T00:00:00.000Z", "2027-03-14T11:00:00.000Z"],
      ["2027-03-14T23:00:00.000Z", "2027-03-15T10:00:00.000Z"],
    ]);
  });
});
