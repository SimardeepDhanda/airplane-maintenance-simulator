/** UTC midnights strictly inside (t0, t1), for day gridlines. */
export function dayStarts(t0: number, t1: number): Date[] {
  const first = new Date(t0);
  const out: Date[] = [];
  for (
    let d = Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), first.getUTCDate() + 1);
    d < t1;
    d += 86_400_000
  ) {
    out.push(new Date(d));
  }
  return out;
}

type Shift = { start_local: string; end_local: string; is_night: boolean };

function minutes(hhmm: string): number {
  const [h = "0", m = "0"] = hhmm.split(":");
  return Number(h) * 60 + Number(m);
}

function inShift(shift: Shift, minute: number): boolean {
  const s = minutes(shift.start_local);
  const e = minutes(shift.end_local);
  return s < e ? minute >= s && minute < e : minute >= s || minute < e;
}

/**
 * [start, end) epoch-ms bands when the facility runs a night shift, evaluated hourly in its
 * local time zone (so bands move with DST).
 */
export function nightBands(
  shifts: readonly Shift[],
  timeZone: string,
  t0: number,
  t1: number,
): [number, number][] {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const bands: [number, number][] = [];
  for (let t = t0; t < t1; t += 3_600_000) {
    const [h = "0", m = "0"] = fmt.format(new Date(t)).split(":");
    const minute = Number(h) * 60 + Number(m);
    const shift = shifts.find((s) => inShift(s, minute));
    const night = shift ? shift.is_night : true;
    if (!night) continue;
    const last = bands.at(-1);
    if (last && last[1] === t) last[1] = t + 3_600_000;
    else bands.push([t, t + 3_600_000]);
  }
  return bands;
}
