export type Engine = {
  tail: string;
  engine: string;
  cycles_flown: number;
  flights_per_day: number;
  predicted_rul: number;
  actual_rul: number;
  history: { cycle: number; predicted: number; actual: number }[];
};

export type Job = {
  tail: string;
  dueDay: number; // last day the plane can fly before it's under the buffer
  day: number | null; // day it goes into the hangar, null if nothing was free
  bay: number | null;
  late: boolean;
};

export const DAYS = 14;

// One flight = one engine cycle. Keep `buffer` cycles in reserve.
export function dueDay(e: Engine, buffer: number): number {
  return Math.max(0, Math.floor((e.predicted_rul - buffer) / e.flights_per_day));
}

// Earliest-due-first. Each job takes one bay for one day. We put a job as late as
// possible without missing its due day (so we don't waste engine life), and if every
// bay is taken up to then, on the first free day after it.
export function schedule(engines: Engine[], bays: number, buffer: number): Job[] {
  const used: number[] = Array(DAYS).fill(0);
  const due = engines
    .map((e) => ({ tail: e.tail, dueDay: dueDay(e, buffer) }))
    .filter((j) => j.dueDay < DAYS)
    .sort((a, b) => a.dueDay - b.dueDay || a.tail.localeCompare(b.tail));

  return due.map(({ tail, dueDay }) => {
    let day: number | null = null;
    for (let d = dueDay; d >= 0 && day === null; d--) if (used[d] < bays) day = d;
    for (let d = dueDay + 1; d < DAYS && day === null; d++) if (used[d] < bays) day = d;
    if (day === null) return { tail, dueDay, day: null, bay: null, late: true };
    const bay = used[day]++;
    return { tail, dueDay, day, bay, late: day > dueDay };
  });
}

// Flights we can't fly: the day in the hangar, plus any days a late plane sits waiting.
export function flightsLost(jobs: Job[], engines: Engine[]): number {
  const perDay = new Map(engines.map((e) => [e.tail, e.flights_per_day]));
  return jobs.reduce((sum, j) => {
    const fpd = perDay.get(j.tail) ?? 0;
    const end = j.day ?? DAYS - 1;
    return sum + fpd * (1 + Math.max(0, end - j.dueDay));
  }, 0);
}
