import type { MetadataRoute } from "next"
import { getSiteUrl } from "@/lib/site-url"

// Runtime SITE_URL (self-hosted deployments differ) → must render per request.
export const dynamic = "force-dynamic"

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl()
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Authenticated app routes: crawlers only ever see a login redirect.
      disallow: ["/dashboard", "/jobs", "/discovery", "/profile", "/admin", "/api/"],
    },
    sitemap: new URL("/sitemap.xml", siteUrl).toString(),
  }
}
