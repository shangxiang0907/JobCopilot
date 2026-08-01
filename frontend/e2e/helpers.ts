import { expect, type Page } from "@playwright/test";

/** Shared by every E2E suite. Requires the test user to exist in the Keycloak realm
 * (CI: infra/scripts/create-test-user.sh; local dev already has it). */

export const USER = process.env.E2E_USER ?? "testuser@example.com";
export const PASSWORD = process.env.E2E_PASSWORD ?? "Test1234!";

/**
 * All sidebar navigation goes through the named landmark. Page content may
 * contain identically-named inline links (the dashboard onboarding empty state
 * links to "discovery"), and Playwright's accessible-name matching is
 * case-insensitive — an unscoped getByRole("link") is a strict-mode violation
 * waiting on a data race (this exact flake failed the 2026-07-19 CD run).
 */
export const sidebarNav = (page: Page) => page.getByRole("navigation", { name: "Primary" });

/** Landing → Keycloak → dashboard. `.first()` disambiguates the hero "Sign in"
 * from the identical header CTA. */
export async function loginViaLanding(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in" }).first().click();
  await page.waitForURL(/openid-connect/);
  await page.fill("#username", USER);
  await page.fill("#password", PASSWORD);
  await page.click("#kc-login");
  await expect(page.getByRole("heading", { name: "Job Applications" })).toBeVisible({
    timeout: 30_000,
  });
}
