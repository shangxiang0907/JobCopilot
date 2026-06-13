import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Providers } from "@/lib/providers"
import { AppShell } from "@/components/layout/AppShell"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "JobCopilot",
  description: "Intelligent job-search management platform",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Read at request time (server-side) so the same image works in every environment.
  // The browser reads these values from window.__ENV__ — no NEXT_PUBLIC_ bake-in needed.
  const clientEnv = {
    KEYCLOAK_URL: process.env.KEYCLOAK_PUBLIC_URL ?? "http://localhost:8080",
    KEYCLOAK_REALM: process.env.KEYCLOAK_REALM ?? "jobcopilot",
    KEYCLOAK_CLIENT_ID: process.env.KEYCLOAK_CLIENT_ID ?? "frontend",
  }

  return (
    <html lang="en">
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__ENV__=${JSON.stringify(clientEnv)}`,
          }}
        />
      </head>
      <body className={inter.className}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
