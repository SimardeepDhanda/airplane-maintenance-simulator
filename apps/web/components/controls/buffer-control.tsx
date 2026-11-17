"use client";

import { useState } from "react";

/** Planning buffer in cycles. Commits on blur/Enter so typing doesn't refetch every keystroke. */
export function BufferControl({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  const [synced, setSynced] = useState(value);
  if (synced !== value) {
    // External change (URL navigation): adopt it. Adjusting state during render avoids an effect.
    setSynced(value);
    setDraft(String(value));
  }

  const commit = () => {
    const n = Number(draft);
    if (Number.isInteger(n) && n >= 0 && n <= 200) onChange(n);
    else setDraft(String(value));
  };

  return (
    <label
      className="text-fg-muted flex items-center gap-2 text-xs"
      title="Hypothetical planning policy: flag when lower-bound RUL minus scheduled cycles falls below this"
    >
      Buffer
      <input
        type="number"
        inputMode="numeric"
        min={0}
        max={200}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && commit()}
        className="border-line-strong bg-surface text-fg w-14 rounded-sm border px-2 py-1 text-right font-mono text-xs"
        aria-label="Planning buffer (cycles)"
      />
      <span className="text-fg-subtle">cyc</span>
    </label>
  );
}
