"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileText } from "lucide-react";
import api, {
  apiErrorMessage,
  type Application,
  type Paginated,
  type Resume,
  type ResumeSnapshot,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// Radix Select cannot carry an empty value, so "not recorded" travels as this
// sentinel and is translated back to a null binding on the wire.
const NOT_RECORDED = "__none__";

/** The identity the Job Service stores alongside resume_id (it cannot look it up). */
export function snapshotOf(resume: Resume): ResumeSnapshot {
  return { file_name: resume.file_name, version: resume.version, label: resume.label ?? null };
}

export function resumeDisplayName(resume: Pick<Resume, "file_name" | "label" | "version">): string {
  return resume.label
    ? `${resume.label} (v${resume.version})`
    : `${resume.file_name} v${resume.version}`;
}

export function useResumes() {
  return useQuery<Resume[]>({
    queryKey: ["resumes"],
    queryFn: () => api.get<Paginated<Resume>>("/v1/resumes").then((r) => r.data.items ?? []),
  });
}

interface Props {
  application: Application;
}

export function ApplicationResumeCard({ application }: Props) {
  const queryClient = useQueryClient();
  const { data: resumes = [], isSuccess: libraryLoaded } = useResumes();

  const bind = useMutation({
    mutationFn: (resumeId: string) => {
      // resume_id and its snapshot travel together or not at all — the API
      // rejects half a binding, because an id with no snapshot becomes
      // unreadable the moment that resume is deleted.
      const body =
        resumeId === NOT_RECORDED
          ? { resume_id: null, resume_snapshot: null }
          : (() => {
              const resume = resumes.find((r) => r.resume_id === resumeId);
              if (!resume) throw new Error("That resume is no longer in your library.");
              return { resume_id: resume.resume_id, resume_snapshot: snapshotOf(resume) };
            })();
      return api.patch(`/v1/applications/${application.application_id}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: ["application-for-job", application.job_id] });
    },
  });

  // Three distinct states, deliberately not collapsed into one:
  //   null                    → the user never recorded which resume they used
  //   resolves in the library → show it normally
  //   set but unresolvable    → the resume was deleted; the snapshot is all
  //                             that is left of it, and showing "not recorded"
  //                             would erase a fact the user did record.
  // libraryLoaded gates the third case: before the query resolves, every
  // binding looks unresolvable, and flashing "deleted" at a resume that is
  // merely still loading is the same lie in the other direction.
  const boundResume = application.resume_id
    ? resumes.find((r) => r.resume_id === application.resume_id)
    : undefined;
  const wasDeleted = application.resume_id != null && libraryLoaded && !boundResume;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <FileText className="h-4 w-4" />
          Resume used
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Select
          value={application.resume_id ?? NOT_RECORDED}
          onValueChange={(value) => bind.mutate(value)}
          disabled={bind.isPending}
        >
          <SelectTrigger aria-label="Resume used for this application">
            <SelectValue placeholder="Not recorded" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NOT_RECORDED}>Not recorded</SelectItem>
            {resumes.map((resume) => (
              <SelectItem key={resume.resume_id} value={resume.resume_id}>
                {resumeDisplayName(resume)}
                {resume.is_default ? " · default" : ""}
              </SelectItem>
            ))}
            {/* A deleted resume is still the honest answer to "what did I apply
                with?", so it stays selectable-looking but disabled — dropping it
                from the list would leave the trigger rendering an empty box. */}
            {wasDeleted && application.resume_snapshot && (
              <SelectItem value={application.resume_id!} disabled>
                {resumeDisplayName({
                  file_name: application.resume_snapshot.file_name,
                  label: application.resume_snapshot.label ?? null,
                  version: application.resume_snapshot.version,
                })}{" "}
                · deleted
              </SelectItem>
            )}
          </SelectContent>
        </Select>

        {wasDeleted && application.resume_snapshot && (
          <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span>
              You applied with{" "}
              <span className="font-medium">
                {resumeDisplayName({
                  file_name: application.resume_snapshot.file_name,
                  label: application.resume_snapshot.label ?? null,
                  version: application.resume_snapshot.version,
                })}
              </span>
              , which has since been deleted from your library.
            </span>
          </p>
        )}

        {!application.resume_id && libraryLoaded && resumes.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Upload a resume on your profile to record which one you applied with.
          </p>
        )}

        {boundResume?.is_default && <Badge variant="secondary">Your default resume</Badge>}

        {bind.isError && (
          <p className="text-sm text-destructive">
            {apiErrorMessage(bind.error, "Could not update the resume for this application.")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
