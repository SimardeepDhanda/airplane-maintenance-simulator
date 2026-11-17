/** Thin horizontal bars with the value at the tip. Single series, so no legend. */
export function HBars({
  rows,
  format,
  label,
}: {
  rows: readonly { key: string; label: string; value: number; note?: string }[];
  format: (v: number) => string;
  label: string;
}) {
  const max = Math.max(...rows.map((r) => r.value), 1e-9);
  return (
    <figure aria-label={label}>
      <ul className="flex flex-col gap-1">
        {rows.map((r) => (
          <li
            key={r.key}
            className="grid grid-cols-[7rem_1fr_3.5rem] items-center gap-2 text-xs"
            title={r.note}
          >
            <span className="text-fg-muted truncate font-mono">{r.label}</span>
            <span className="relative h-2.5">
              <span
                className="bg-accent/70 absolute top-0 left-0 h-full rounded-r-[3px]"
                style={{ width: `${(Math.max(r.value, 0) / max) * 100}%` }}
              />
            </span>
            <span className="text-right font-mono">{format(r.value)}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
