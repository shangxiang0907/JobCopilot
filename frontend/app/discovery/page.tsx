"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Play, Plus, Settings2, RefreshCw } from "lucide-react"
import api, { type DiscoveryConfig, type DiscoveryRun } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cookie_expired: "bg-orange-100 text-orange-800",
}
const STATUS_COLOR_FALLBACK = "bg-gray-100 text-gray-800"

export default function DiscoveryPage() {
  const queryClient = useQueryClient()
  const [keywords, setKeywords] = useState("")
  const [locations, setLocations] = useState("")
  const [showForm, setShowForm] = useState(false)

  const { data: configs = [], isLoading } = useQuery<DiscoveryConfig[]>({
    queryKey: ["discovery-configs"],
    queryFn: () => api.get("/v1/discovery/configs").then((r) => r.data.items ?? []),
  })

  const { data: runs = [] } = useQuery<DiscoveryRun[]>({
    queryKey: ["discovery-runs"],
    queryFn: () => api.get("/v1/discovery/runs").then((r) => r.data.items ?? []),
    refetchInterval: 5_000,
  })

  const createConfig = useMutation({
    mutationFn: (payload: { keywords: string[]; locations: string[] }) =>
      api.post("/v1/discovery/configs", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discovery-configs"] })
      setKeywords("")
      setLocations("")
      setShowForm(false)
    },
  })

  const triggerRun = useMutation({
    mutationFn: (configId: string) =>
      api.post("/v1/discovery/runs", { config_id: configId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discovery-runs"] }),
  })

  const handleCreate = () => {
    const kws = keywords.split(",").map((s) => s.trim()).filter(Boolean)
    const locs = locations.split(",").map((s) => s.trim()).filter(Boolean)
    if (kws.length === 0) return
    createConfig.mutate({ keywords: kws, locations: locs })
  }

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
        <div>
          <h1 className="text-2xl font-semibold">Discovery</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Configure and trigger LinkedIn job discovery
          </p>
        </div>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          New Config
        </Button>
      </div>

      <div className="flex-1 p-6 space-y-6 max-w-3xl">
        {showForm && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Settings2 className="h-4 w-4" />
                New Discovery Config
              </CardTitle>
              <CardDescription>Comma-separated keywords and locations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Keywords</Label>
                <Input
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  placeholder="Python Engineer, Backend Developer"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Locations</Label>
                <Input
                  value={locations}
                  onChange={(e) => setLocations(e.target.value)}
                  placeholder="San Francisco, Remote"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleCreate}
                  disabled={createConfig.isPending || !keywords.trim()}
                >
                  Create
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading configs…</p>
        ) : configs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No discovery configs yet. Create one to start finding jobs.
          </p>
        ) : (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Configs
            </h2>
            {configs.map((cfg) => {
              const activeRun = runs.find(
                (r) => r.config_id === cfg.config_id && r.status === "running"
              )
              return (
                <Card key={cfg.config_id}>
                  <CardContent className="flex items-center justify-between p-4">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">
                        {cfg.keywords.join(", ")}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {cfg.locations.length > 0
                          ? cfg.locations.join(", ")
                          : "Any location"}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!!activeRun || triggerRun.isPending}
                      onClick={() => triggerRun.mutate(cfg.config_id)}
                    >
                      {activeRun ? (
                        <>
                          <RefreshCw className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                          Running
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5 mr-1.5" />
                          Run Now
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}

        {runs.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Recent Runs
            </h2>
            {runs.slice(0, 10).map((run) => (
              <div
                key={run.run_id}
                className="flex items-center justify-between py-2 px-3 rounded-md border text-sm"
              >
                <span className="text-muted-foreground font-mono text-xs truncate max-w-[8rem]">
                  {run.run_id.slice(0, 8)}…
                </span>
                <span>
                  {run.jobs_discovered ?? 0} jobs found
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[run.status] ?? STATUS_COLOR_FALLBACK}`}
                >
                  {run.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
