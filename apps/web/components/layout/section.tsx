import type { ReactNode } from "react";

/** Compact titled region. Not a card: a hairline rule and a small label. */
export function Section({
  title,
  aside,
  children,
  className = "",
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`min-w-0 ${className}`} aria-label={title}>
      <div className="border-line mb-2 flex items-baseline justify-between gap-3 border-b pb-1.5">
        <h2 className="text-fg-muted text-xs font-medium tracking-wide uppercase">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
