import { test, expect } from "@playwright/test";

// SPEC §6.10: het statische schema veroudert client-side mee met de klok van de bezoeker.
// De fixture zet starttijden relatief aan "nu": één game van 8 uur geleden (gisteravond),
// één TBD-rij op de dag van gisteren, één die 2 uur geleden begon (mogelijk nog bezig) en één
// van vanavond.

// MLB Stats API gemockt: Cubs @ Reds is al afgelopen, Dodgers @ Mariners nog bezig.
function statsGame(away, home, startMs, state) {
  return {
    gameDate: new Date(startMs).toISOString(),
    status: { abstractGameState: state },
    teams: { away: { team: { name: away } }, home: { team: { name: home } } },
  };
}

test.beforeEach(async ({ page }) => {
  const now = Date.now();
  const HOUR = 3600 * 1000;
  await page.route("**/statsapi.mlb.com/**", (route) =>
    route.fulfill({
      json: {
        dates: [{ games: [
          statsGame("Chicago Cubs", "Cincinnati Reds", now - 3 * HOUR, "Final"),
          statsGame("Los Angeles Dodgers", "Seattle Mariners", now - 2 * HOUR, "Live"),
        ] }],
      },
    })
  );
  await page.goto("/stale.html");
  await expect(page.locator("body")).toHaveAttribute("data-stale-pruned", "1");
});

test("stale: afgelopen wedstrijd van gisteravond verdwijnt", async ({ page }) => {
  await expect(page.locator("#row-past")).toBeHidden();
  await expect(page.locator("#row-past-tbd")).toBeHidden();
});

test("stale: dagkop zonder zichtbare rijen verdwijnt mee", async ({ page }) => {
  await expect(page.locator("#hdr-past")).toBeHidden();
  await expect(page.locator("#hdr-today")).toBeVisible();
});

test("stale: lopende en toekomstige wedstrijden blijven staan", async ({ page }) => {
  await expect(page.locator("#row-running")).toBeVisible();
  await expect(page.locator("#row-future")).toBeVisible();
});

test("stale: wedstrijd binnen het grace-window die al Final is verdwijnt", async ({ page }) => {
  await expect(page.locator("#row-finished")).toBeHidden();
  await expect(page.locator("#row-running")).toBeVisible();
});
