import { type Application, type ApplicationStatus } from "@/lib/api"
import { JobCard } from "./JobCard"
import { Badge } from "@/components/ui/badge"

interface Props {
  status: ApplicationStatus
  label: string
  color: string
  applications: Application[]
}

export function KanbanColumn({ label, color, applications }: Props) {
  return (
    <div className={`flex flex-col w-72 rounded-xl border ${color}`}>
      {/* Column header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <span className="text-sm font-semibold">{label}</span>
        <Badge variant="secondary" className="text-xs h-5 px-2">
          {applications.length}
        </Badge>
      </div>

      {/* Cards */}
      <div className="flex flex-col gap-3 p-3 overflow-y-auto flex-1 min-h-0 max-h-[calc(100vh-12rem)]">
        {applications.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-6">No applications here</p>
        ) : (
          applications.map((app) => <JobCard key={app.id} application={app} />)
        )}
      </div>
    </div>
  )
}
