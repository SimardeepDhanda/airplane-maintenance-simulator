"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/** Read/write query-string state so filtered views are shareable links. */
export function useUrlState() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const set = useCallback(
    (updates: Record<string, string | number | null | undefined>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === undefined || value === "") next.delete(key);
        else next.set(key, String(value));
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return { params, set };
}

export function parseBuffer(raw: string | null): number | undefined {
  if (raw === null) return undefined;
  const value = Number(raw);
  return Number.isInteger(value) && value >= 0 && value <= 200 ? value : undefined;
}
