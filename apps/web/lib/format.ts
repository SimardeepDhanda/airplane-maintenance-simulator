import type { PlanningStatus } from "@/lib/api/schemas";

export const STATUS_LABEL: Record<PlanningStatus, string> = {
  critical: "Critical",
  review: "Review",
  ok: "OK",
};

/** Cycles with at most one decimal; integers shown without a decimal. */
export function cycles(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1);
}

export function signedCycles(value: number): string {
  const text = cycles(Math.abs(value));
  if (text === "0") return "0";
  return value < 0 ? `−${text}` : `+${text}`;
}

/** e.g. "Thu 06:25 CST" in the airport's own zone. */
export function localTime(iso: string, timeZone: string, abbr: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
  return `${parts.replace(",", "")} ${abbr}`;
}

/** e.g. "11 Mar 13:25Z". */
export function utcTime(iso: string): string {
  const d = new Date(iso);
  const day = d.getUTCDate();
  const month = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${day} ${month} ${hh}:${mm}Z`;
}

/** e.g. "Thu 11 Mar" (UTC calendar day). */
export function utcDay(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const weekday = d.toLocaleString("en-US", { weekday: "short", timeZone: "UTC" });
  const month = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  return `${weekday} ${d.getUTCDate()} ${month}`;
}

export function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function sensorLabel(name: string): string {
  return name.replace("sensor_", "S");
}
