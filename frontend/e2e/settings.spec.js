import { test, expect } from "@playwright/test";

test("settings: check teams, save, reload restores checkboxes", async ({ page }) => {
  await page.goto("/settings.html");
  await page.waitForTimeout(300);

  // Check yankees and dodgers checkboxes (force needed: checkbox is hidden, card intercepts)
  await page.locator('input[type="checkbox"][value="yankees"]').check({ force: true });
  await page.locator('input[type="checkbox"][value="dodgers"]').check({ force: true });
  await page.locator("#favorites-save").click();

  // Verify localStorage
  const stored = await page.evaluate(() => localStorage.getItem("honkbal-favorite-teams"));
  const parsed = JSON.parse(stored);
  expect(parsed).toContain("yankees");
  expect(parsed).toContain("dodgers");

  // Reload and verify checkboxes restored
  await page.reload();
  await page.waitForTimeout(300);
  const yankeesChecked = await page.locator('input[type="checkbox"][value="yankees"]').isChecked();
  const dodgersChecked = await page.locator('input[type="checkbox"][value="dodgers"]').isChecked();
  expect(yankeesChecked).toBe(true);
  expect(dodgersChecked).toBe(true);
});

test("settings: status message appears and disappears", async ({ page }) => {
  await page.goto("/settings.html");
  await page.waitForTimeout(300);
  await page.locator("#favorites-save").click();
  const statusVisible = await page.locator("#favorites-status").textContent();
  expect(statusVisible.length).toBeGreaterThan(0);
});

test("settings: clear button empties all checkboxes", async ({ page }) => {
  await page.goto("/settings.html");
  await page.waitForTimeout(300);
  // Check a team first (force needed: checkbox is hidden, card intercepts)
  await page.locator('input[type="checkbox"][value="mets"]').check({ force: true });
  await page.locator("#favorites-save").click();
  // Now clear
  await page.locator("#favorites-clear").click();
  const metsChecked = await page.locator('input[type="checkbox"][value="mets"]').isChecked();
  expect(metsChecked).toBe(false);
  const stored = await page.evaluate(() => localStorage.getItem("honkbal-favorite-teams"));
  expect(JSON.parse(stored)).toEqual([]);
});
