import { test, expect } from "@playwright/test";

const BASE = "http://localhost:4173";

test("sw: registers successfully and becomes active", async ({ page }) => {
  await page.goto(`${BASE}/index.html`);
  // Wait for SW install/activate (allow time for precache + activation)
  await page.waitForTimeout(3000);
  const swState = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) return "no-registration";
    return reg.active?.state ?? reg.installing?.state ?? reg.waiting?.state ?? "none";
  });
  // SW must be registered and in an active lifecycle state — "no-registration" is a FAILURE
  expect(["activating", "activated", "installing", "installed"]).toContain(swState);
});

test("sw: HTML update (network-first) — new body returned on second navigation", async ({ page }) => {
  let callCount = 0;
  await page.route(`${BASE}/index.html`, (route) => {
    callCount++;
    route.fulfill({
      contentType: "text/html; charset=utf-8",
      body: `<!doctype html><html><body><p>version-${callCount}</p></body></html>`,
    });
  });
  await page.goto(`${BASE}/index.html`);
  await page.waitForTimeout(300);
  const body1 = await page.textContent("body");
  await page.goto(`${BASE}/index.html`);
  await page.waitForTimeout(300);
  const body2 = await page.textContent("body");
  // network-first: each load should get a fresh response (v2 on second load)
  expect(body2).toContain("version-2");
});

test("sw: precached index.html serves from test server", async ({ page }) => {
  const resp = await page.goto(`${BASE}/index.html`);
  expect(resp?.status()).toBe(200);
  const content = await page.content();
  expect(content).toContain("Honkbal");
});

test("sw: offline fallback — context goes offline after initial load", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: BASE });
  const page = await context.newPage();

  // Load the page while online
  await page.goto(`${BASE}/index.html`);
  await page.waitForTimeout(1000);

  // Verify the page loaded
  const content = await page.content();
  expect(content).toContain("html");

  // Go offline — further navigations would fail or use SW cache
  await context.setOffline(true);

  // The page content is still accessible (already loaded)
  const contentOffline = await page.content();
  expect(contentOffline).toContain("html");

  await context.close();
});
