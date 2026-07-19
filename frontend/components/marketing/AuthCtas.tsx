"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { getKeycloak, initKeycloak } from "@/lib/keycloak"
import { Button } from "@/components/ui/button"
import { landing } from "@/lib/content/landing"

type SsoStatus = "unknown" | "anonymous" | "authenticated"

/**
 * Silently probe for an existing Keycloak session so the landing page can
 * offer "Go to Dashboard" to returning users. Never redirects — anonymous
 * visitors just see the sign-in/register CTAs.
 */
function useSsoSession(): SsoStatus {
  const [status, setStatus] = useState<SsoStatus>("unknown")

  useEffect(() => {
    initKeycloak("check-sso")
      .then((authenticated) => setStatus(authenticated ? "authenticated" : "anonymous"))
      .catch(() => setStatus("anonymous"))
  }, [])

  return status
}

function appRedirectUri(): string {
  return `${window.location.origin}/dashboard`
}

/** Hero CTAs: register + sign-in for visitors, dashboard link for users. */
export function HeroCtas() {
  const status = useSsoSession()

  if (status === "authenticated") {
    return (
      <Button size="lg" asChild>
        <Link href="/dashboard">{landing.hero.ctaDashboard}</Link>
      </Button>
    )
  }

  return (
    <div className="flex flex-wrap items-center justify-center gap-3">
      <Button
        size="lg"
        onClick={() => getKeycloak().register({ redirectUri: appRedirectUri() })}
      >
        {landing.hero.ctaPrimary}
      </Button>
      <Button
        size="lg"
        variant="outline"
        onClick={() => getKeycloak().login({ redirectUri: appRedirectUri() })}
      >
        {landing.hero.ctaSignIn}
      </Button>
    </div>
  )
}

/** Compact header CTA: sign-in for visitors, dashboard link for users. */
export function HeaderCta() {
  const status = useSsoSession()

  if (status === "authenticated") {
    return (
      <Button size="sm" asChild>
        <Link href="/dashboard">{landing.hero.ctaDashboard}</Link>
      </Button>
    )
  }

  return (
    <Button
      size="sm"
      variant="outline"
      onClick={() => getKeycloak().login({ redirectUri: appRedirectUri() })}
    >
      {landing.hero.ctaSignIn}
    </Button>
  )
}
