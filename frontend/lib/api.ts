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
      if (kc.token) config.headers.Authorization = `Bearer ${kc.token}`
      const parsed = kc.tokenParsed
      if (parsed?.tenant_id) config.headers["X-Tenant-ID"] = parsed.tenant_id as string
      if (parsed?.sub) config.headers["X-User-ID"] = parsed.sub
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

export interface Company {
  id: string
  name: string
  website?: string
  industry?: string
  size?: string
}

export interface Job {
  id: string
  tenant_id: string
  title: string
  company: Company
  location?: string
  job_url: string
  description_raw?: string
  remote_type?: string
  employment_type?: string
  salary_range?: Record<string, unknown>
  source: string
  posted_at?: string
  discovered_at: string
}

export interface Application {
  id: string
  tenant_id: string
  user_id: string
  job_id: string
  job?: Job
  status: ApplicationStatus
  match_score?: number
  applied_at?: string
  notes?: string
  created_at: string
  updated_at: string
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

export interface JobAnalysis {
  id: string
  job_id: string
  user_id: string
  match_score?: number
  jd_structured?: Record<string, unknown>
  resume_suggestions?: Record<string, unknown>
  interview_questions?: Record<string, unknown>
  created_at: string
}
