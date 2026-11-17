import type { ReactNode } from "react";

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="flex min-h-9 items-center justify-between gap-4">
      <h1 className="text-base font-semibold tracking-tight">{title}</h1>
      {actions}
    </div>
  );
}
