import type { Metadata } from "next"
import {
  Bot,
  FileScan,
  Github,
  KanbanSquare,
  MessagesSquare,
  Radar,
  Target,
} from "lucide-react"
import { HeroCtas } from "@/components/marketing/AuthCtas"
import { Button } from "@/components/ui/button"
import { GITHUB_URL, landing } from "@/lib/content/landing"
import { getSiteUrl } from "@/lib/site-url"

// Rendered per request so SEO metadata reflects the deployment's runtime
// SITE_URL (see lib/site-url.ts) — reading env in a static page would freeze
// build-time values into the image.
export const dynamic = "force-dynamic"

const TITLE = "JobCopilot — AI-powered job-search management"
const DESCRIPTION =
  "Open-source platform that discovers jobs from public boards, matches them against your resume with AI, and manages your application pipeline end to end."

export function generateMetadata(): Metadata {
  const siteUrl = getSiteUrl()
  return {
    title: TITLE,
    description: DESCRIPTION,
    metadataBase: siteUrl,
    alternates: { canonical: "/" },
    openGraph: {
      title: TITLE,
      description: DESCRIPTION,
      url: "/",
      siteName: "JobCopilot",
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: TITLE,
      description: DESCRIPTION,
    },
  }
}

const FEATURE_ICONS = [Radar, FileScan, Target, MessagesSquare, KanbanSquare, Bot]

export default function LandingPage() {
  return (
    <>
      {/* Hero */}
      <section className="mx-auto flex w-full max-w-3xl flex-col items-center gap-6 px-4 py-24 text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          {landing.hero.headline}
        </h1>
        <p className="text-lg text-muted-foreground">{landing.hero.subheadline}</p>
        <HeroCtas />
        <p className="text-sm text-muted-foreground">{landing.hero.openSourceNote}</p>
      </section>

      {/* Features */}
      <section className="border-t bg-muted/40">
        <div className="mx-auto w-full max-w-6xl px-4 py-20">
          <h2 className="mb-12 text-center text-3xl font-semibold tracking-tight">
            {landing.features.heading}
          </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {landing.features.items.map((feature, i) => {
              const Icon = FEATURE_ICONS[i % FEATURE_ICONS.length]
              return (
                <div
                  key={feature.title}
                  className="rounded-lg border bg-background p-6"
                >
                  <Icon className="mb-4 h-6 w-6 text-primary" />
                  <h3 className="mb-2 font-semibold">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Deployment modes */}
      <section className="border-t">
        <div className="mx-auto w-full max-w-6xl px-4 py-20">
          <h2 className="mb-3 text-center text-3xl font-semibold tracking-tight">
            {landing.modes.heading}
          </h2>
          <p className="mb-12 text-center text-muted-foreground">
            {landing.modes.subheading}
          </p>
          <div className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2">
            {[landing.modes.hosted, landing.modes.selfHosted].map((mode) => (
              <div key={mode.name} className="rounded-lg border p-8">
                <h3 className="text-xl font-semibold">{mode.name}</h3>
                <p className="mb-4 text-sm text-muted-foreground">{mode.tagline}</p>
                <ul className="space-y-2 text-sm">
                  {mode.points.map((point) => (
                    <li key={point} className="flex gap-2">
                      <span aria-hidden className="text-primary">
                        ✓
                      </span>
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="mt-10 text-center">
            <Button variant="outline" asChild>
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
                <Github className="mr-2 h-4 w-4" />
                {landing.modes.githubCta}
              </a>
            </Button>
          </div>
        </div>
      </section>
    </>
  )
}
