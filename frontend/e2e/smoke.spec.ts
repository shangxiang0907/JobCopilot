import { expect, test } from "@playwright/test"

/**
 * Smoke journey through the deployed stack: Keycloak OIDC login and every
 * core page rendering real data from the backend. Deliberately avoids
 * LLM-dependent assertions (no real DASHSCOPE key in CI) and drag-and-drop
 * (flaky under WebKit/CI) — this is a "is the system wired together" net,
 * not a feature test suite.
 *
 * Requires the test user to exist in the Keycloak realm
 * (CI: infra/scripts/create-test-user.sh; local dev already has it).
 */

const USER = process.env.E2E_USER ?? "testuser@example.com"
const PASSWORD = process.env.E2E_PASSWORD ?? "Test1234!"

test.describe.configure({ mode: "serial" })

test("unauthenticated visit redirects to Keycloak login", async ({ page }) => {
  await page.goto("/")
  await page.waitForURL(/\/realms\/jobcopilot\/protocol\/openid-connect\//)
  await expect(page.locator("#username")).toBeVisible()
})

test("login lands on the dashboard", async ({ page }) => {
  await page.goto("/")
  await page.waitForURL(/openid-connect/)
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("#kc-login")

  await page.waitForURL((url) => url.origin !== "http://localhost:8080", {
    timeout: 30_000,
  })
  await expect(
    page.getByRole("heading", { name: "Job Applications" })
  ).toBeVisible({ timeout: 30_000 })
})

test("core pages render behind auth", async ({ page }) => {
  // Serial mode reuses nothing between tests — log in again in this context.
  await page.goto("/")
  await page.waitForURL(/openid-connect/)
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("#kc-login")
  await expect(
    page.getByRole("heading", { name: "Job Applications" })
  ).toBeVisible({ timeout: 20_000 })

  await page.getByRole("link", { name: "Jobs" }).click()
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible({
    timeout: 15_000,
  })

  await page.getByRole("link", { name: "Discovery" }).click()
  await expect(page.getByRole("heading", { name: "Discovery" })).toBeVisible({
    timeout: 15_000,
  })

  await page.getByRole("link", { name: "Profile" }).click()
  await expect(page.getByRole("heading", { name: "Profile Settings" })).toBeVisible({
    timeout: 15_000,
  })

  // AI assistant panel opens and its input is ready (no message sent — that
  // needs a real LLM key).
  await page.getByRole("button", { name: "AI Assistant" }).click()
  await expect(page.getByPlaceholder("Ask anything…")).toBeVisible()
})
