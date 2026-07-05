import { NextRequest } from "next/server"

const KONG_URL = process.env.KONG_URL ?? "http://kong:8000"

export async function POST(req: NextRequest) {
  const { messages } = await req.json()

  const backendRes = await fetch(`${KONG_URL}/v1/agent/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: req.headers.get("Authorization") ?? "",
    },
    // Backend contract is ChatRequest { messages: [{ role, content }] } — forward
    // the full conversation as-is rather than splitting into message/history.
    body: JSON.stringify({
      messages: messages.map((m: { role: string; content: string }) => ({
        role: m.role,
        content: m.content,
      })),
    }),
  })

  if (!backendRes.ok || !backendRes.body) {
    return new Response("Backend error", { status: backendRes.status })
  }

  // Adapt the agent's SSE contract → Vercel AI SDK text stream (protocol v1).
  // The agent already flattens LangGraph events into:
  //   data: {"type":"token","content":"..."}   (assistant text chunk)
  //   data: {"type":"tool_call"|"tool_result"|"done"|"error", ...}
  const encoder = new TextEncoder()
  const emitText = (
    controller: ReadableStreamDefaultController<Uint8Array>,
    content: unknown,
  ) => {
    const text =
      typeof content === "string"
        ? content
        : Array.isArray(content)
          ? content.map((c: { text?: string }) => c.text ?? "").join("")
          : ""
    if (text) controller.enqueue(encoder.encode(`0:${JSON.stringify(text)}\n`))
  }
  const stream = new ReadableStream({
    async start(controller) {
      const reader = backendRes.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            const payload = line.slice(6).trim()
            if (!payload) continue

            try {
              const event = JSON.parse(payload)
              if (event.type === "token") emitText(controller, event.content)
              else if (event.type === "error") emitText(controller, event.content)
            } catch {
              // skip malformed events
            }
          }
        }
      } finally {
        controller.close()
      }
    },
  })

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "X-Vercel-AI-Data-Stream": "v1",
      "Cache-Control": "no-cache",
    },
  })
}
