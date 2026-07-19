// Landing-page copy, separated from markup so a future i18n layer (e.g.
// next-intl) only needs to swap this module for a message catalog — components
// render exclusively from this structure and contain no hardcoded prose.

export interface LandingFeature {
  title: string
  description: string
}

export interface LandingMode {
  name: string
  tagline: string
  points: string[]
}

export interface LandingContent {
  hero: {
    headline: string
    subheadline: string
    ctaPrimary: string
    ctaSignIn: string
    ctaDashboard: string
    openSourceNote: string
  }
  features: {
    heading: string
    items: LandingFeature[]
  }
  modes: {
    heading: string
    subheading: string
    hosted: LandingMode
    selfHosted: LandingMode
    githubCta: string
  }
  footer: {
    tagline: string
    github: string
  }
}

export const GITHUB_URL = "https://github.com/shangxiang0907/JobCopilot"

export const landing: LandingContent = {
  hero: {
    headline: "Your AI copilot for the job search",
    subheadline:
      "JobCopilot discovers openings from public job boards, analyzes every posting against your resume with AI, and manages your whole application pipeline — so you spend your time interviewing, not tab-juggling.",
    ctaPrimary: "Get started free",
    ctaSignIn: "Sign in",
    ctaDashboard: "Go to Dashboard",
    openSourceNote: "Open source. Self-host it, or use the hosted app.",
  },
  features: {
    heading: "Everything between “looking” and “hired”",
    items: [
      {
        title: "Automated job discovery",
        description:
          "Scheduled crawls of public job boards bring new matching openings to you. No account credentials ever required — public sources only.",
      },
      {
        title: "Add any posting, any way",
        description:
          "Found a job elsewhere? Add it by pasting a URL, the raw description text, or even a screenshot — AI parses it into a structured posting.",
      },
      {
        title: "AI resume matching",
        description:
          "Every posting is scored against your resume: a match score, your strongest talking points, and the gaps to address before applying.",
      },
      {
        title: "Interview preparation",
        description:
          "Generate role-specific interview questions and preparation notes from the actual job description and your background.",
      },
      {
        title: "Kanban application pipeline",
        description:
          "Track every application from saved to offer on a drag-and-drop board, with email notifications on the events you care about.",
      },
      {
        title: "AI assistant built in",
        description:
          "A chat assistant that can actually do things — search your jobs, run an analysis, update your pipeline — through natural language.",
      },
    ],
  },
  modes: {
    heading: "Run it your way",
    subheading:
      "JobCopilot is open source with two first-class deployment modes.",
    hosted: {
      name: "Hosted",
      tagline: "Sign up and start in minutes",
      points: [
        "No setup — register with email or Google",
        "AI features powered by the platform, with a fair daily usage allowance",
        "Always running the latest release",
      ],
    },
    selfHosted: {
      name: "Self-hosted",
      tagline: "Your infrastructure, your keys",
      points: [
        "Deploy the full stack with Docker Compose",
        "Bring your own LLM API key — no usage limits imposed",
        "All data stays on your own server",
      ],
    },
    githubCta: "View on GitHub",
  },
  footer: {
    tagline: "Open-source intelligent job-search management.",
    github: "GitHub",
  },
}
