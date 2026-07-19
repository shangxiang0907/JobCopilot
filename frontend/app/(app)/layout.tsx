import { Providers } from "@/lib/providers"
import { AppShell } from "@/components/layout/AppShell"

// Authentication boundary: everything in this route group requires a Keycloak
// session (AuthProvider inside Providers runs login-required). Public pages
// live in (marketing) and must never be nested under this layout.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <AppShell>{children}</AppShell>
    </Providers>
  )
}
