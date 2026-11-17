"use client";

import { ApiError } from "@/lib/api/client";

export function Skeleton({ className = "h-48" }: { className?: string }) {
  return <div aria-hidden className={`bg-raised/70 animate-pulse rounded-sm ${className}`} />;
}

export function Loading({ label, className }: { label: string; className?: string }) {
  return (
    <div role="status" aria-label={`Loading ${label}`}>
      <Skeleton {...(className ? { className } : {})} />
    </div>
  );
}

export function QueryError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const api = error instanceof ApiError ? error : null;
  if (api?.code === "not_seeded") {
    return (
      <div role="alert" className="border-line text-fg-muted rounded-sm border px-4 py-6 text-sm">
        <p className="text-fg font-medium">No demo data</p>
        <p className="mt-1">
          Run <code className="font-mono text-xs">make seed</code> after{" "}
          <code className="font-mono text-xs">make data</code> and{" "}
          <code className="font-mono text-xs">make pipeline</code>.
        </p>
      </div>
    );
  }
  // A 4xx (e.g. unknown engine id) won't change on retry.
  const retryable = !api || api.status === 0 || api.status >= 500;
  const message =
    api?.code === "unreachable" ? "API unreachable" : (api?.message ?? "Request failed");
  return (
    <div
      role="alert"
      className="border-crit/40 text-fg-muted flex items-center justify-between gap-4 rounded-sm border px-4 py-3 text-sm"
    >
      <span>
        <span className="text-fg font-medium">{message}</span>
        {api && api.status > 0 ? <span className="ml-2 font-mono text-xs">{api.code}</span> : null}
      </span>
      {retryable ? (
        <button
          type="button"
          onClick={onRetry}
          className="border-line-strong hover:bg-raised rounded-sm border px-2 py-1 text-xs"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-line text-fg-subtle rounded-sm border border-dashed px-4 py-8 text-center text-xs">
      {children}
    </div>
  );
}
