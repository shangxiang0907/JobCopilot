"use client"

import { useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { isAxiosError } from "axios"
import { User, Key, ExternalLink, KeyRound } from "lucide-react"
import api, { type Profile } from "@/lib/api"
import { useAuth } from "@/components/auth/AuthProvider"
import { ResumeLibrary } from "@/components/profile/ResumeLibrary"
import { getKeycloak } from "@/lib/keycloak"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const { email, name, identityProvider } = useAuth()
  const [llmApiKey, setLlmApiKey] = useState("")

  // Deployment mode (ADR-007): hosted platform deployments hide the BYO key UI.
  // Read after mount — window.__ENV__ (served by /env.js) is a browser-only global.
  const [byoKeyEnabled, setByoKeyEnabled] = useState(false)
  useEffect(() => {
    setByoKeyEnabled(window.__ENV__?.LLM_KEY_MODE !== "platform")
  }, [])

  const { data: profile, isLoading } = useQuery<Profile>({
    queryKey: ["profile"],
    queryFn: () => api.get("/v1/profiles/me").then((r) => r.data),
  })
  const personalName = (profile?.personal_info as { name?: string } | null | undefined)?.name

  const saveCredentials = useMutation({
    mutationFn: (payload: { llm_api_key?: string }) =>
      api.patch("/v1/profiles/me/credentials", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] })
      setLlmApiKey("")
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Loading profile…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex items-center px-6 py-4 border-b shrink-0">
        <div>
          <h1 className="text-2xl font-semibold">Profile Settings</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage your credentials and resume library
          </p>
        </div>
      </div>

      <div className="flex-1 p-6 max-w-3xl space-y-6">
        {/* Account identity — read from the ID token; credential management is
            delegated to the Keycloak Account Console (never rebuilt in-app). */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <User className="h-4 w-4" />
              Account
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="space-y-2">
              {(name ?? personalName) && (
                <p>
                  <span className="text-muted-foreground">Name: </span>
                  {name ?? personalName}
                </p>
              )}
              {email && (
                <p>
                  <span className="text-muted-foreground">Email: </span>
                  {email}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">
                  {identityProvider
                    ? `Signed in with ${identityProvider.charAt(0).toUpperCase()}${identityProvider.slice(1)}`
                    : "Email & password"}
                </Badge>
                {byoKeyEnabled && (
                  <Badge variant={profile?.has_llm_api_key ? "default" : "outline"}>
                    LLM Key {profile?.has_llm_api_key ? "Set" : "Not Set"}
                  </Badge>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => getKeycloak().accountManagement()}>
                <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                Manage account
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => getKeycloak().login({ action: "UPDATE_PASSWORD" })}
              >
                <KeyRound className="h-3.5 w-3.5 mr-1.5" />
                {identityProvider ? "Set password" : "Change password"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Password, two-factor auth, linked sign-in providers, and active sessions are managed
              in your account console.
            </p>
          </CardContent>
        </Card>

        {/* Credentials — self-hosted (byo) deployments only */}
        {byoKeyEnabled && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Key className="h-4 w-4" />
              Credentials
            </CardTitle>
            <CardDescription>
              Stored AES-256-GCM encrypted. Never logged or exposed.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="llm-key">LLM API Key</Label>
              <Input
                id="llm-key"
                type="password"
                placeholder="Your DashScope / OpenAI-compatible API key"
                value={llmApiKey}
                onChange={(e) => setLlmApiKey(e.target.value)}
              />
            </div>
            <Button
              disabled={saveCredentials.isPending || !llmApiKey.trim()}
              onClick={() => saveCredentials.mutate({ llm_api_key: llmApiKey })}
            >
              {saveCredentials.isPending ? "Verifying key…" : "Save Credentials"}
            </Button>
            {saveCredentials.isError && (
              <p className="text-sm text-destructive">
                {(isAxiosError(saveCredentials.error) &&
                  saveCredentials.error.response?.data?.error?.message) ||
                  "Could not save the key. Please try again."}
              </p>
            )}
            {saveCredentials.isSuccess && (
              <p className="text-sm text-muted-foreground">Key verified and saved.</p>
            )}
          </CardContent>
        </Card>
        )}

        <ResumeLibrary />

        <Separator />
        <p className="text-xs text-muted-foreground pb-6">
          Authentication is handled via Keycloak OIDC with automatic token refresh.
        </p>
      </div>
    </div>
  )
}
