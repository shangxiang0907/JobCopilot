import type { MetadataRoute } from "next"
import { getSiteUrl } from "@/lib/site-url"

// Runtime SITE_URL (self-hosted deployments differ) → must render per request.
export const dynamic = "force-dynamic"

// Public, indexable pages only — the authenticated app is deliberately absent.
export default function sitemap(): MetadataRoute.Sitemap {
  const siteUrl = getSiteUrl()
  return [
    {
      url: siteUrl.toString(),
      changeFrequency: "weekly",
      priority: 1,
    },
  ]
}
