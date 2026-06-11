"use client"

import { useParams, useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, ExternalLink, Star, Building2, MapPin, Briefcase } from "lucide-react"
import api, { type Job, type Application, type JobAnalysis, type ApplicationStatus } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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

const STATUS_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  discovered: ["applied", "withdrawn"],
  applied: ["interviewing", "rejected", "withdrawn"],
  interviewing: ["offer", "rejected", "withdrawn"],
  offer: ["withdrawn"],
  rejected: [],
  withdrawn: [],
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const queryClient = useQueryClient()
  const openChat = useUIStore((s) => s.openChat)

  const { data: job, isLoading: jobLoading } = useQuery<Job>({
    queryKey: ["job", id],
    queryFn: () => api.get(`/v1/jobs/${id}`).then((r) => r.data),
  })

  const { data: application } = useQuery<Application>({
    queryKey: ["application-for-job", id],
    queryFn: () =>
      api.get("/v1/applications", { params: { job_id: id } }).then((r) => r.data.items?.[0]),
    enabled: !!id,
  })

  const { data: analysis } = useQuery<JobAnalysis>({
    queryKey: ["analysis", id],
    queryFn: () => api.get(`/v1/agent/analyses/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const updateStatus = useMutation({
    mutationFn: (status: ApplicationStatus) =>
      api.patch(`/v1/applications/${application!.id}`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["applications"] })
      queryClient.invalidateQueries({ queryKey: ["application-for-job", id] })
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
          <p className="text-sm text-muted-foreground">{job.company.name}</p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <a href={job.job_url} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
            View Posting
          </a>
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
                <span className="flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5" />
                  {job.company.name}
                </span>
                {job.location && (
                  <span className="flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5" />
                    {job.location}
                  </span>
                )}
                {job.employment_type && (
                  <span className="flex items-center gap-1.5">
                    <Briefcase className="h-3.5 w-3.5" />
                    {job.employment_type}
                  </span>
                )}
                {job.remote_type && <Badge variant="secondary">{job.remote_type}</Badge>}
              </div>
              {job.description_raw && (
                <>
                  <Separator />
                  <div className="text-sm whitespace-pre-wrap text-foreground/80 max-h-96 overflow-y-auto">
                    {job.description_raw}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {analysis && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">AI Analysis</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {analysis.match_score !== undefined && (
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
                <p className="text-sm text-muted-foreground">No application yet.</p>
              )}
            </CardContent>
          </Card>

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
    </div>
  )
}
