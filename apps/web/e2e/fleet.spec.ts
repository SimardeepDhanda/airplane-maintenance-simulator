import { expect, type APIRequestContext, type Page, test } from "@playwright/test";

// Runs against the seeded demo database. Expected values come from the live API rather than
// being hard-coded, so the suite stays valid when the model artifact is retrained.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Summary = {
  engines: number;
  flights: number;
  status_counts: { ok: number; review: number; critical: number };
};
type EnginePage = {
  total: number;
  items: { id: string; aircraft_id: string; planning: { status: string } }[];
};

// Next.js mounts its own empty role="alert" route announcer; match ours only.
const alert = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');

async function api<T>(request: APIRequestContext, path: string): Promise<T> {
  const response = await request.get(`${API}${path}`);
  expect(response.ok(), `${path} -> ${response.status()}`).toBeTruthy();
  return (await response.json()) as T;
}

test.describe("overview", () => {
  test("status counts match the API", async ({ page, request }) => {
    const summary = await api<Summary>(request, "/api/v1/fleet/summary");
    await page.goto("/overview");
    const counts = page.getByLabel("Planning status counts");
    for (const [status, label] of [
      ["critical", "Critical"],
      ["review", "Review"],
      ["ok", "OK"],
    ] as const) {
      await expect(counts).toContainText(`${summary.status_counts[status]}${label}`);
    }
    await expect(page.getByText(`${summary.flights} legs`)).toBeVisible();
    await expect(
      page.getByRole("figure", { name: "Lower-bound RUL against scheduled cycles per engine" }),
    ).toBeVisible();
  });

  test("buffer change is kept in the URL and re-plans", async ({ page, request }) => {
    const wide = await api<Summary>(request, "/api/v1/fleet/summary?buffer=60");
    await page.goto("/overview");
    const buffer = page.getByLabel("Planning buffer (cycles)");
    await buffer.fill("60");
    await buffer.press("Enter");
    await expect(page).toHaveURL(/buffer=60/);
    await expect(page.getByLabel("Planning status counts")).toContainText(
      `${wide.status_counts.review}Review`,
    );
    // The buffer follows navigation.
    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Engines", exact: true })
      .click();
    await expect(page).toHaveURL(/\/engines\?buffer=60/);
  });

  test("invalid buffer input is rejected", async ({ page }) => {
    await page.goto("/overview");
    const buffer = page.getByLabel("Planning buffer (cycles)");
    await buffer.fill("-5");
    await buffer.press("Enter");
    await expect(buffer).toHaveValue("10");
    await expect(page).not.toHaveURL(/buffer=/);
  });
});

test.describe("engines", () => {
  test("status filter and station filter narrow the table and persist in the URL", async ({
    page,
    request,
  }) => {
    const critical = await api<EnginePage>(request, "/api/v1/engines?status=critical");
    await page.goto("/engines");
    await page.getByRole("radio", { name: "Critical" }).click();
    await expect(page).toHaveURL(/status=critical/);
    await expect(page.getByText(`${critical.total} engines`)).toBeVisible();
    await expect(page.locator("tbody tr")).toHaveCount(critical.total);

    await page.reload();
    await expect(page.getByRole("radio", { name: "Critical" })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    const den = await api<EnginePage>(request, "/api/v1/engines?status=critical&station=DEN");
    await page.getByLabel("Station").selectOption("DEN");
    await expect(page).toHaveURL(/station=DEN/);
    await expect(page.locator("tbody tr")).toHaveCount(den.total);
  });

  test("column sort toggles order", async ({ page, request }) => {
    const byRul = await api<EnginePage>(request, "/api/v1/engines?sort=rul_point&order=desc");
    await page.goto("/engines");
    const header = page.getByRole("columnheader", { name: /RUL est/ });
    await header.getByRole("button").click();
    await expect(page).toHaveURL(/sort=rul_point/);
    await header.getByRole("button").click();
    await expect(page).toHaveURL(/order=desc/);
    await expect(header).toHaveAttribute("aria-sort", "descending");
    await expect(page.locator("tbody tr").first()).toContainText(byRul.items[0]!.id);
  });

  test("row opens the engine detail", async ({ page, request }) => {
    const first = (await api<EnginePage>(request, "/api/v1/engines?sort=conservative_margin"))
      .items[0]!;
    await page.goto("/engines");
    await page.getByRole("link", { name: first.id, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/engines/${first.id}$`));
    await expect(page.getByRole("heading", { level: 1, name: first.id })).toBeVisible();
  });
});

test.describe("engine detail", () => {
  test("shows prediction chart, sensors, provenance and legs", async ({ page, request }) => {
    const first = (await api<EnginePage>(request, "/api/v1/engines?sort=conservative_margin"))
      .items[0]!;
    await page.goto(`/engines/${first.id}`);
    await expect(
      page.getByRole("figure", { name: "Predicted RUL by cycle with scheduled consumption" }),
    ).toBeVisible();
    await expect(page.getByText("NASA C-MAPSS FD001 test unit")).toBeVisible();

    // Sensor toggles add and remove small multiples.
    const sensors = page.getByRole("group", { name: "Sensors shown" });
    const pressed = sensors.locator('button[aria-pressed="true"]');
    const before = await pressed.count();
    await sensors.locator('button[aria-pressed="false"]').first().click();
    await expect(pressed).toHaveCount(before + 1);
    await expect(page.locator('figure[aria-label$=" by cycle"]')).toHaveCount(before + 1);

    // A leg links to the flight schedule with that leg selected.
    const leg = page.getByRole("region", { name: "Scheduled legs" }).getByRole("link").nth(1);
    await leg.click();
    await expect(page).toHaveURL(new RegExp(`/flights\\?aircraft=${first.aircraft_id}&flight=`));
    await expect(page.locator('tr[aria-selected="true"]')).toHaveCount(1);
    await expect(page.locator('tr[aria-selected="true"]')).toBeInViewport();
  });

  test("unknown engine shows the API error", async ({ page }) => {
    await page.goto("/engines/ENG-000");
    await expect(alert(page)).toContainText("No engine 'ENG-000'");
    await expect(alert(page)).toContainText("engine_not_found");
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
  });
});

test.describe("flights", () => {
  test("whole horizon is loaded and timeline bars select legs", async ({ page, request }) => {
    const summary = await api<Summary>(request, "/api/v1/fleet/summary");
    await page.goto("/flights");
    await expect(page.getByText(`${summary.flights} legs`, { exact: true })).toBeVisible();

    const timeline = page.getByRole("figure", { name: "Aircraft rotations" });
    const bar = timeline.getByRole("button").first();
    await bar.click();
    await expect(page).toHaveURL(/flight=/);
    await expect(bar).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('tr[aria-selected="true"]')).toHaveCount(1);

    // Clicking again clears the selection.
    await bar.click();
    await expect(page).not.toHaveURL(/flight=/);
  });

  test("filters compose and the flagged filter matches the API", async ({ page, request }) => {
    const flagged = await api<{ total: number }>(request, "/api/v1/flights?flagged=true");
    await page.goto("/flights");
    // Controlled by the URL, so the box flips once the route updates.
    await page.getByLabel("Flagged only").click();
    await expect(page.getByLabel("Flagged only")).toBeChecked();
    await expect(page).toHaveURL(/flagged=1/);
    await expect(page.getByText(`${flagged.total} legs`, { exact: true })).toBeVisible();

    await page.getByLabel("Day (UTC)").selectOption({ index: 1 });
    await expect(page).toHaveURL(/day=\d{4}-\d{2}-\d{2}/);
    await expect(page.getByLabel("Flagged only")).toBeChecked();
  });

  test("leg rows are keyboard selectable", async ({ page }) => {
    await page.goto("/flights?aircraft=801");
    const select = page.getByRole("button", { name: /^Select / }).first();
    await select.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/flight=/);
    await expect(select).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("methodology", () => {
  test("shows measured metrics for the active model", async ({ page, request }) => {
    const metrics = await api<{
      model: { version: string };
      test: { comparison: { selected: boolean; last_cycle: { rmse: number } }[] };
    }>(request, "/api/v1/models/metrics");
    const selected = metrics.test.comparison.find((r) => r.selected)!;
    await page.goto("/methodology");
    await expect(page.getByText(metrics.model.version).first()).toBeVisible();
    await expect(page.getByRole("row", { name: /selected/ })).toContainText(
      selected.last_cycle.rmse.toFixed(2),
    );
    await expect(
      page.getByRole("figure", { name: "Predicted versus true RUL on official test engines" }),
    ).toBeVisible();
  });
});

test.describe("failure states", () => {
  test("unreachable API shows an error with retry", async ({ page }) => {
    await page.route(`${API}/api/v1/**`, (route) => route.abort("connectionrefused"));
    await page.goto("/engines");
    await expect(alert(page)).toContainText("API unreachable", { timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  });

  test("unseeded database explains how to seed", async ({ page }) => {
    await page.route(`${API}/api/v1/**`, (route) =>
      route.fulfill({
        status: 503,
        json: { error: { code: "not_seeded", message: "Demo data not loaded" } },
      }),
    );
    await page.goto("/overview");
    await expect(alert(page).first()).toContainText("No demo data", {
      timeout: 15_000,
    });
  });
});

test("data pages have no horizontal overflow", async ({ page, request }) => {
  const first = (await api<EnginePage>(request, "/api/v1/engines")).items[0]!;
  for (const path of [
    "/overview",
    "/engines",
    `/engines/${first.id}`,
    "/flights",
    "/methodology",
  ]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
