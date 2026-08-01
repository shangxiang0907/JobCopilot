"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileUp, MessageSquare, Plus, Search } from "lucide-react";
import api, { type Application, type ApplicationStatus } from "@/lib/api";
import { KanbanColumn } from "./KanbanColumn";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useUIStore } from "@/lib/store";

const COLUMNS: { status: ApplicationStatus; label: string; color: string }[] = [
  { status: "discovered", label: "Discovered", color: "bg-slate-100" },
  { status: "applied", label: "Applied", color: "bg-blue-50" },
  { status: "interviewing", label: "Interviewing", color: "bg-yellow-50" },
  { status: "offer", label: "Offer", color: "bg-green-50" },
  { status: "rejected", label: "Rejected", color: "bg-red-50" },
  { status: "withdrawn", label: "Withdrawn", color: "bg-gray-50" },
];

function GettingStarted() {
  const openChat = useUIStore((s) => s.openChat);

  // Ordered so every step is reachable without the AI layer (SAD ADR-008). The
  // assistant comes last and is explicitly optional: until v0.3 this empty
  // state offered the chat agent as the ONLY way to add a posting, which made a
  // plain write depend on an LLM key, the daily quota and the model behaving.
  const steps = [
    {
      icon: Plus,
      title: "1. Add a job",
      description:
        "Type or paste a posting into the form — title, company, URL and JD text. No AI needed.",
      action: (
        <Button variant="outline" size="sm" asChild>
          <Link href="/jobs">Go to Jobs</Link>
        </Button>
      ),
    },
    {
      icon: FileUp,
      title: "2. Upload your resume",
      description: "Your default resume pre-fills new applications and powers AI match scores.",
      action: (
        <Button variant="outline" size="sm" asChild>
          <Link href="/profile">Go to Profile</Link>
        </Button>
      ),
    },
    {
      icon: Search,
      title: "3. Or discover jobs automatically",
      description: "Run discovery to pull matching postings from public job boards.",
      action: (
        <Button variant="outline" size="sm" asChild>
          <Link href="/discovery">Go to Discovery</Link>
        </Button>
      ),
    },
    {
      icon: MessageSquare,
      title: "Optional: ask the assistant",
      description:
        "The AI assistant can add a posting from a URL, pasted JD text or a screenshot — it saves typing, it is never required.",
      action: (
        <Button variant="outline" size="sm" onClick={openChat}>
          Open Assistant
        </Button>
      ),
    },
  ];

  return (
    <div className="flex items-start justify-center h-full p-6 pt-16">
      <Card className="max-w-lg w-full">
        <CardHeader>
          <CardTitle>Welcome to JobCopilot</CardTitle>
          <CardDescription>
            Your board is empty — here is how to get your job search running.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {steps.map(({ icon: Icon, title, description, action }) => (
            <div key={title} className="flex gap-3">
              <Icon className="h-5 w-5 mt-0.5 text-muted-foreground shrink-0" />
              <div className="space-y-1.5">
                <p className="text-sm font-medium">{title}</p>
                <p className="text-sm text-muted-foreground">{description}</p>
                {action}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export function KanbanBoard() {
  const { data, isLoading, error } = useQuery<{ items: Application[] }>({
    queryKey: ["applications"],
    queryFn: () => api.get("/v1/applications").then((r) => r.data),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground text-sm">Loading applications…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-destructive text-sm">Failed to load applications.</p>
      </div>
    );
  }

  const applications = data?.items ?? [];

  if (applications.length === 0) {
    return <GettingStarted />;
  }

  const byStatus = COLUMNS.reduce<Record<ApplicationStatus, Application[]>>(
    (acc, col) => {
      acc[col.status] = applications.filter((a) => a.status === col.status);
      return acc;
    },
    {} as Record<ApplicationStatus, Application[]>,
  );

  return (
    <ScrollArea className="h-full w-full" orientation="horizontal">
      <div className="flex gap-4 p-6 h-full min-w-max">
        {COLUMNS.map((col) => (
          <KanbanColumn
            key={col.status}
            status={col.status}
            label={col.label}
            color={col.color}
            applications={byStatus[col.status]}
          />
        ))}
      </div>
    </ScrollArea>
  );
}
