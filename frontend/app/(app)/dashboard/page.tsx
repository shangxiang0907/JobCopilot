import { KanbanBoard } from "@/components/kanban/KanbanBoard"

export default function DashboardPage() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
        <div>
          <h1 className="text-2xl font-semibold">Job Applications</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage and track all your job applications
          </p>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <KanbanBoard />
      </div>
    </div>
  )
}
