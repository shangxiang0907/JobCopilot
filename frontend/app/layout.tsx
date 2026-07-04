import type { Metadata } from "next"
import { Inter } from "next/font/google"
import Script from "next/script"
import "./globals.css"
import { Providers } from "@/lib/providers"
import { AppShell } from "@/components/layout/AppShell"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "JobCopilot",
  description: "Intelligent job-search management platform",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // window.__ENV__ is served by the always-dynamic /env.js route handler and loaded
  // beforeInteractive (before any app code/hydration), so runtime config is read
  // per-request from the container env — never baked in at build time. This layout
  // touches no process.env, keeping all pages statically optimizable.
  return (
    <html lang="en">
      <body className={inter.className}>
        <Script src="/env.js" strategy="beforeInteractive" />
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
