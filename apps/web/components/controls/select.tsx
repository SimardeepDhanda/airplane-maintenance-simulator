"use client";

export function Select({
  label,
  value,
  options,
  onChange,
  allLabel = "All",
  hideLabel = false,
}: {
  label: string;
  value: string;
  options: readonly { value: string; label: string }[];
  onChange: (value: string) => void;
  allLabel?: string;
  hideLabel?: boolean;
}) {
  return (
    <label className="text-fg-muted flex items-center gap-2 text-xs">
      {hideLabel ? <span className="sr-only">{label}</span> : label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border-line-strong bg-surface text-fg rounded-sm border px-2 py-1 text-xs"
      >
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
