import { z } from "zod";

// NEXT_PUBLIC_* values are inlined at build time, so they must be referenced literally.
const parsed = z.url({ protocol: /^https?$/ }).safeParse(process.env.NEXT_PUBLIC_API_URL);

if (!parsed.success) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is missing or not an http(s) URL. Copy .env.example to .env at the repo root.",
  );
}

export const API_URL = parsed.data.replace(/\/+$/, "");
