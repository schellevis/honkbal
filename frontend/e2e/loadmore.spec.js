import { test, expect } from "@playwright/test";

test("loadmore: clicking button appends rows", async ({ page }) => {
  await page.goto("/avond.html");
  await page.waitForTimeout(300);
  const initialRows = await page.locator("tr[data-away-team]").count();
  const btn = page.locator(".loadmore");
  // avond.html fixture has a real loadmore button — fail if absent
  expect(await btn.count()).toBeGreaterThan(0);
  await btn.click();
  await page.waitForTimeout(500);
  const afterRows = await page.locator("tr[data-away-team]").count();
  // Two new rows from avond.tail.json should have been appended
  expect(afterRows).toBeGreaterThan(initialRows);
});

test("loadmore: offline shows error message", async ({ page }) => {
  await page.goto("/avond.html");
  await page.waitForTimeout(300);
  const btn = page.locator(".loadmore");
  expect(await btn.count()).toBeGreaterThan(0);

  // Block the tail JSON to simulate offline
  await page.route("**/*.tail.json", (route) => route.abort());
  await btn.click();
  await page.waitForTimeout(500);
  // Offline error message should be shown
  const msg = await page.locator(".loadmore-msg").textContent();
  expect(msg).toContain("offline");
});

test("loadmore: favorites highlighted on new rows", async ({ page }) => {
  // Set favorites BEFORE navigating so localStorage is pre-seeded
  await page.goto("/avond.html");
  await page.evaluate(() => {
    localStorage.setItem("honkbal-favorite-teams", JSON.stringify(["mets"]));
  });
  await page.reload();
  await page.waitForTimeout(300);
  const btn = page.locator(".loadmore");
  expect(await btn.count()).toBeGreaterThan(0);
  await btn.click();
  await page.waitForTimeout(500);
  // The mets row from avond.tail.json should be highlighted
  const favRows = await page.locator(".favorite-game").count();
  expect(favRows).toBeGreaterThanOrEqual(1);
});
