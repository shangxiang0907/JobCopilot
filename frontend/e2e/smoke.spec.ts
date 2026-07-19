import { expect, test, type Page } from "@playwright/test"

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

// All sidebar navigation goes through the named landmark. Page content may
// contain identically-named inline links (the dashboard onboarding empty state
// links to "discovery"), and Playwright's accessible-name matching is
// case-insensitive — an unscoped getByRole("link") is a strict-mode violation
// waiting on a data race (this exact flake failed the 2026-07-19 CD run).
const sidebarNav = (page: Page) => page.getByRole("navigation", { name: "Primary" })

test.describe.configure({ mode: "serial" })

test("unauthenticated visit redirects to Keycloak login", async ({ page }) => {
  await page.goto("/")
  await page.waitForURL(/\/realms\/jobcopilot\/protocol\/openid-connect\//)
  await expect(page.locator("#username")).toBeVisible()
  // Self-registration (v0.2) — keycloak-init must have enabled it on the realm.
  await expect(page.getByRole("link", { name: /register/i })).toBeVisible()
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

  await sidebarNav(page).getByRole("link", { name: "Jobs" }).click()
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible({
    timeout: 15_000,
  })

  await sidebarNav(page).getByRole("link", { name: "Discovery" }).click()
  await expect(page.getByRole("heading", { name: "Discovery" })).toBeVisible({
    timeout: 15_000,
  })

  await sidebarNav(page).getByRole("link", { name: "Profile" }).click()
  await expect(page.getByRole("heading", { name: "Profile Settings" })).toBeVisible({
    timeout: 15_000,
  })

  // AI assistant panel opens and its input is ready (no message sent — that
  // needs a real LLM key).
  await page.getByRole("button", { name: "AI Assistant" }).click()
  await expect(page.getByPlaceholder("Ask anything…")).toBeVisible()
})

test("admin pages render for the admin role", async ({ page }) => {
  // The test user carries realm role `admin` (create-test-user.sh), so the
  // role-gated sidebar section and both operator pages must work end-to-end
  // (JWT roles → sidebar gate → Kong admin routes → per-service endpoints).
  await page.goto("/")
  await page.waitForURL(/openid-connect/)
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("#kc-login")
  await expect(
    page.getByRole("heading", { name: "Job Applications" })
  ).toBeVisible({ timeout: 20_000 })

  await sidebarNav(page).getByRole("link", { name: "Users" }).click()
  await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible({
    timeout: 15_000,
  })
  // Real data, not just the page shell: the test user itself must be listed.
  await expect(page.getByText(USER).first()).toBeVisible({ timeout: 15_000 })

  await sidebarNav(page).getByRole("link", { name: "Usage" }).click()
  await expect(page.getByRole("heading", { name: "Usage", exact: true })).toBeVisible({
    timeout: 15_000,
  })
  // Subtitle renders this only after BOTH usage queries succeed (works for a
  // fresh stack too — zero counts still produce the "all time" summary line).
  await expect(page.getByText(/discovery runs, all time/)).toBeVisible({ timeout: 15_000 })
})

test("sign out ends the session and returns to the login screen", async ({ page }) => {
  // Exercises RP-initiated logout end-to-end: keycloak-init must have the
  // frontend origin in post.logout.redirect.uris or Keycloak shows an
  // "Invalid redirect uri" error page instead of the login form.
  await page.goto("/")
  await page.waitForURL(/openid-connect/)
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("#kc-login")
  await expect(
    page.getByRole("heading", { name: "Job Applications" })
  ).toBeVisible({ timeout: 20_000 })

  await page.getByRole("button", { name: "Sign out" }).click()

  // Landing back at the app origin, login-required kicks in → Keycloak login.
  await page.waitForURL(/\/realms\/jobcopilot\/protocol\/openid-connect\//, {
    timeout: 20_000,
  })
  await expect(page.locator("#username")).toBeVisible()
})
