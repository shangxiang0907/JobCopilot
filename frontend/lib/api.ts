import axios from "axios"
import { getKeycloak } from "@/lib/keycloak"

const api = axios.create({
  baseURL: typeof window !== "undefined" ? "" : (process.env.KONG_URL ?? "http://kong:8000"),
  timeout: 30_000,
})

api.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    const kc = getKeycloak()
    if (kc.authenticated) {
      await kc.updateToken(30).catch(() => kc.login())
      // Identity (sub / tenant_id) travels ONLY inside the verified JWT — backends
      // must never trust client-declared identity headers.
      if (kc.token) config.headers.Authorization = `Bearer ${kc.token}`
    }
  }
  return config
})

export default api

// ── Wire types ────────────────────────────────────────────────────────────────
// All entity types are GENERATED from the backend OpenAPI schemas — never
// hand-write them. Regenerate with `npm run gen:api-types` after running
// `uv run python scripts/export_openapi.py`; CI fails when either is stale.
import type { components as AgentComponents } from "./gen/agent"
import type { components as DiscoveryComponents } from "./gen/discovery"
import type { components as JobComponents } from "./gen/job"
import type { components as ProfileComponents } from "./gen/profile"

export type Job = JobComponents["schemas"]["JobResponse"]
export type Application = JobComponents["schemas"]["ApplicationResponse"]
export type ApplicationJobSummary = JobComponents["schemas"]["ApplicationJobSummary"]
export type ApplicationStatus = Application["status"]

export type Profile = ProfileComponents["schemas"]["ProfileResponse"]
export type Resume = ProfileComponents["schemas"]["ResumeResponse"]

export type DiscoveryConfig = DiscoveryComponents["schemas"]["DiscoveryConfigResponse"]
export type DiscoveryRun = DiscoveryComponents["schemas"]["DiscoveryRunResponse"]

export type JobAnalysis = AgentComponents["schemas"]["AnalysisResponse"]

// Mirrors jobcopilot_shared.schemas.common.PaginatedResponse (generic on items)
export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  size: number
  has_next: boolean
}
