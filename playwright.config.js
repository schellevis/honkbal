import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "frontend/e2e",
  use: {
    baseURL: "http://localhost:4173",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
  webServer: {
    command: "node frontend/e2e/server.js",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
  },
});
