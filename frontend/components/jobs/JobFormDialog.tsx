"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { apiErrorMessage, type Job } from "@/lib/api";
import { Button } from "@/components/ui/button";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

/** Mirrors JOB_TYPES in services/job/.../schemas/job.py — change them together. */
export const JOB_TYPE_OPTIONS = [
  { value: "full_time", label: "Full-time" },
  { value: "part_time", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
  { value: "remote", label: "Remote" },
] as const;

// Radix Select has no "no value" item, and an empty string is not a valid item
// value, so unset is carried by this sentinel and translated back to null.
const NO_JOB_TYPE = "__none__";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Omit to create; pass a job to edit it. */
  job?: Job;
  onSaved?: (job: Job) => void;
}

interface FormState {
  title: string;
  company_name: string;
  url: string;
  location: string;
  job_type: string;
  salary_min: string;
  salary_max: string;
  raw_jd: string;
}

const EMPTY: FormState = {
  title: "",
  company_name: "",
  url: "",
  location: "",
  job_type: NO_JOB_TYPE,
  salary_min: "",
  salary_max: "",
  raw_jd: "",
};

function toForm(job?: Job): FormState {
  if (!job) return EMPTY;
  return {
    title: job.title,
    company_name: job.company_name,
    url: job.url,
    location: job.location ?? "",
    job_type: job.job_type ?? NO_JOB_TYPE,
    salary_min: job.salary_min?.toString() ?? "",
    salary_max: job.salary_max?.toString() ?? "",
    raw_jd: job.raw_jd ?? "",
  };
}

/** Empty means "clear it" — an explicit null, never an omitted key (see the API). */
function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : null;
}

export function JobFormDialog({ open, onOpenChange, job, onSaved }: Props) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(() => toForm(job));
  const isEdit = job !== undefined;

  useEffect(() => {
    if (open) setForm(toForm(job));
  }, [open, job]);

  const save = useMutation({
    mutationFn: async (): Promise<Job> => {
      const common = {
        title: form.title.trim(),
        company_name: form.company_name.trim(),
        url: form.url.trim(),
        location: optionalText(form.location),
        job_type: form.job_type === NO_JOB_TYPE ? null : form.job_type,
        salary_min: optionalNumber(form.salary_min),
        salary_max: optionalNumber(form.salary_max),
        raw_jd: optionalText(form.raw_jd),
      };
      const response = isEdit
        ? await api.patch<Job>(`/v1/jobs/${job.job_id}`, common)
        : // source=manual marks this as hand-entered rather than crawled, which
          // is what makes the job library's provenance badges meaningful.
          await api.post<Job>("/v1/jobs", { ...common, source: "manual" });
      return response.data;
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job", saved.job_id] });
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      onOpenChange(false);
      onSaved?.(saved);
    },
  });

  const set =
    (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const canSubmit =
    form.title.trim() !== "" && form.company_name.trim() !== "" && form.url.trim() !== "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit job" : "Add job"}</DialogTitle>
          <DialogDescription>
            Type or paste the posting yourself. No AI involved — this always works.
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
            <Label htmlFor="job-title">Title</Label>
            <Input
              id="job-title"
              required
              value={form.title}
              onChange={set("title")}
              placeholder="Senior Backend Engineer"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="job-company">Company</Label>
              <Input
                id="job-company"
                required
                value={form.company_name}
                onChange={set("company_name")}
                placeholder="Acme Corp"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="job-location">Location</Label>
              <Input
                id="job-location"
                value={form.location}
                onChange={set("location")}
                placeholder="Berlin / Remote"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="job-url">Posting URL</Label>
            <Input
              id="job-url"
              type="url"
              required
              value={form.url}
              onChange={set("url")}
              placeholder="https://example.com/jobs/123"
            />
            <p className="text-xs text-muted-foreground">
              Used to recognise the same posting across sources, so it must be unique.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="job-type">Type</Label>
              <Select
                value={form.job_type}
                onValueChange={(value) => setForm((f) => ({ ...f, job_type: value }))}
              >
                <SelectTrigger id="job-type" aria-label="Job type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_JOB_TYPE}>Not specified</SelectItem>
                  {JOB_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="job-salary-min">Salary min</Label>
              <Input
                id="job-salary-min"
                type="number"
                inputMode="numeric"
                value={form.salary_min}
                onChange={set("salary_min")}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="job-salary-max">Salary max</Label>
              <Input
                id="job-salary-max"
                type="number"
                inputMode="numeric"
                value={form.salary_max}
                onChange={set("salary_max")}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="job-jd">Job description</Label>
            <Textarea
              id="job-jd"
              rows={8}
              value={form.raw_jd}
              onChange={set("raw_jd")}
              placeholder="Paste the full job description here…"
            />
          </div>

          {save.isError && (
            <p className="text-sm text-destructive">
              {apiErrorMessage(save.error, "Could not save the job. Please try again.")}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending || !canSubmit}>
              {save.isPending ? "Saving…" : isEdit ? "Save changes" : "Add job"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
