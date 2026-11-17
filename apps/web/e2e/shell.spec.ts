import { expect, test } from "@playwright/test";

const SECTIONS = [
  { link: "Overview", path: "/overview", heading: "Fleet health" },
  { link: "Engines", path: "/engines", heading: "Engines" },
  { link: "Flights", path: "/flights", heading: "Flight schedule" },
  { link: "Maintenance", path: "/maintenance", heading: "Maintenance planning" },
  { link: "Scenarios", path: "/scenarios", heading: "Scenarios" },
  { link: "Methodology", path: "/methodology", heading: "Methodology" },
];

test("root redirects to overview inside the app shell", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("heading", { level: 1, name: "Fleet health" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Simulation" })).toBeVisible();
});

test("every primary nav link routes to its section", async ({ page }) => {
  await page.goto("/overview");
  const nav = page.getByRole("navigation", { name: "Primary" });
  for (const section of SECTIONS) {
    await nav.getByRole("link", { name: section.link, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${section.path}$`));
    await expect(page.getByRole("heading", { level: 1, name: section.heading })).toBeVisible();
    await expect(nav.getByRole("link", { name: section.link, exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
  }
});

test("status rail reports the live API as online", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByRole("status", { name: /^API v[\d.]+ online$/ })).toBeVisible();
});

test("status rail reports an unreachable API", async ({ page }) => {
  await page.route("**/health", (route) => route.abort("connectionrefused"));
  await page.goto("/overview");
  await expect(page.getByRole("status", { name: "API unreachable" })).toBeVisible({
    timeout: 15_000,
  });
});

test("status rail reports a degraded database", async ({ page }) => {
  await page.route("**/health", (route) =>
    route.fulfill({
      status: 503,
      json: { status: "degraded", database: "unavailable", version: "0.1.0" },
    }),
  );
  await page.goto("/overview");
  await expect(
    page.getByRole("status", { name: "API online, database unavailable" }),
  ).toBeVisible();
});

test("unknown routes show a not-found page with a way back", async ({ page }) => {
  const response = await page.goto("/no-such-page");
  expect(response?.status()).toBe(404);
  await page.getByRole("link", { name: "Back to overview" }).click();
  await expect(page).toHaveURL(/\/overview$/);
});

test("nav is keyboard reachable with a visible focus ring", async ({ page }) => {
  await page.goto("/overview");
  const engines = page.getByRole("navigation", { name: "Primary" }).getByRole("link", {
    name: "Engines",
    exact: true,
  });
  for (let i = 0; i < 10 && !(await engines.evaluate((el) => el === document.activeElement)); i++) {
    await page.keyboard.press("Tab");
  }
  await expect(engines).toBeFocused();
  const outline = await engines.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).toBe("solid");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/engines$/);
});

test("layout has no horizontal page overflow", async ({ page }) => {
  await page.goto("/overview");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
