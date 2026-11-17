import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// WCAG 2.1 A/AA rules on every page with real data loaded.
const PAGES = [
  "/overview",
  "/engines",
  "/engines/ENG-801",
  "/flights",
  "/maintenance",
  "/scenarios",
  "/methodology",
];

for (const path of PAGES) {
  test(`no WCAG A/AA violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const summary = results.violations.map(
      (v) => `${v.id} (${v.impact}): ${v.nodes.length} × ${v.nodes[0]?.target.join(" ")}`,
    );
    expect(summary).toEqual([]);
  });
}
