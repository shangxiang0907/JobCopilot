"use client"

import { useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  ExternalLink,
  Star,
  Building2,
  MapPin,
  Briefcase,
  Pencil,
  Trash2,
} from "lucide-react"
import { isAxiosError } from "axios"
import api, {
  apiErrorMessage,
  type Job,
  type Application,
  type JobAnalysis,
  type ApplicationStatus,
  type Paginated,
  type Resume,
} from "@/lib/api"
import {
  ApplicationResumeCard,
  snapshotOf,
  useResumes,
} from "@/components/jobs/ApplicationResumeCard"
import { JobFormDialog } from "@/components/jobs/JobFormDialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Separator } from "@/components/ui/separator"
import { useUIStore } from "@/lib/store"

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  discovered: "Discovered",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
}

// Mirrors VALID_TRANSITIONS in services/job models/application.py
const STATUS_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  discovered: ["applied", "withdrawn"],
  applied: ["interviewing", "rejected", "withdrawn"],
  interviewing: ["offer", "rejected", "withdrawn"],
  offer: [],
  rejected: [],
  withdrawn: [],
}

const JOB_TYPE_LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
  remote: "Remote",
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const queryClient = useQueryClient()
  const openChat = useUIStore((s) => s.openChat)
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const { data: resumes = [] } = useResumes()

  const { data: job, isLoading: jobLoading } = useQuery<Job>({
    queryKey: ["job", id],
    queryFn: () => api.get(`/v1/jobs/${id}`).then((r) => r.data),
  })

  const { data: application } = useQuery<Application | undefined>({
    queryKey: ["application-for-job", id],
    queryFn: () =>
      api
        .get<Paginated<Application>>("/v1/applications", { params: { job_id: id } })
        .then((r) => r.data.items[0]),
    enabled: !!id,
  })

  const { data: analysis, isError: analysisUnavailable } = useQuery<JobAnalysis | null>({
    queryKey: ["analysis", id],
    queryFn: () =>
      api
        .get(`/v1/agent/analyses/${id}`)
        .then((r) => r.data)
        .catch((error: unknown) => {
          // 404 is the only answer that means "this job has not been analyzed".
          // Everything else means the AI layer failed, and swallowing it into
          // `null` rendered the page exactly as if no analysis existed — the
          // user would sit there waiting for an analysis nobody is running.
          if (isAxiosError(error) && error.response?.status === 404) return null
          throw error
        }),
    enabled: !!id,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["applications"] })
    queryClient.invalidateQueries({ queryKey: ["application-for-job", id] })
  }

  const defaultResume: Resume | undefined = resumes.find((r) => r.is_default)

  const trackJob = useMutation({
    // Pre-bind the default resume so "which resume did I apply with?" is
    // answered by default (PRD §3.4). With no default the binding is left
    // genuinely absent rather than guessed at — NULL means "not recorded".
    mutationFn: () =>
      api.post("/v1/applications", {
        job_id: id,
        ...(defaultResume
          ? { resume_id: defaultResume.resume_id, resume_snapshot: snapshotOf(defaultResume) }
          : {}),
      }),
    onSuccess: invalidate,
  })

  const updateStatus = useMutation({
    mutationFn: (status: ApplicationStatus) =>
      api.patch(`/v1/applications/${application!.application_id}/status`, { status }),
    onSuccess: invalidate,
  })

  const deleteJob = useMutation({
    mutationFn: () => api.delete(`/v1/jobs/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      queryClient.invalidateQueries({ queryKey: ["applications"] })
      router.push("/jobs")
    },
  })

  if (jobLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Loading job details…</p>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-muted-foreground">Job not found.</p>
        <Button variant="outline" onClick={() => router.back()}>Go back</Button>
      </div>
    )
  }

  const nextStatuses = application ? STATUS_TRANSITIONS[application.status] : []

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex items-center gap-3 px-6 py-4 border-b shrink-0">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold truncate">{job.title}</h1>
          <p className="text-sm text-muted-foreground">{job.company_name}</p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <a href={job.url} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
            View Posting
          </a>
        </Button>
        <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
          <Pencil className="h-3.5 w-3.5 mr-1.5" />
          Edit
        </Button>
        <Button variant="outline" size="sm" onClick={() => setConfirmingDelete(true)}>
          <Trash2 className="h-3.5 w-3.5 mr-1.5" />
          Delete
        </Button>
      </div>

      <div className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: job info */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Job Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                {/* Linked to a company record when one was resolved by name;
                    plain text when the job carries a name but no link. */}
                {job.company_id ? (
                  <Link
                    href={`/companies/${job.company_id}`}
                    className="flex items-center gap-1.5 underline underline-offset-2 hover:text-foreground"
                  >
                    <Building2 className="h-3.5 w-3.5" />
                    {job.company_name}
                  </Link>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <Building2 className="h-3.5 w-3.5" />
                    {job.company_name}
                  </span>
                )}
                {job.location && (
                  <span className="flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5" />
                    {job.location}
                  </span>
                )}
                {job.job_type && (
                  <span className="flex items-center gap-1.5">
                    <Briefcase className="h-3.5 w-3.5" />
                    {JOB_TYPE_LABELS[job.job_type] ?? job.job_type}
                  </span>
                )}
                <Badge variant="secondary">{job.source}</Badge>
              </div>
              {job.raw_jd && (
                <>
                  <Separator />
                  <div className="text-sm whitespace-pre-wrap text-foreground/80 max-h-96 overflow-y-auto">
                    {job.raw_jd}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {analysisUnavailable && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">AI Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                {/* Says which of the two it is. "Nothing here" would be a lie
                    when the truth is "we could not ask". */}
                <p className="text-sm text-muted-foreground">
                  Could not load the AI analysis for this job. Everything else on this page is up
                  to date — try again later.
                </p>
              </CardContent>
            </Card>
          )}

          {analysis && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">AI Analysis</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {analysis.match_score != null && (
                  <div className="flex items-center gap-2">
                    <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                    <span className="font-semibold">{analysis.match_score}% match</span>
                  </div>
                )}
                {analysis.resume_suggestions && (
                  <div>
                    <p className="text-sm font-medium mb-1">Resume Suggestions</p>
                    <p className="text-sm text-muted-foreground">
                      {JSON.stringify(analysis.resume_suggestions, null, 2)}
                    </p>
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    openChat()
                  }}
                >
                  Ask AI about this job
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right column: status management */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Application Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {application ? (
                <>
                  <Badge className="text-sm px-3 py-1">
                    {STATUS_LABELS[application.status]}
                  </Badge>
                  {nextStatuses.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">Move to:</p>
                      {nextStatuses.map((s) => (
                        <Button
                          key={s}
                          variant="outline"
                          size="sm"
                          className="w-full justify-start"
                          disabled={updateStatus.isPending}
                          onClick={() => updateStatus.mutate(s)}
                        >
                          {STATUS_LABELS[s]}
                        </Button>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Not tracked yet. Add it to your kanban board.
                  </p>
                  <Button
                    size="sm"
                    className="w-full"
                    disabled={trackJob.isPending}
                    onClick={() => trackJob.mutate()}
                  >
                    Track this job
                  </Button>
                  {trackJob.isError && (
                    <p className="text-sm text-destructive">
                      {apiErrorMessage(trackJob.error, "Could not track this job.")}
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {application && <ApplicationResumeCard application={application} />}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">AI Assistant</CardTitle>
            </CardHeader>
            <CardContent>
              <Button className="w-full" onClick={openChat}>
                Prepare for Interview
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <JobFormDialog open={editing} onOpenChange={setEditing} job={job} />

      <ConfirmDialog
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        title={`Delete “${job.title}”?`}
        confirmLabel="Delete job"
        pending={deleteJob.isPending}
        errorMessage={
          deleteJob.isError ? apiErrorMessage(deleteJob.error, "Could not delete the job.") : null
        }
        onConfirm={() => deleteJob.mutate()}
        description={
          <>
            <p>This removes the job and its job description from your library.</p>
            {application && (
              <p>
                Its application card (currently {STATUS_LABELS[application.status].toLowerCase()})
                will lose the job it points at.
              </p>
            )}
          </>
        }
      />
    </div>
  )
}
