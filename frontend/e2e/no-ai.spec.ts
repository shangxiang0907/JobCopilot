import { expect, test } from "@playwright/test"

import { loginViaLanding, sidebarNav } from "./helpers"

/**
 * No-AI mode: the executable definition of SAD ADR-008.
 *
 * The Core layer (resume / job / company libraries + the application pipeline)
 * must be complete and usable with the Agent Service STOPPED. v0.2 shipped
 * without that property — adding a job, a plain write, was only reachable
 * through the chat agent — so this suite exists to make a regression fail CI
 * instead of surfacing as "the product is down because the LLM quota ran out".
 *
 * Run it against a stack whose agent-service is stopped:
 *
 *   docker compose stop agent-service
 *   npx playwright test --project=no-ai
 *
 * `tests/contracts/test_layering_adr_008.py` proves the coupling is absent from
 * the source; this proves the product still works without the layer.
 */

// The Agent Service's own port (docker-compose publishes it on the loopback).
// Probing it directly is unambiguous: through Kong, the JWT plugin answers 401
// before the upstream is ever consulted, so a dead agent looks identical to a
// live one.
const AGENT_HEALTH_URL = process.env.E2E_AGENT_HEALTH_URL ?? "http://127.0.0.1:8013/healthz/live"

test.describe.configure({ mode: "serial" })

test("the AI layer really is down", async ({ request }) => {
  // Without this guard the whole suite would pass with the agent running and
  // prove nothing at all — the same failure mode as a lint rule that never
  // fires. Everything below is only evidence because this test passed.
  let reachable: boolean
  try {
    const response = await request.get(AGENT_HEALTH_URL, { timeout: 5_000 })
    reachable = response.ok()
  } catch {
    reachable = false // connection refused — the container is stopped
  }

  expect(
    reachable,
    `${AGENT_HEALTH_URL} answered: the Agent Service is running, so this suite ` +
      "cannot prove the Core layer works without it. Stop it first: " +
      "docker compose stop agent-service"
  ).toBe(false)
})

test("a job can be added, edited, tracked and deleted entirely by hand", async ({ page }) => {
  const stamp = Date.now()
  const title = `No-AI Engineer ${stamp}`
  const company = `NoAI Test Co ${stamp}`
  const url = `https://example.com/jobs/no-ai-${stamp}`

  await loginViaLanding(page)

  // ── Create ────────────────────────────────────────────────────────────────
  await sidebarNav(page).getByRole("link", { name: "Jobs" }).click()
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible({
    timeout: 15_000,
  })
  // The header CTA and the empty-state CTA are deliberately the same action, so
  // which one is present depends on whether the library is empty. Either opens
  // the same form.
  await page.getByRole("button", { name: "Add job" }).first().click()

  const createForm = page.getByRole("dialog")
  await createForm.getByLabel("Title").fill(title)
  await createForm.getByLabel("Company").fill(company)
  await createForm.getByLabel("Posting URL").fill(url)
  await createForm.getByLabel("Location").fill("Remote")
  await createForm.getByRole("button", { name: "Add job" }).click()
  await expect(createForm).toBeHidden({ timeout: 15_000 })
  await expect(page.getByText(title)).toBeVisible({ timeout: 15_000 })

  // ── The company library was populated by name resolution, not by AI ───────
  await sidebarNav(page).getByRole("link", { name: "Companies" }).click()
  await page.getByLabel("Search companies").fill(company)
  await expect(page.getByText(company)).toBeVisible({ timeout: 15_000 })

  // ── Edit ──────────────────────────────────────────────────────────────────
  await sidebarNav(page).getByRole("link", { name: "Jobs" }).click()
  await page.getByLabel("Search jobs").fill(title)
  await page.getByText(title).click()
  await expect(page.getByRole("heading", { name: title })).toBeVisible({ timeout: 15_000 })
  // The job is linked to the company record, so the name is a link, not text.
  await expect(page.getByRole("link", { name: company })).toBeVisible()

  await page.getByRole("button", { name: "Edit" }).click()
  const editForm = page.getByRole("dialog")
  await editForm.getByLabel("Location").fill("Berlin")
  await editForm.getByRole("button", { name: "Save changes" }).click()
  await expect(editForm).toBeHidden({ timeout: 15_000 })
  await expect(page.getByText("Berlin")).toBeVisible({ timeout: 15_000 })

  // ── Track and advance the application ─────────────────────────────────────
  // Asserted through the offered transitions rather than the status text: the
  // badge and the "move to" button share the same words, and status words also
  // occur in prose elsewhere on the card ("…which one you applied with", shown
  // only to a tenant with no resume — which is exactly what CI is). Roles and
  // legal moves are unambiguous; free text here is not.
  await page.getByRole("button", { name: "Track this job" }).click()
  const moveToApplied = page.getByRole("button", { name: "Applied" })
  await expect(moveToApplied).toBeVisible({ timeout: 15_000 })
  await moveToApplied.click()
  // Applied → its own legal successors, and no longer offered itself.
  await expect(page.getByRole("button", { name: "Interviewing" })).toBeVisible({ timeout: 15_000 })
  await expect(moveToApplied).toBeHidden()

  // It reaches the pipeline board — the Core layer's home screen.
  await sidebarNav(page).getByRole("link", { name: "Dashboard" }).click()
  await expect(page.getByText(title)).toBeVisible({ timeout: 15_000 })

  // ── Delete both, leaving the tenant as we found it ────────────────────────
  await sidebarNav(page).getByRole("link", { name: "Jobs" }).click()
  await page.getByLabel("Search jobs").fill(title)
  await page.getByText(title).click()
  await page.getByRole("button", { name: "Delete" }).click()
  const deleteJob = page.getByRole("dialog")
  await deleteJob.getByRole("button", { name: "Delete job" }).click()
  await expect(page).toHaveURL(/\/jobs$/, { timeout: 15_000 })

  await sidebarNav(page).getByRole("link", { name: "Companies" }).click()
  await page.getByLabel("Search companies").fill(company)
  await page.getByText(company).click()
  await expect(page.getByRole("heading", { name: company })).toBeVisible({ timeout: 15_000 })
  await page.getByRole("button", { name: "Delete" }).click()
  const deleteCompany = page.getByRole("dialog")
  await deleteCompany.getByRole("button", { name: "Delete company" }).click()
  await expect(page).toHaveURL(/\/companies$/, { timeout: 15_000 })
})

test("every Core page renders with the AI layer stopped", async ({ page }) => {
  await loginViaLanding(page)

  for (const [link, heading] of [
    ["Jobs", "Jobs"],
    ["Companies", "Companies"],
    ["Discovery", "Discovery"],
    ["Profile", "Profile Settings"],
    ["Dashboard", "Job Applications"],
  ] as const) {
    await sidebarNav(page).getByRole("link", { name: link }).click()
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible({
      timeout: 15_000,
    })
  }
})

test("the AI panel reports the outage instead of failing silently", async ({ page }) => {
  // The AI layer being down must be VISIBLE (CLAUDE.md, "No Silent Degradation")
  // and must not take the page with it — the sidebar still navigates afterwards.
  await loginViaLanding(page)
  await page.getByRole("button", { name: "AI Assistant" }).click()

  const panel = page.getByRole("region", { name: "AI Assistant" })
  const input = panel.getByPlaceholder("Ask anything…")
  await expect(input).toBeVisible()
  await input.fill("Is anyone there?")
  await input.press("Enter")

  // Scoped to the panel: Next.js keeps a route announcer with role=alert in
  // every page, so an unscoped alert lookup is a strict-mode violation.
  await expect(panel.getByRole("alert")).toBeVisible({ timeout: 30_000 })

  await sidebarNav(page).getByRole("link", { name: "Jobs" }).click()
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible({
    timeout: 15_000,
  })
})
