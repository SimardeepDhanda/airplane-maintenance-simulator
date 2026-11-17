import { z } from "zod";
import { API_URL } from "@/lib/config";

export const healthSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  database: z.enum(["ok", "unavailable"]),
  version: z.string(),
});

export type Health = z.infer<typeof healthSchema>;

/** Resolves for 200 and 503 (both carry a typed body); rejects when the API is unreachable. */
export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch(`${API_URL}/health`, { signal: signal ?? null, cache: "no-store" });
  if (!response.ok && response.status !== 503) {
    throw new Error(`Health check failed: HTTP ${response.status}`);
  }
  return healthSchema.parse(await response.json());
}
