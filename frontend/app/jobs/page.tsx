"use client"

import { useState } from "react"
import Link from "next/link"
import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { Building2, MapPin, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react"
import api, { type Job, type Paginated } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

const JOB_TYPES = ["full_time", "part_time", "contract", "internship", "remote"] as const

const JOB_TYPE_LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
  remote: "Remote",
}

const PAGE_SIZE = 20

function formatDate(iso?: string | null) {
  if (!iso) return null
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function formatSalary(min?: number | null, max?: number | null) {
  if (min == null && max == null) return null
  const fmt = (n: number) => `$${n.toLocaleString("en-US")}`
  if (min != null && max != null) return `${fmt(min)} – ${fmt(max)}`
  return min != null ? `From ${fmt(min)}` : `Up to ${fmt(max!)}`
}

export default function JobsPage() {
  const [page, setPage] = useState(1)
  const [jobType, setJobType] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery<Paginated<Job>>({
    queryKey: ["jobs", page, jobType],
    queryFn: () =>
      api
        .get("/v1/jobs", {
          params: { page, size: PAGE_SIZE, ...(jobType ? { job_type: jobType } : {}) },
        })
        .then((r) => r.data),
    placeholderData: keepPreviousData,
  })

  const jobs = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const selectJobType = (t: string | null) => {
    setJobType(t)
    setPage(1)
  }

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
        <div>
          <h1 className="text-2xl font-semibold">Jobs</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total > 0 ? `${total} discovered job${total === 1 ? "" : "s"}` : "Discovered jobs"}
          </p>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-4 max-w-4xl w-full">
        {/* Job type filter */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant={jobType === null ? "default" : "outline"}
            onClick={() => selectJobType(null)}
          >
            All
          </Button>
          {JOB_TYPES.map((t) => (
            <Button
              key={t}
              size="sm"
              variant={jobType === t ? "default" : "outline"}
              onClick={() => selectJobType(t)}
            >
              {JOB_TYPE_LABELS[t]}
            </Button>
          ))}
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading jobs…</p>
        ) : error ? (
          <p className="text-sm text-destructive">Failed to load jobs.</p>
        ) : jobs.length === 0 ? (
          <div className="py-12 text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              {jobType ? "No jobs match this filter." : "No jobs discovered yet."}
            </p>
            {!jobType && (
              <p className="text-sm text-muted-foreground">
                Run a{" "}
                <Link href="/discovery" className="underline underline-offset-2">
                  discovery
                </Link>{" "}
                to start finding jobs, or ask the AI assistant.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => {
              const salary = formatSalary(job.salary_min, job.salary_max)
              const discovered = formatDate(job.discovered_at ?? job.created_at)
              return (
                <Link key={job.job_id} href={`/jobs/${job.job_id}`} className="block">
                  <Card className="cursor-pointer hover:shadow-md transition-shadow">
                    <CardContent className="p-4 space-y-2">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-semibold leading-snug">{job.title}</p>
                        <div className="flex items-center gap-2 shrink-0">
                          {job.job_type && (
                            <Badge variant="secondary">
                              {JOB_TYPE_LABELS[job.job_type] ?? job.job_type}
                            </Badge>
                          )}
                          <Badge variant="outline">{job.source}</Badge>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <Building2 className="h-3 w-3 shrink-0" />
                          {job.company_name}
                        </span>
                        {job.location && (
                          <span className="flex items-center gap-1.5">
                            <MapPin className="h-3 w-3 shrink-0" />
                            {job.location}
                          </span>
                        )}
                        {salary && <span>{salary}</span>}
                        {discovered && <span>Discovered {discovered}</span>}
                        <a
                          href={job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 hover:text-foreground"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <ExternalLink className="h-3 w-3" />
                          Posting
                        </a>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              )
            })}
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <p className="text-xs text-muted-foreground">
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-3.5 w-3.5 mr-1" />
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!data?.has_next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
