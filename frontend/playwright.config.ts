import { defineConfig } from "@playwright/test"

/**
 * E2E suites. Both expect the stack to be running already
 * (locally: `cd infra && docker compose up -d`; CI: the cd.yml e2e-smoke job).
 *
 * The two projects need DIFFERENT stack states, so they are never run in one
 * command: `smoke` needs everything up, `no-ai` needs the Agent Service stopped
 * (SAD ADR-008). Running `no-ai` against a complete stack proves nothing, which
 * is why its first test asserts the agent is genuinely unreachable.
 *
 *   npx playwright test --project=smoke
 *   docker compose stop agent-service && npx playwright test --project=no-ai
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
  projects: [
    { name: "smoke", testMatch: /smoke\.spec\.ts/ },
    { name: "no-ai", testMatch: /no-ai\.spec\.ts/ },
  ],
})
