"use client"

import Link from "next/link"
import { Building2, MapPin, Star } from "lucide-react"
import { type Application } from "@/lib/api"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface Props {
  application: Application
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

export function JobCard({ application }: Props) {
  const job = application.job

  return (
    <Link href={`/jobs/${application.job_id}`}>
      <Card className="cursor-pointer hover:shadow-md transition-shadow">
        <CardContent className="p-4 space-y-2.5">
          {/* Title */}
          <p className="text-sm font-semibold leading-snug line-clamp-2">
            {job?.title ?? "Unknown Position"}
          </p>

          {/* Company + location */}
          <div className="space-y-1">
            {job?.company_name && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Building2 className="h-3 w-3 shrink-0" />
                <span className="truncate">{job.company_name}</span>
              </div>
            )}
            {job?.location && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <MapPin className="h-3 w-3 shrink-0" />
                <span className="truncate">{job.location}</span>
              </div>
            )}
          </div>

          {/* Footer: match score + date */}
          <div className="flex items-center justify-between pt-0.5">
            {application.match_score != null ? (
              <span className="flex items-center gap-1 text-xs font-medium text-yellow-600">
                <Star className="h-3 w-3 fill-yellow-500 text-yellow-500" />
                {application.match_score}%
              </span>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-2">
              {job?.job_type && (
                <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                  {job.job_type}
                </Badge>
              )}
              <span className="text-[10px] text-muted-foreground">
                {formatDate(application.created_at)}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
