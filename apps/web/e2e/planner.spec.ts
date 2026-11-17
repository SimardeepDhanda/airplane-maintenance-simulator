import { expect, type APIRequestContext, type Page, test } from "@playwright/test";

// Runs against the seeded real-data demo. Expected values come from the live API.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Plan = {
  placements: {
    job_id: string;
    engine_id: string;
    aircraft_id: string;
    bay: string;
    cancelled_flights: string[];
  }[];
  unscheduled: { job_id: string }[];
  jobs: { aircraft_id: string }[];
};

async function plan(request: APIRequestContext): Promise<Plan> {
  const r = await request.get(`${API}/api/v1/maintenance/plan`);
  expect(r.ok()).toBeTruthy();
  return (await r.json()) as Plan;
}

const alert = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');

test.describe("maintenance", () => {
  test("calendar shows the baseline plan and bars select jobs", async ({ page, request }) => {
    const p = await plan(request);
    await page.goto("/maintenance");
    const calendar = page.getByRole("figure", { name: "Maintenance calendar" });
    await expect(calendar.getByRole("button")).toHaveCount(p.placements.length);
    await expect(page.getByText(`${p.placements.length}/${p.jobs.length}`)).toBeVisible();

    const first = p.placements[0]!;
    await calendar.getByRole("button", { name: new RegExp(`^${first.engine_id} `) }).click();
    await expect(page).toHaveURL(new RegExp(`job=${first.job_id}`));
    await expect(page.getByRole("heading", { name: first.engine_id })).toBeVisible();
    await expect(page.locator('tr[aria-selected="true"]')).toHaveCount(1);

    // Facilities and spares come from the resource tables.
    await expect(page.getByRole("region", { name: "Facilities" })).toContainText("hangar");
    await expect(page.getByRole("region", { name: "Spare engines" })).toContainText("SE-DEN");
  });

  test("a cancelled leg links to the flight schedule", async ({ page, request }) => {
    const p = await plan(request);
    await page.goto("/maintenance");
    const job = p.placements.find((x) => x.cancelled_flights.length > 0)!;
    await page.getByRole("button", { name: `Select ${job.job_id}` }).click();
    const detail = page.getByRole("region", { name: job.engine_id });
    await expect(detail.getByRole("listitem").first()).toBeVisible();
    await detail.getByRole("link").first().click();
    await expect(page).toHaveURL(
      new RegExp(`/flights\\?aircraft=${job.aircraft_id}&flight=${job.cancelled_flights[0]}`),
    );
    await expect(page.locator('tr[aria-selected="true"]')).toHaveCount(1);
  });

  test("engine detail and overview link to the job", async ({ page, request }) => {
    const first = (await plan(request)).placements[0]!;
    await page.goto(`/engines/${first.engine_id}`);
    await page.getByRole("link", { name: new RegExp(first.bay) }).click();
    await expect(page).toHaveURL(new RegExp(`/maintenance\\?job=${first.job_id}`));
    await expect(page.locator('tr[aria-selected="true"]')).toContainText(first.engine_id);

    await page.goto("/overview");
    const next = page.getByRole("region", { name: "Next maintenance" });
    await expect(next.getByRole("link", { name: first.engine_id })).toBeVisible();
  });
});

test.describe("scenarios", () => {
  test("run the default week, compare, and open the optimized calendar", async ({ page }) => {
    await page.goto("/scenarios");
    await page.getByRole("button", { name: "Default week" }).click();
    await page.getByRole("button", { name: "Run scenario" }).click();
    await expect(page).toHaveURL(/\/scenarios\?id=\d+/);
    await expect(page.getByText(/CP-SAT, proven|CP-SAT, not proven optimal/)).toBeVisible({
      timeout: 30_000,
    });
    const comparison = page.getByRole("table", { name: "Baseline vs optimized" });
    await expect(comparison.getByRole("row", { name: /Simulated cost/ })).toBeVisible();
    await expect(page.getByRole("table", { name: "Job placements" })).toBeVisible();

    const id = new URL(page.url()).searchParams.get("id");
    await page.getByRole("link", { name: "Calendar" }).last().click();
    await expect(page).toHaveURL(new RegExp(`/maintenance\\?scenario=${id}`));
    await expect(page.getByRole("radio", { name: "Optimized" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await page.getByRole("radio", { name: "Baseline" }).click();
    await expect(page).toHaveURL(/method=baseline/);
    await expect(page.getByText("EDD heuristic")).toBeVisible();
  });

  test("the deliberately infeasible preset is explained, not hidden", async ({ page }) => {
    await page.goto("/scenarios");
    await page.getByRole("button", { name: "Hard threshold, DEN bay out" }).click();
    await expect(page.getByRole("radio", { name: "Hard" })).toHaveAttribute("aria-checked", "true");
    await page.getByRole("button", { name: "Run scenario" }).click();
    await expect(alert(page)).toContainText("Cannot all be on time", { timeout: 30_000 });
    await expect(page.getByText(/^Infeasible\s*CP-SAT/)).toBeVisible();
    await expect(page.getByText(/^No plan found\s*EDD heuristic/)).toBeVisible();
    await expect(page.getByRole("table", { name: "Job placements" })).toHaveCount(0);

    // Edit as new resets the form to this scenario's assumptions.
    await page.getByRole("button", { name: "Default week" }).click();
    await expect(page.getByRole("radio", { name: "Penalty" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await page.getByRole("button", { name: "Edit as new" }).click();
    await expect(page.getByRole("radio", { name: "Hard" })).toHaveAttribute("aria-checked", "true");
  });

  test("bay steppers and invalid assumptions", async ({ page, request }) => {
    const ship = (await plan(request)).jobs[0]!.aircraft_id;
    await page.goto("/scenarios");
    await page.getByRole("button", { name: "Add ORD bay" }).click();
    await expect(page.getByRole("button", { name: "Remove ORD bay" })).toBeEnabled();
    await page.getByRole("button", { name: "Remove ATL bay" }).click();
    await expect(page.getByRole("button", { name: "Remove ATL bay" })).toBeDisabled();

    // Adding a job to a ship that already has one is rejected by the API with a reason.
    await page.getByLabel("Add job: ship").selectOption(ship);
    await page.getByRole("button", { name: "Run scenario" }).click();
    await expect(alert(page)).toContainText("duplicate_job");
    await expect(page).not.toHaveURL(/id=/);
  });
});

test("planner pages have no horizontal overflow", async ({ page }) => {
  for (const path of ["/maintenance", "/scenarios"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
