import Keycloak from "keycloak-js"

declare global {
  interface Window {
    __ENV__: {
      KEYCLOAK_URL: string
      KEYCLOAK_REALM: string
      KEYCLOAK_CLIENT_ID: string
      LLM_KEY_MODE: "byo" | "platform"
    }
  }
}

let instance: Keycloak | null = null
let initPromise: Promise<boolean> | null = null

export function getKeycloak(): Keycloak {
  if (!instance) {
    const env = window.__ENV__
    instance = new Keycloak({
      url: env.KEYCLOAK_URL,
      realm: env.KEYCLOAK_REALM,
      clientId: env.KEYCLOAK_CLIENT_ID,
    })
  }
  return instance
}

/**
 * Initialize the Keycloak singleton exactly once per page load.
 *
 * keycloak-js allows a single `init()` per instance, but two entry points need
 * it: the public landing page (silent `check-sso` so CTAs can reflect an
 * existing session) and the authenticated app shell (`login-required`). The
 * memoized promise makes whichever runs first win; a later caller reuses the
 * result — so a client-side navigation from `/` into the app does not re-init.
 * Callers wanting `login-required` semantics must still check
 * `kc.authenticated` afterwards and call `kc.login()` themselves, because the
 * first init may have been the landing page's non-redirecting `check-sso`.
 */
export function initKeycloak(onLoad: "check-sso" | "login-required"): Promise<boolean> {
  const kc = getKeycloak()
  if (!initPromise) {
    initPromise = kc.init({
      onLoad,
      pkceMethod: "S256",
      checkLoginIframe: false,
      silentCheckSsoRedirectUri:
        onLoad === "check-sso"
          ? `${window.location.origin}/silent-check-sso.html`
          : undefined,
    })
  }
  return initPromise
}
