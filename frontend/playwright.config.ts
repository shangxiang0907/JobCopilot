import { defineConfig } from "@playwright/test"

/**
 * E2E smoke suite. Expects the full stack to be running already
 * (locally: `cd infra && docker compose up -d`; CI: the cd.yml e2e-smoke job).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["list"], ["github"]] : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
})
