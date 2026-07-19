import { readFileSync } from "node:fs"
import path from "node:path"

import { expect, test, type Page } from "@playwright/test"

/**
 * Smoke journey through the deployed stack: public landing page, Keycloak OIDC
 * login and every core page rendering real data from the backend. Deliberately
 * avoids LLM-dependent assertions (no real DASHSCOPE key in CI) and
 * drag-and-drop (flaky under WebKit/CI) — this is a "is the system wired
 * together" net, not a feature test suite.
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

// Landing → Keycloak → dashboard. `.first()` disambiguates the hero "Sign in"
// from the identical header CTA.
async function loginViaLanding(page: Page) {
  await page.goto("/")
  await page.getByRole("button", { name: "Sign in" }).first().click()
  await page.waitForURL(/openid-connect/)
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("#kc-login")
  await expect(
    page.getByRole("heading", { name: "Job Applications" })
  ).toBeVisible({ timeout: 30_000 })
}

test("landing page renders publicly without a redirect", async ({ page }) => {
  await page.goto("/")
  // Still on the app origin — anonymous visitors are NOT bounced to Keycloak.
  await expect(
    page.getByRole("heading", { name: /AI copilot for the job search/i })
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "Get started free" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Sign in" }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: /GitHub repository/i })).toBeVisible()
})

test("unauthenticated app route redirects to Keycloak login", async ({ page }) => {
  await page.goto("/dashboard")
  await page.waitForURL(/\/realms\/jobcopilot\/protocol\/openid-connect\//)
  await expect(page.locator("#username")).toBeVisible()
  // Self-registration (v0.2) — keycloak-init must have enabled it on the realm.
  await expect(page.getByRole("link", { name: /register/i })).toBeVisible()
})

test("login from the landing page lands on the dashboard", async ({ page }) => {
  await loginViaLanding(page)
})

test("core pages render behind auth", async ({ page }) => {
  // Serial mode reuses nothing between tests — log in again in this context.
  await loginViaLanding(page)

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

test("uploaded resume appears immediately, without a reload", async ({ page }) => {
  // Regression net for the read-after-write race (fixed 2026-07-20): services
  // used to commit in the session dependency's teardown, AFTER the response was
  // sent, so the refetch triggered by the upload could read the pre-upload list
  // and the new resume only appeared after a manual refresh. Mutating endpoints
  // now commit before returning — the invalidate-refetch alone MUST surface the
  // row. No page.reload() may ever be added to this test.
  await loginViaLanding(page)
  await sidebarNav(page).getByRole("link", { name: "Profile" }).click()
  await expect(page.getByRole("heading", { name: "Profile Settings" })).toBeVisible({
    timeout: 15_000,
  })

  // Unique name per run so a leftover row from an aborted earlier run can never
  // satisfy the visibility assertion.
  const fileName = `e2e-resume-${Date.now()}.pdf`
  // Await the 201 explicitly so a failure here separates "upload broke" from
  // "refetch broke" — the two halves of the read-after-write contract.
  const uploadResponse = page.waitForResponse(
    (r) => r.url().includes("/v1/resumes") && r.request().method() === "POST"
  )
  await page.setInputFiles('input[type="file"]', {
    name: fileName,
    mimeType: "application/pdf",
    buffer: readFileSync(path.join(__dirname, "fixtures", "resume.pdf")),
  })
  expect((await uploadResponse).status()).toBe(201)
  await expect(page.getByText(fileName)).toBeVisible({ timeout: 15_000 })

  // Delete it again — cleans up AND exercises the delete path's commit the same
  // way: the row must disappear from the refetched list without a reload.
  await page.getByRole("button", { name: `Delete ${fileName}` }).click()
  await expect(page.getByText(fileName)).toBeHidden({ timeout: 15_000 })
})

test("admin pages render for the admin role", async ({ page }) => {
  // The test user carries realm role `admin` (create-test-user.sh), so the
  // role-gated sidebar section and both operator pages must work end-to-end
  // (JWT roles → sidebar gate → Kong admin routes → per-service endpoints).
  await loginViaLanding(page)

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

test("sign out ends the session and returns to the landing page", async ({ page }) => {
  // Exercises RP-initiated logout end-to-end: keycloak-init must have the
  // frontend origin in post.logout.redirect.uris or Keycloak shows an
  // "Invalid redirect uri" error page instead of the landing page.
  await loginViaLanding(page)

  // Returning user revisits the landing page: silent check-sso must detect the
  // session and swap the CTAs for "Go to Dashboard" (exercises
  // silent-check-sso.html + the shared init path end-to-end).
  await page.goto("/")
  await page.getByRole("link", { name: "Go to Dashboard" }).first().click()
  await expect(
    page.getByRole("heading", { name: "Job Applications" })
  ).toBeVisible({ timeout: 20_000 })

  await page.getByRole("button", { name: "Sign out" }).click()

  // Logout redirects to the app origin, which is now the PUBLIC landing page —
  // a signed-out user must not be bounced straight back into Keycloak.
  await expect(
    page.getByRole("heading", { name: /AI copilot for the job search/i })
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole("button", { name: "Sign in" }).first()).toBeVisible()
})
