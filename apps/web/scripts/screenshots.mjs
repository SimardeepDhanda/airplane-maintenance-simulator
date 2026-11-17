// Regenerates docs/screenshots/*.png from a running production build and seeded API.
// Usage: pnpm --filter web build && pnpm --filter web start & make api & node apps/web/scripts/screenshots.mjs
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const base = process.env.WEB_URL ?? "http://localhost:3000";
const out = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../docs/screenshots");

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();

async function shot(name, url, prepare) {
  await page.goto(base + url);
  await page.waitForLoadState("networkidle");
  if (prepare) await prepare();
  await page.waitForTimeout(400); // let charts finish their entry layout
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(name);
}

await shot("overview", "/overview");
await shot("engines", "/engines");
await shot("engine-detail", "/engines/ENG-802");
await shot("flights", "/flights?aircraft=802");
await shot("methodology", "/methodology");
await shot("maintenance", "/maintenance");

async function runPreset(preset, done) {
  await page.getByRole("button", { name: preset }).click();
  await page.getByRole("button", { name: "Run scenario" }).click();
  await page.getByText(done).first().waitFor({ timeout: 30_000 });
}
await shot("scenario-compare", "/scenarios", () => runPreset("Default week", /CP-SAT, proven/));
await shot("scenario-infeasible", "/scenarios", () =>
  runPreset("Hard threshold, DEN bay out", "Cannot all be on time"),
);

await browser.close();
