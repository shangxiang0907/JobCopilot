"use client"

import { useQuery } from "@tanstack/react-query"
import api from "@/lib/api"

interface AiUsage {
  user_id: string
  total_analyses: number
  analyses_this_month: number
  last_activity: string | null
}

interface CrawlUsage {
  user_id: string
  total_runs: number
  runs_this_month: number
  jobs_discovered: number
  last_run: string | null
}

export default function AdminUsagePage() {
  const ai = useQuery({
    queryKey: ["admin-usage-ai"],
    queryFn: () =>
      api
        .get("/v1/admin/usage/ai")
        .then((r) => r.data as { users: AiUsage[]; total_analyses: number }),
  })
  const crawls = useQuery({
    queryKey: ["admin-usage-crawls"],
    queryFn: () =>
      api
        .get("/v1/admin/usage/crawls")
        .then((r) => r.data as { users: CrawlUsage[]; total_runs: number }),
  })

  // Merge the two per-user tables on user_id for a single overview row.
  const crawlByUser = new Map((crawls.data?.users ?? []).map((u) => [u.user_id, u]))
  const aiByUser = new Map((ai.data?.users ?? []).map((u) => [u.user_id, u]))
  const userIds = Array.from(new Set([...aiByUser.keys(), ...crawlByUser.keys()]))

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="px-6 py-4 border-b shrink-0">
        <h1 className="text-2xl font-semibold">Usage</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {ai.data && crawls.data
            ? `${ai.data.total_analyses} AI analyses · ${crawls.data.total_runs} discovery runs, all time`
            : "Per-user AI and crawl consumption"}
        </p>
      </div>

      <div className="flex-1 p-6">
        {ai.isError || crawls.isError ? (
          <p className="text-sm text-destructive">
            Failed to load usage — admin role required.
          </p>
        ) : ai.isLoading || crawls.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading usage…</p>
        ) : userIds.length === 0 ? (
          <p className="text-sm text-muted-foreground">No usage recorded yet.</p>
        ) : (
          <table className="w-full max-w-4xl text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="py-2 pr-4 font-medium">User</th>
                <th className="py-2 pr-4 font-medium">AI analyses (month / total)</th>
                <th className="py-2 pr-4 font-medium">Crawl runs (month / total)</th>
                <th className="py-2 pr-4 font-medium">Jobs discovered</th>
                <th className="py-2 font-medium">Last activity</th>
              </tr>
            </thead>
            <tbody>
              {userIds.map((id) => {
                const a = aiByUser.get(id)
                const c = crawlByUser.get(id)
                const last = [a?.last_activity, c?.last_run]
                  .filter((d): d is string => Boolean(d))
                  .sort()
                  .pop()
                return (
                  <tr key={id} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-mono text-xs">{id.slice(0, 8)}…</td>
                    <td className="py-2 pr-4">
                      {a ? `${a.analyses_this_month} / ${a.total_analyses}` : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {c ? `${c.runs_this_month} / ${c.total_runs}` : "—"}
                    </td>
                    <td className="py-2 pr-4">{c?.jobs_discovered ?? "—"}</td>
                    <td className="py-2 text-muted-foreground">
                      {last ? new Date(last).toLocaleString() : "—"}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
