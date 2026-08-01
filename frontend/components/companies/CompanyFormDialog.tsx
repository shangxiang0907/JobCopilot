"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { apiErrorMessage, type Company } from "@/lib/api";
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
import { Textarea } from "@/components/ui/textarea";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Omit to create; pass a company to edit it. */
  company?: Company;
  onSaved?: (company: Company) => void;
}

interface FormState {
  name: string;
  industry: string;
  size: string;
  website: string;
  notes: string;
}

const EMPTY: FormState = { name: "", industry: "", size: "", website: "", notes: "" };

function toForm(company?: Company): FormState {
  if (!company) return EMPTY;
  return {
    name: company.name,
    industry: company.industry ?? "",
    size: company.size ?? "",
    website: company.website ?? "",
    notes: company.notes ?? "",
  };
}

/**
 * An empty optional field means "clear it", which the API expresses as an
 * explicit null — `undefined` would be dropped from the JSON body and read as
 * "leave unchanged", so deleting a value in the form would silently not save.
 */
function optional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function CompanyFormDialog({ open, onOpenChange, company, onSaved }: Props) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(() => toForm(company));
  const isEdit = company !== undefined;

  // Re-seed whenever the dialog opens: the component stays mounted between
  // openings, so without this an edit would show the previous company's values.
  useEffect(() => {
    if (open) setForm(toForm(company));
  }, [open, company]);

  const save = useMutation({
    mutationFn: async (): Promise<Company> => {
      const body = {
        name: form.name.trim(),
        industry: optional(form.industry),
        size: optional(form.size),
        website: optional(form.website),
        notes: optional(form.notes),
      };
      const response = isEdit
        ? await api.patch<Company>(`/v1/companies/${company.company_id}`, body)
        : await api.post<Company>("/v1/companies", body);
      return response.data;
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["company", saved.company_id] });
      onOpenChange(false);
      onSaved?.(saved);
    },
  });

  const set =
    (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit company" : "Add company"}</DialogTitle>
          <DialogDescription>
            Your own private record — notes and blacklist are never shared with other users.
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
            <Label htmlFor="company-name">Name</Label>
            <Input
              id="company-name"
              required
              value={form.name}
              onChange={set("name")}
              placeholder="Acme Corp"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="company-industry">Industry</Label>
              <Input
                id="company-industry"
                value={form.industry}
                onChange={set("industry")}
                placeholder="Fintech"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="company-size">Size</Label>
              <Input
                id="company-size"
                value={form.size}
                onChange={set("size")}
                placeholder="50-200"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="company-website">Website</Label>
            <Input
              id="company-website"
              type="url"
              value={form.website}
              onChange={set("website")}
              placeholder="https://example.com"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="company-notes">Notes</Label>
            <Textarea
              id="company-notes"
              rows={4}
              value={form.notes}
              onChange={set("notes")}
              placeholder="Team size, culture impression, compensation…"
            />
          </div>

          {save.isError && (
            <p className="text-sm text-destructive">
              {apiErrorMessage(save.error, "Could not save the company. Please try again.")}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending || form.name.trim() === ""}>
              {save.isPending ? "Saving…" : isEdit ? "Save changes" : "Add company"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
