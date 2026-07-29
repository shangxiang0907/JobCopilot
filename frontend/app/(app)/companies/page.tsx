"use client"

import { useState } from "react"
import Link from "next/link"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { Building2, ChevronLeft, ChevronRight, Globe, Plus, Search } from "lucide-react"
import api, { type Company, type Paginated } from "@/lib/api"
import { CompanyFormDialog } from "@/components/companies/CompanyFormDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

const PAGE_SIZE = 20

export default function CompaniesPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [creating, setCreating] = useState(false)

  const { data, isLoading, error } = useQuery<Paginated<Company>>({
    queryKey: ["companies", page, search],
    queryFn: () =>
      api
        .get("/v1/companies", {
          params: { page, size: PAGE_SIZE, ...(search.trim() ? { q: search.trim() } : {}) },
        })
        .then((r) => r.data),
    placeholderData: keepPreviousData,
  })

  const companies = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex items-center justify-between gap-4 px-6 py-4 border-b shrink-0">
        <div>
          <h1 className="text-2xl font-semibold">Companies</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total > 0 ? `${total} compan${total === 1 ? "y" : "ies"}` : "Your target company list"}
          </p>
        </div>
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          Add company
        </Button>
      </div>

      <div className="flex-1 p-6 space-y-4 max-w-4xl w-full">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search companies"
            aria-label="Search companies"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading companies…</p>
        ) : error ? (
          <p className="text-sm text-destructive">Failed to load companies.</p>
        ) : companies.length === 0 ? (
          <div className="py-12 text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              {search ? "No companies match this search." : "No companies yet."}
            </p>
            {!search && (
              <p className="text-sm text-muted-foreground">
                Companies are added automatically when you save a job, or you can add one by hand.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {companies.map((company) => (
              <Link
                key={company.company_id}
                href={`/companies/${company.company_id}`}
                className="block"
              >
                <Card className="cursor-pointer hover:shadow-md transition-shadow">
                  <CardContent className="p-4 space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-semibold leading-snug flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        {company.name}
                      </p>
                      {company.is_blacklisted && <Badge variant="destructive">Blacklisted</Badge>}
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      {company.industry && <span>{company.industry}</span>}
                      {company.size && <span>{company.size}</span>}
                      {company.website && (
                        <span className="flex items-center gap-1">
                          <Globe className="h-3 w-3" />
                          {company.website.replace(/^https?:\/\//, "")}
                        </span>
                      )}
                    </div>
                    {company.notes && (
                      <p className="text-xs text-muted-foreground line-clamp-2">{company.notes}</p>
                    )}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <p className="text-xs text-muted-foreground">
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-3.5 w-3.5 mr-1" />
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!data?.has_next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </div>

      <CompanyFormDialog open={creating} onOpenChange={setCreating} />
    </div>
  )
}
