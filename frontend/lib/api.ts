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

export type ApplicationStatus =
  | "discovered"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "withdrawn"

// Mirrors jobcopilot_shared.schemas.common.PaginatedResponse
export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  size: number
  has_next: boolean
}

// Mirrors services/job JobResponse
export interface Job {
  job_id: string
  tenant_id: string
  company_id?: string | null
  title: string
  company_name: string
  url: string
  source: string
  raw_jd?: string | null
  analysis?: Record<string, unknown> | null
  salary_min?: number | null
  salary_max?: number | null
  location?: string | null
  job_type?: string | null
  discovered_at?: string | null
  created_at: string
  updated_at: string
}

// Mirrors services/job ApplicationJobSummary (embedded by GET /v1/applications)
export interface ApplicationJobSummary {
  job_id: string
  title: string
  company_name: string
  location?: string | null
  job_type?: string | null
  url: string
}

// Mirrors services/job ApplicationResponse
export interface Application {
  application_id: string
  user_id: string
  job_id: string
  status: ApplicationStatus
  match_score?: number | null
  resume_suggestions?: Record<string, unknown> | null
  notes?: string | null
  applied_at?: string | null
  created_at: string
  updated_at: string
  job?: ApplicationJobSummary | null
}

export interface Profile {
  id: string
  tenant_id: string
  user_id: string
  display_name?: string
  personal_info?: Record<string, unknown>
  job_preferences?: Record<string, unknown>
  has_linkedin_cookie: boolean
  has_llm_api_key: boolean
}

export interface Resume {
  id: string
  tenant_id: string
  user_id: string
  filename: string
  file_size: number
  mime_type: string
  is_active: boolean
  version: number
  created_at: string
}

// Mirrors services/agent AnalysisResponse
export interface JobAnalysis {
  analysis_id: string
  job_id: string
  user_id: string
  jd_structured?: Record<string, unknown> | null
  skills_required?: unknown[] | null
  match_score?: number | null
  resume_suggestions?: Record<string, unknown> | null
  interview_questions?: Record<string, unknown> | null
  status: string
  created_at: string
  updated_at: string
}
