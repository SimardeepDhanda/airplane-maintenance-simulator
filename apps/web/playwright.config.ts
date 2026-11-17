import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const webPort = 3000;
const apiPort = 8000;
// Set to run the suite against a deployed site instead of local servers.
const remote = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: remote ?? `http://localhost:${webPort}`,
    trace: "off",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  // Runs the real API (needs DATABASE_URL) and the production web build (`pnpm build` first).
  webServer: remote
    ? []
    : [
        {
          command: `uv run uvicorn --factory app.main:create_app --port ${apiPort}`,
          cwd: repoRoot,
          url: `http://localhost:${apiPort}/health`,
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
        {
          command: "pnpm start",
          url: `http://localhost:${webPort}`,
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
      ],
});
