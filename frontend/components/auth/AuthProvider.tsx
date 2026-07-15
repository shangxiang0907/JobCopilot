"use client"

import { createContext, useContext, useEffect, useState } from "react"
import { getKeycloak } from "@/lib/keycloak"

interface AuthState {
  ready: boolean
  userId: string | undefined
  tenantId: string | undefined
  email: string | undefined
  name: string | undefined
  /** Broker alias (e.g. "google") when the session came from an IdP; absent for password logins. */
  identityProvider: string | undefined
}

const AuthContext = createContext<AuthState>({
  ready: false,
  userId: undefined,
  tenantId: undefined,
  email: undefined,
  name: undefined,
  identityProvider: undefined,
})

export function useAuth(): AuthState {
  return useContext(AuthContext)
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    ready: false,
    userId: undefined,
    tenantId: undefined,
    email: undefined,
    name: undefined,
    identityProvider: undefined,
  })

  useEffect(() => {
    const kc = getKeycloak()

    kc.init({
      onLoad: "login-required",
      pkceMethod: "S256",
      checkLoginIframe: false,
    })
      .then(() => {
        const parsed = kc.tokenParsed
        setState({
          ready: true,
          userId: parsed?.sub,
          tenantId: parsed?.tenant_id as string | undefined,
          email: parsed?.email as string | undefined,
          name: parsed?.name as string | undefined,
          identityProvider: parsed?.identity_provider as string | undefined,
        })

        // Silently refresh the token 30 s before it expires
        kc.onTokenExpired = () => {
          kc.updateToken(30).catch(() => kc.login())
        }
      })
      .catch(() => kc.login())
  }, [])

  if (!state.ready) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    )
  }

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
}
