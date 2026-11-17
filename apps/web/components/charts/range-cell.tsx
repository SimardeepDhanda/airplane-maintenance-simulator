import { cycles } from "@/lib/format";

/** Inline interval: band = lower–upper, tick = point estimate, on a shared 0..max scale. */
export function RangeCell({
  point,
  lower,
  upper,
  max,
}: {
  point: number;
  lower: number;
  upper: number;
  max: number;
}) {
  const pct = (v: number) => `${(Math.min(v, max) / max) * 100}%`;
  return (
    <span
      className="flex items-center gap-2"
      title={`90% interval ${cycles(lower)}–${cycles(upper)}`}
    >
      <span className="w-9 text-right font-mono">{cycles(point)}</span>
      <span aria-hidden className="bg-line relative hidden h-2 w-24 rounded-[2px] md:block">
        <span
          className="bg-accent/30 absolute top-0 h-full"
          style={{ left: pct(lower), width: `calc(${pct(upper)} - ${pct(lower)})` }}
        />
        <span className="bg-accent absolute -top-0.5 h-3 w-0.5" style={{ left: pct(point) }} />
      </span>
    </span>
  );
}
