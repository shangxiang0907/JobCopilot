"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, Globe, MapPin, Pencil, Trash2 } from "lucide-react";
import api, { apiErrorMessage, type Company, type Job, type Paginated } from "@/lib/api";
import { CompanyFormDialog } from "@/components/companies/CompanyFormDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const { data: company, isLoading } = useQuery<Company>({
    queryKey: ["company", id],
    queryFn: () => api.get(`/v1/companies/${id}`).then((r) => r.data),
  });

  const { data: jobs } = useQuery<Paginated<Job>>({
    queryKey: ["jobs", "by-company", id],
    queryFn: () =>
      api.get("/v1/jobs", { params: { company_id: id, size: 100 } }).then((r) => r.data),
    enabled: !!id,
  });

  const toggleBlacklist = useMutation({
    mutationFn: (next: boolean) => api.patch(`/v1/companies/${id}`, { is_blacklisted: next }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company", id] }),
  });

  const remove = useMutation({
    mutationFn: () => api.delete(`/v1/companies/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      router.push("/companies");
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Loading company…</p>
      </div>
    );
  }

  if (!company) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-muted-foreground">Company not found.</p>
        <Button variant="outline" onClick={() => router.push("/companies")}>
          Back to companies
        </Button>
      </div>
    );
  }

  const jobCount = jobs?.total ?? 0;

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex items-center gap-3 px-6 py-4 border-b shrink-0">
        <Button variant="ghost" size="icon" aria-label="Back" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold truncate">{company.name}</h1>
          <p className="text-sm text-muted-foreground">
            {jobCount} job{jobCount === 1 ? "" : "s"} tracked
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
          <Pencil className="h-3.5 w-3.5 mr-1.5" />
          Edit
        </Button>
        <Button variant="outline" size="sm" onClick={() => setConfirmingDelete(true)}>
          <Trash2 className="h-3.5 w-3.5 mr-1.5" />
          Delete
        </Button>
      </div>

      <div className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-5xl w-full">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <dl className="grid grid-cols-[7rem_1fr] gap-y-2">
                <dt className="text-muted-foreground">Industry</dt>
                <dd>{company.industry ?? <span className="text-muted-foreground">—</span>}</dd>
                <dt className="text-muted-foreground">Size</dt>
                <dd>{company.size ?? <span className="text-muted-foreground">—</span>}</dd>
                <dt className="text-muted-foreground">Website</dt>
                <dd>
                  {company.website ? (
                    <a
                      href={company.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 underline underline-offset-2"
                    >
                      <Globe className="h-3.5 w-3.5" />
                      {company.website.replace(/^https?:\/\//, "")}
                    </a>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </dd>
              </dl>
              {company.notes && (
                <div className="pt-2">
                  <p className="text-muted-foreground mb-1">Notes</p>
                  <p className="whitespace-pre-wrap">{company.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Jobs at this company</CardTitle>
            </CardHeader>
            <CardContent>
              {jobCount === 0 ? (
                <p className="text-sm text-muted-foreground">No jobs linked to this company yet.</p>
              ) : (
                <div className="space-y-2">
                  {jobs?.items.map((job) => (
                    <Link
                      key={job.job_id}
                      href={`/jobs/${job.job_id}`}
                      className="flex items-center justify-between gap-3 p-3 rounded-md border hover:bg-accent transition-colors"
                    >
                      <span className="text-sm font-medium truncate">{job.title}</span>
                      <span className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground">
                        {job.location && (
                          <span className="flex items-center gap-1">
                            <MapPin className="h-3 w-3" />
                            {job.location}
                          </span>
                        )}
                        <Badge variant="outline">{job.source}</Badge>
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Discovery</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {company.is_blacklisted
                  ? "Jobs from this company are suppressed during discovery."
                  : "Jobs from this company appear normally in discovery."}
              </p>
              <Button
                variant={company.is_blacklisted ? "outline" : "destructive"}
                size="sm"
                className="w-full"
                disabled={toggleBlacklist.isPending}
                onClick={() => toggleBlacklist.mutate(!company.is_blacklisted)}
              >
                <Ban className="h-3.5 w-3.5 mr-1.5" />
                {company.is_blacklisted ? "Remove from blacklist" : "Blacklist company"}
              </Button>
              {toggleBlacklist.isError && (
                <p className="text-sm text-destructive">
                  {apiErrorMessage(toggleBlacklist.error, "Could not update the blacklist.")}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <CompanyFormDialog open={editing} onOpenChange={setEditing} company={company} />

      <ConfirmDialog
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        title={`Delete ${company.name}?`}
        confirmLabel="Delete company"
        pending={remove.isPending}
        errorMessage={
          remove.isError ? apiErrorMessage(remove.error, "Could not delete the company.") : null
        }
        onConfirm={() => remove.mutate()}
        description={
          <>
            <p>This deletes the company record, its notes and its blacklist setting.</p>
            {jobCount > 0 && (
              <p>
                {jobCount} job{jobCount === 1 ? "" : "s"} will stay in your job library and keep
                showing “{company.name}” as the company name — only the link to this record is
                removed.
              </p>
            )}
          </>
        }
      />
    </div>
  );
}
