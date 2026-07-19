"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import api from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"

interface AdminUser {
  id: string
  email: string
  first_name: string
  last_name: string
  enabled: boolean
  email_verified: boolean
  created_at_ms: number
}

export default function AdminUsersPage() {
  const queryClient = useQueryClient()
  const [q, setQ] = useState("")
  const [page, setPage] = useState(1)

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin-users", q, page],
    queryFn: () =>
      api
        .get("/v1/admin/users", { params: { q, page } })
        .then((r) => r.data as { items: AdminUser[]; total: number; has_next: boolean }),
  })

  const setEnabled = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/v1/admin/users/${id}`, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  })

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
        <div>
          <h1 className="text-2xl font-semibold">Users</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {data ? `${data.total} registered users` : "Platform user management"}
          </p>
        </div>
        <Input
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setPage(1)
          }}
          placeholder="Search by email or name…"
          className="w-64"
        />
      </div>

      <div className="flex-1 p-6">
        {isError ? (
          <p className="text-sm text-destructive">
            Failed to load users — admin role required.
          </p>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">Loading users…</p>
        ) : (
          <div className="space-y-2 max-w-3xl">
            {(data?.items ?? []).map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between rounded-lg border px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium">{u.email || u.id}</p>
                  <p className="text-xs text-muted-foreground">
                    {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"} · joined{" "}
                    {u.created_at_ms ? new Date(u.created_at_ms).toLocaleDateString() : "—"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {!u.email_verified && <Badge variant="outline">unverified</Badge>}
                  <Badge variant={u.enabled ? "default" : "destructive"}>
                    {u.enabled ? "active" : "disabled"}
                  </Badge>
                  <Button
                    size="sm"
                    variant={u.enabled ? "outline" : "default"}
                    disabled={setEnabled.isPending}
                    onClick={() => setEnabled.mutate({ id: u.id, enabled: !u.enabled })}
                  >
                    {u.enabled ? "Disable" : "Enable"}
                  </Button>
                </div>
              </div>
            ))}
            <div className="flex items-center gap-2 pt-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!data?.has_next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
