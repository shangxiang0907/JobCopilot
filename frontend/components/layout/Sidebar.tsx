"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, Search, User, MessageSquare, Briefcase } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useUIStore } from "@/lib/store"

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/discovery", label: "Discovery", icon: Search },
  { href: "/profile", label: "Profile", icon: User },
]

export function Sidebar() {
  const pathname = usePathname()
  const { chatOpen, toggleChat } = useUIStore()

  return (
    <aside className="flex flex-col w-56 shrink-0 border-r bg-background h-full">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b">
        <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center">
          <Briefcase className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="font-semibold text-sm">JobCopilot</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href}>
            <span
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                pathname === href || pathname.startsWith(href + "/")
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </span>
          </Link>
        ))}
      </nav>

      {/* Chat toggle */}
      <div className="px-2 py-4 border-t">
        <Button
          variant={chatOpen ? "default" : "outline"}
          size="sm"
          className="w-full justify-start gap-2"
          onClick={toggleChat}
        >
          <MessageSquare className="h-4 w-4" />
          AI Assistant
        </Button>
      </div>
    </aside>
  )
}
