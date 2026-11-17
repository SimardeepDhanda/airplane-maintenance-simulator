import { describe, expect, it } from "vitest";
import {
  cycles,
  localTime,
  percent,
  sensorLabel,
  signedCycles,
  utcDay,
  utcTime,
  zonedTime,
} from "./format";

describe("cycles", () => {
  it("drops the decimal for integers and keeps one otherwise", () => {
    expect(cycles(42)).toBe("42");
    expect(cycles(41.96)).toBe("42");
    expect(cycles(12.34)).toBe("12.3");
  });
});

describe("signedCycles", () => {
  it("uses a true minus sign and an explicit plus", () => {
    expect(signedCycles(-4.2)).toBe("−4.2");
    expect(signedCycles(7)).toBe("+7");
    expect(signedCycles(0.01)).toBe("0");
  });
});

describe("time formatting", () => {
  const iso = "2027-03-11T13:25:00Z";

  it("formats UTC timestamps with a Z suffix", () => {
    expect(utcTime(iso)).toBe("11 Mar 13:25Z");
    expect(utcDay(iso)).toBe("Thu 11 Mar");
  });

  it("renders local time in the airport zone, across the DST change", () => {
    expect(localTime(iso, "America/Chicago", "CST")).toBe("Thu 07:25 CST");
    // 15 Mar is after the 14 Mar 2027 US DST switch: Chicago is UTC−5.
    expect(localTime("2027-03-15T13:25:00Z", "America/Chicago", "CDT")).toBe("Mon 08:25 CDT");
  });
});

describe("labels", () => {
  it("formats percent and sensor names", () => {
    expect(percent(0.9)).toBe("90.0%");
    expect(percent(0.775, 0)).toBe("78%");
    expect(sensorLabel("sensor_11")).toBe("S11");
  });
});

describe("zonedTime", () => {
  it("derives the abbreviation for the instant", () => {
    expect(zonedTime("2027-03-13T13:00:00Z", "America/Denver")).toBe("Sat 06:00 MST");
    expect(zonedTime("2027-03-15T13:00:00Z", "America/Denver")).toBe("Mon 07:00 MDT");
    expect(zonedTime("2027-03-15T13:00:00Z", "America/Phoenix")).toBe("Mon 06:00 MST");
  });
});
