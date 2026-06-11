"use client"

import { useQuery } from "@tanstack/react-query"
import api, { type Application, type ApplicationStatus } from "@/lib/api"
import { KanbanColumn } from "./KanbanColumn"
import { ScrollArea } from "@/components/ui/scroll-area"

const COLUMNS: { status: ApplicationStatus; label: string; color: string }[] = [
  { status: "discovered", label: "Discovered", color: "bg-slate-100" },
  { status: "applied", label: "Applied", color: "bg-blue-50" },
  { status: "interviewing", label: "Interviewing", color: "bg-yellow-50" },
  { status: "offer", label: "Offer", color: "bg-green-50" },
  { status: "rejected", label: "Rejected", color: "bg-red-50" },
  { status: "withdrawn", label: "Withdrawn", color: "bg-gray-50" },
]

export function KanbanBoard() {
  const { data, isLoading, error } = useQuery<{ items: Application[] }>({
    queryKey: ["applications"],
    queryFn: () => api.get("/v1/applications").then((r) => r.data),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground text-sm">Loading applications…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-destructive text-sm">Failed to load applications.</p>
      </div>
    )
  }

  const applications = data?.items ?? []

  const byStatus = COLUMNS.reduce<Record<ApplicationStatus, Application[]>>(
    (acc, col) => {
      acc[col.status] = applications.filter((a) => a.status === col.status)
      return acc
    },
    {} as Record<ApplicationStatus, Application[]>
  )

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
  )
}
