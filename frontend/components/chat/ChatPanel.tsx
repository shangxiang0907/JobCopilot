"use client"

import { useRef, useEffect } from "react"
import { useChat } from "ai/react"
import { Check, Loader2, X, Send, Bot, User } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useUIStore } from "@/lib/store"
import { getKeycloak } from "@/lib/keycloak"

async function fetchWithAuth(url: URL | RequestInfo, options?: RequestInit): Promise<Response> {
  const kc = getKeycloak()
  if (kc.authenticated) {
    await kc.updateToken(30).catch(() => kc.login())
  }
  return fetch(url, {
    ...options,
    headers: {
      ...options?.headers,
      // Identity travels only inside the verified JWT; backends derive
      // sub/tenant_id from it and never trust client-declared headers.
      Authorization: `Bearer ${kc.token ?? ""}`,
    },
  })
}

const TOOL_LABELS: Record<string, string> = {
  analyze_job: "Analyzing job posting",
  update_kanban: "Updating kanban board",
  search_jobs: "Searching jobs",
  get_applications: "Fetching applications",
  prepare_interview: "Preparing interview questions",
}

export function ChatPanel() {
  const closeChat = useUIStore((s) => s.closeChat)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: "/api/chat",
    fetch: fetchWithAuth,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">AI Assistant</span>
        </div>
        <Button variant="ghost" size="icon" onClick={closeChat}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-center">
            <Bot className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Ask me to analyze a job, prepare for an interview, or update your kanban.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "flex gap-2.5",
                  m.role === "user" ? "flex-row-reverse" : "flex-row"
                )}
              >
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border",
                    m.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {m.role === "user" ? (
                    <User className="h-3.5 w-3.5" />
                  ) : (
                    <Bot className="h-3.5 w-3.5" />
                  )}
                </div>
                <div
                  className={cn(
                    "rounded-xl px-3.5 py-2.5 text-sm max-w-[85%] leading-relaxed",
                    m.role === "user"
                      ? "bg-primary text-primary-foreground rounded-tr-sm"
                      : "bg-muted text-foreground rounded-tl-sm"
                  )}
                >
                  {m.toolInvocations && m.toolInvocations.length > 0 && (
                    <div className={cn("space-y-1", m.content && "mb-1.5")}>
                      {m.toolInvocations.map((t) => (
                        <div
                          key={t.toolCallId}
                          className="flex items-center gap-1.5 text-xs text-muted-foreground"
                        >
                          {t.state === "result" ? (
                            <Check className="h-3 w-3 shrink-0" />
                          ) : (
                            <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
                          )}
                          <span>{TOOL_LABELS[t.toolName] ?? t.toolName}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {m.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-2.5">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border bg-muted text-muted-foreground">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="rounded-xl rounded-tl-sm bg-muted px-3.5 py-2.5 text-sm text-muted-foreground">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 px-4 py-3 border-t shrink-0"
      >
        <Input
          value={input}
          onChange={handleInputChange}
          placeholder="Ask anything…"
          disabled={isLoading}
          className="flex-1"
        />
        <Button type="submit" size="icon" disabled={isLoading || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  )
}
