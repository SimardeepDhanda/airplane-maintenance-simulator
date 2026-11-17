import type { z } from "zod";
import { API_URL } from "@/lib/config";
import { errorEnvelope } from "./schemas";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type QueryValue = string | number | boolean | null | undefined | readonly string[];

export function buildUrl(path: string, params: Record<string, QueryValue> = {}): string {
  const url = new URL(`${API_URL}${path}`);
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v));
    else url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/** GET + schema validation. Non-2xx responses become ApiError with the API's error code. */
export async function apiGet<T extends z.ZodType>(
  path: string,
  schema: T,
  params: Record<string, QueryValue> = {},
  signal?: AbortSignal,
): Promise<z.infer<T>> {
  return request(buildUrl(path, params), schema, { signal: signal ?? null });
}

export async function apiPost<T extends z.ZodType>(
  path: string,
  schema: T,
  body?: unknown,
): Promise<z.infer<T>> {
  return request(buildUrl(path), schema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

async function request<T extends z.ZodType>(
  url: string,
  schema: T,
  init: RequestInit,
): Promise<z.infer<T>> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "unreachable", "API unreachable");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = errorEnvelope.safeParse(body);
    if (parsed.success) {
      throw new ApiError(response.status, parsed.data.error.code, parsed.data.error.message);
    }
    throw new ApiError(response.status, "http_error", `HTTP ${response.status}`);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError(response.status, "schema_mismatch", "Unexpected response from API");
  }
  return parsed.data;
}
