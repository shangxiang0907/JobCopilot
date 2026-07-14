// Runtime client config endpoint.
//
// Emits `window.__ENV__` as JavaScript, evaluated at REQUEST time so the same
// prebuilt image serves the correct values in every environment (12-factor:
// config is separated from the code/build). This deliberately avoids two traps:
//   • NEXT_PUBLIC_* vars — inlined into the client bundle at build time.
//   • Reading process.env inside a statically-prerendered Server Component — the
//     value is frozen at `next build`, when prod env vars do not exist yet.
//
// `force-dynamic` opts this single tiny endpoint out of Next.js 15's default GET
// caching so process.env is read on every request. Pages stay statically
// optimizable; only this config route is dynamic.
export const dynamic = "force-dynamic"

export function GET() {
  const env = {
    KEYCLOAK_URL: process.env.KEYCLOAK_PUBLIC_URL ?? "http://localhost:8080",
    KEYCLOAK_REALM: process.env.KEYCLOAK_REALM ?? "jobcopilot",
    KEYCLOAK_CLIENT_ID: process.env.KEYCLOAK_CLIENT_ID ?? "frontend",
    // Deployment mode for LLM key sourcing (ADR-007); platform hides the BYO key UI.
    LLM_KEY_MODE: process.env.LLM_KEY_MODE === "platform" ? "platform" : "byo",
  }
  return new Response(`window.__ENV__=${JSON.stringify(env)}`, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "no-store",
    },
  })
}
