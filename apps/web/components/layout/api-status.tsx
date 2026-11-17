"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api/health";

type Indicator = { label: string; tone: string; detail: string };

export function ApiStatus() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
  });

  let indicator: Indicator;
  if (isPending) {
    indicator = { label: "API", tone: "bg-fg-subtle", detail: "Checking API" };
  } else if (isError) {
    indicator = { label: "API offline", tone: "bg-crit", detail: "API unreachable" };
  } else if (data.status === "ok") {
    indicator = { label: "API", tone: "bg-ok", detail: `API v${data.version} online` };
  } else {
    indicator = {
      label: "DB offline",
      tone: "bg-warn",
      detail: "API online, database unavailable",
    };
  }

  return (
    <span
      role="status"
      title={indicator.detail}
      aria-label={indicator.detail}
      className="text-fg-muted flex items-center gap-1.5 text-xs"
    >
      <span aria-hidden className={`size-1.5 rounded-full ${indicator.tone}`} />
      {indicator.label}
    </span>
  );
}
