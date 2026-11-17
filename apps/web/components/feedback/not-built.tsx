/** Honest placeholder for a section scheduled in a later phase. Never shows sample data. */
export function NotBuilt({ phase }: { phase: number }) {
  return (
    <div className="border-line text-fg-subtle flex h-48 items-center justify-center rounded-sm border border-dashed text-xs">
      Not built yet · Phase {phase}
    </div>
  );
}
