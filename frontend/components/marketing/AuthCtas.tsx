"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getKeycloak, initKeycloak } from "@/lib/keycloak";
import { Button } from "@/components/ui/button";
import { landing } from "@/lib/content/landing";

type SsoStatus = "unknown" | "anonymous" | "authenticated";

/**
 * Silently probe for an existing Keycloak session so the landing page can
 * offer "Go to Dashboard" to returning users. Never redirects — anonymous
 * visitors just see the sign-in/register CTAs.
 */
function useSsoSession(): SsoStatus {
  const [status, setStatus] = useState<SsoStatus>("unknown");

  useEffect(() => {
    initKeycloak("check-sso")
      .then((authenticated) => setStatus(authenticated ? "authenticated" : "anonymous"))
      .catch(() => setStatus("anonymous"));
  }, []);

  return status;
}

function appRedirectUri(): string {
  return `${window.location.origin}/dashboard`;
}

/**
 * Start an auth flow, but never while the landing page's silent `check-sso` is
 * still in flight.
 *
 * keycloak-js runs that probe in a hidden iframe against the SAME authorization
 * endpoint a top-level login uses. Firing both at once makes the two requests
 * race Keycloak's `AUTH_SESSION_ID` / `KC_RESTART` cookies: whichever lands
 * second replaces the root authentication session, so the rendered login form
 * carries an orphaned `session_code` and submitting it fails with "Your
 * previous sign-in attempt ended."
 *
 * A human never loses that race — the probe finishes long before they can read
 * the page and click. Playwright clicks in ~50ms and loses it on the first
 * login of a fresh browser context, which is the 2026-07-30 E2E flake.
 *
 * `initKeycloak` memoizes its promise, so by click time this is almost always
 * already resolved and costs nothing. A REJECTED probe is deliberately ignored
 * rather than reported: "is there an existing session?" is not an input to
 * "the user asked to sign in" — we proceed to the full interactive flow, which
 * is the complete action requested, not a degraded stand-in for it.
 */
async function startAuth(action: "login" | "register"): Promise<void> {
  await initKeycloak("check-sso").catch(() => undefined);
  const kc = getKeycloak();
  const options = { redirectUri: appRedirectUri() };
  await (action === "login" ? kc.login(options) : kc.register(options));
}

/** Hero CTAs: register + sign-in for visitors, dashboard link for users. */
export function HeroCtas() {
  const status = useSsoSession();

  if (status === "authenticated") {
    return (
      <Button size="lg" asChild>
        <Link href="/dashboard">{landing.hero.ctaDashboard}</Link>
      </Button>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-center gap-3">
      <Button size="lg" onClick={() => startAuth("register")}>
        {landing.hero.ctaPrimary}
      </Button>
      <Button size="lg" variant="outline" onClick={() => startAuth("login")}>
        {landing.hero.ctaSignIn}
      </Button>
    </div>
  );
}

/** Compact header CTA: sign-in for visitors, dashboard link for users. */
export function HeaderCta() {
  const status = useSsoSession();

  if (status === "authenticated") {
    return (
      <Button size="sm" asChild>
        <Link href="/dashboard">{landing.hero.ctaDashboard}</Link>
      </Button>
    );
  }

  return (
    <Button size="sm" variant="outline" onClick={() => startAuth("login")}>
      {landing.hero.ctaSignIn}
    </Button>
  );
}
