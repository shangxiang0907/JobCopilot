"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle, Pencil, Trash2, Upload } from "lucide-react";
import api, { apiErrorMessage, type Application, type Paginated, type Resume } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** Unique within a library: several resumes commonly share one file name. */
function resumeIdentity(resume: Resume): string {
  return `${resume.label ?? resume.file_name} v${resume.version}`;
}

export function ResumeLibrary() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Resume | null>(null);
  const [deleting, setDeleting] = useState<Resume | null>(null);

  const { data: resumes = [], isSuccess } = useQuery<Resume[]>({
    queryKey: ["resumes"],
    queryFn: () => api.get<Paginated<Resume>>("/v1/resumes").then((r) => r.data.items ?? []),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["resumes"] });

  const uploadResume = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.post("/v1/resumes", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    },
    onSuccess: invalidate,
  });

  const setDefaultResume = useMutation({
    mutationFn: (id: string) => api.patch(`/v1/resumes/${id}/default`, { is_default: true }),
    onSuccess: invalidate,
  });

  const deleteResume = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/resumes/${id}`),
    onSuccess: () => {
      invalidate();
      // An application's resume binding may now be unresolvable — its card
      // needs to re-render from the snapshot rather than show a stale name.
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      setDeleting(null);
    },
  });

  // "Has resumes but none is default" is a real, reachable state: deleting the
  // default deliberately does not promote a replacement (owner decision, PRD
  // v0.3), and every AI action fails closed until the user picks one. Saying
  // nothing here would make that failure arrive far from its cause.
  const hasNoDefault = isSuccess && resumes.length > 0 && !resumes.some((r) => r.is_default);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadResume.mutate(file);
    e.target.value = "";
  };

  return (
    <>
      {/* A named landmark, so a row can be addressed without colliding with the
          same file name rendered inside an open dialog (E2E locator rule). */}
      <Card role="region" aria-label="Resume library">
        <CardHeader>
          <CardTitle className="text-base">Resume Library</CardTitle>
          <CardDescription>
            Upload PDF or DOCX. Label each one by role direction — the default is used to pre-fill
            new applications and AI actions.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {hasNoDefault && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3">
              <AlertTriangle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <p className="text-sm">
                No default resume. New applications will not record a resume, and AI actions that
                need one will fail until you set a default below.
              </p>
            </div>
          )}

          <label className="flex items-center gap-2 w-fit cursor-pointer">
            <Button variant="outline" size="sm" disabled={uploadResume.isPending} asChild>
              <span>
                <Upload className="h-3.5 w-3.5 mr-1.5" />
                {uploadResume.isPending ? "Uploading…" : "Upload Resume"}
              </span>
            </Button>
            <input type="file" accept=".pdf,.docx" className="hidden" onChange={handleFileChange} />
          </label>

          {uploadResume.isError && (
            <p className="text-sm text-destructive">
              {apiErrorMessage(
                uploadResume.error,
                "Could not read that file. Try exporting it as a text-based PDF or DOCX.",
              )}
            </p>
          )}

          {resumes.length === 0 ? (
            <p className="text-sm text-muted-foreground">No resumes uploaded yet.</p>
          ) : (
            <div className="space-y-2">
              {resumes.map((r) => (
                <div
                  key={r.resume_id}
                  className="flex items-start justify-between gap-3 p-3 rounded-md border"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    {r.is_default && (
                      <CheckCircle className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                    )}
                    <div className="min-w-0 space-y-0.5">
                      <p className="text-sm font-medium truncate">{r.label ?? r.file_name}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {r.label && <>{r.file_name} · </>}v{r.version} ·{" "}
                        {new Date(r.created_at).toLocaleDateString()}
                      </p>
                      {r.notes && (
                        <p className="text-xs text-muted-foreground line-clamp-2">{r.notes}</p>
                      )}
                      {r.is_default && (
                        <Badge variant="secondary" className="mt-1">
                          Default
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {!r.is_default && (
                      <Button
                        variant="outline"
                        size="sm"
                        aria-label={`Set ${resumeIdentity(r)} as default`}
                        onClick={() => setDefaultResume.mutate(r.resume_id)}
                      >
                        Set Default
                      </Button>
                    )}
                    {/* Accessible names carry the version: an unlabelled
                        library is several rows all called "resume.pdf", and a
                        duplicated name is both ambiguous to a screen reader and
                        a strict-mode locator collision in the E2E suite. */}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit ${resumeIdentity(r)}`}
                      onClick={() => setEditing(r)}
                    >
                      <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${resumeIdentity(r)}`}
                      onClick={() => setDeleting(r)}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {setDefaultResume.isError && (
            <p className="text-sm text-destructive">
              {apiErrorMessage(setDefaultResume.error, "Could not change the default resume.")}
            </p>
          )}
        </CardContent>
      </Card>

      <ResumeMetadataDialog resume={editing} onClose={() => setEditing(null)} />

      {deleting && (
        <DeleteResumeDialog
          resume={deleting}
          onCancel={() => setDeleting(null)}
          onConfirm={() => deleteResume.mutate(deleting.resume_id)}
          pending={deleteResume.isPending}
          errorMessage={
            deleteResume.isError
              ? apiErrorMessage(deleteResume.error, "Could not delete the resume.")
              : null
          }
        />
      )}
    </>
  );
}

function ResumeMetadataDialog({ resume, onClose }: { resume: Resume | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    setLabel(resume?.label ?? "");
    setNotes(resume?.notes ?? "");
  }, [resume]);

  const save = useMutation({
    // The API reads "" as "clear this field" and omission as "leave unchanged",
    // so an emptied box must send "" rather than be dropped from the body.
    mutationFn: () =>
      api.patch(`/v1/resumes/${resume!.resume_id}`, { label: label.trim(), notes: notes.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
      onClose();
    },
  });

  return (
    <Dialog open={resume !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit resume details</DialogTitle>
          <DialogDescription>
            The file itself cannot be changed — upload a new resume for a new version.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="resume-label">Label</Label>
            <Input
              id="resume-label"
              maxLength={100}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Backend / AI engineer / …"
            />
            <p className="text-xs text-muted-foreground">
              {resume?.file_name} · v{resume?.version}
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="resume-notes">Notes</Label>
            <Textarea
              id="resume-notes"
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="What this version emphasises, who you sent it to…"
            />
          </div>
          {save.isError && (
            <p className="text-sm text-destructive">
              {apiErrorMessage(save.error, "Could not save the resume details.")}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteResumeDialog({
  resume,
  onCancel,
  onConfirm,
  pending,
  errorMessage,
}: {
  resume: Resume;
  onCancel: () => void;
  onConfirm: () => void;
  pending: boolean;
  errorMessage: string | null;
}) {
  // How much history references this resume. Deleting is never blocked (owner
  // decision) — the applications keep a snapshot of the file name, version and
  // label — but the user deserves to know before, not after.
  const { data: references } = useQuery<Paginated<Application>>({
    queryKey: ["applications", "by-resume", resume.resume_id],
    queryFn: () =>
      api
        .get("/v1/applications", { params: { resume_id: resume.resume_id, size: 1 } })
        .then((r) => r.data),
  });
  const count = references?.total;

  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => !open && onCancel()}
      title={`Delete ${resumeIdentity(resume)}?`}
      confirmLabel="Delete resume"
      pending={pending}
      errorMessage={errorMessage}
      onConfirm={onConfirm}
      description={
        <>
          <p>The file and its saved text are removed permanently.</p>
          {count !== undefined && count > 0 && (
            <p>
              {count} application{count === 1 ? "" : "s"} recorded this resume. They stay in your
              pipeline and keep showing its name and version, but the file will no longer be there.
            </p>
          )}
          {resume.is_default && (
            <p>
              This is your default resume. No replacement is chosen automatically — until you set a
              new default, AI actions that need a resume will fail.
            </p>
          )}
        </>
      }
    />
  );
}
