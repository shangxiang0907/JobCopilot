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
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
