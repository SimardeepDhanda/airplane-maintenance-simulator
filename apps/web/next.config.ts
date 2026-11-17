import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// One .env at the repository root configures both the API and the web app.
// Values already set in the environment (CI, Docker build args) take precedence.
const rootEnv = path.join(repoRoot, ".env");
if (existsSync(rootEnv)) process.loadEnvFile(rootEnv);
const apiUrl = process.env.NEXT_PUBLIC_API_URL;

const nextConfig: NextConfig = {
  // Docker builds set NEXT_OUTPUT=standalone; local `next start` uses the default output.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" as const } : {}),
  outputFileTracingRoot: repoRoot,
  poweredByHeader: false,
  reactStrictMode: true,
  // Forward explicitly: build workers do not inherit values loaded from the root .env.
  env: apiUrl ? { NEXT_PUBLIC_API_URL: apiUrl } : {},
};

export default nextConfig;
