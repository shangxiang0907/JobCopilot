"use client"

import { Sidebar } from "./Sidebar"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { useUIStore } from "@/lib/store"

export function AppShell({ children }: { children: React.ReactNode }) {
  const chatOpen = useUIStore((s) => s.chatOpen)

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col min-w-0">
        {children}
      </main>
      {chatOpen && (
        <aside className="w-96 shrink-0 border-l flex flex-col">
          <ChatPanel />
        </aside>
      )}
    </div>
  )
}
