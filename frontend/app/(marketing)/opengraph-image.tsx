import { ImageResponse } from "next/og"

// Social-share card for the landing page (og:image / twitter:image), generated
// with next/og so it needs no binary asset in the repo.

export const alt = "JobCopilot — AI-powered job-search management"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 24,
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
          color: "#f8fafc",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 16,
              background: "#3b82f6",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 40,
            }}
          >
            💼
          </div>
          <div style={{ fontSize: 64, fontWeight: 700 }}>JobCopilot</div>
        </div>
        <div style={{ fontSize: 30, color: "#94a3b8", textAlign: "center", maxWidth: 900 }}>
          Your AI copilot for the job search — discover, match, apply, track.
        </div>
      </div>
    ),
    size
  )
}
