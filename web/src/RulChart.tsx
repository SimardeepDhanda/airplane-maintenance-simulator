import type { Engine } from "./schedule";

const W = 520;
const H = 220;
const PAD = { left: 36, right: 10, top: 10, bottom: 28 };

// Predicted vs actual cycles left over the engine's history.
export default function RulChart({ engine, cap }: { engine: Engine; cap: number }) {
  const pts = engine.history;
  const maxCycle = pts[pts.length - 1].cycle;
  const x = (c: number) => PAD.left + ((c - 1) / Math.max(1, maxCycle - 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - Math.min(v, cap) / cap) * (H - PAD.top - PAD.bottom);
  const line = (key: "predicted" | "actual") =>
    pts.map((p, i) => `${i ? "L" : "M"}${x(p.cycle).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={`Cycles left for ${engine.tail}`}>
      {[0, 25, 50, 75, 100, 125].map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="grid" />
          <text x={PAD.left - 6} y={y(v) + 4} textAnchor="end">{v}</text>
        </g>
      ))}
      <text x={W - PAD.right} y={H - 6} textAnchor="end">cycle {maxCycle}</text>
      <text x={PAD.left} y={H - 6}>cycle 1</text>
      <path d={line("actual")} className="actual" />
      <path d={line("predicted")} className="predicted" />
      <g className="legend" transform={`translate(${W - 170}, ${PAD.top + 4})`}>
        <line x1={0} x2={18} y1={0} y2={0} className="predicted" />
        <text x={24} y={4}>predicted</text>
        <line x1={84} x2={102} y1={0} y2={0} className="actual" />
        <text x={108} y={4}>actual</text>
      </g>
    </svg>
  );
}
