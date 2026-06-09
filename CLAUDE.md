# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.  
本文件为 Claude Code 在本仓库协作开发时提供上下文与约定。

All documentation in this repo is **bilingual (English / Chinese)** in a single-file sectioned format.  
本仓库所有文档采用**双语（英文 / 中文）单文件分节**格式。

---

## Project Status / 项目状态

**No application code exists yet.** The repository currently contains only architecture and product documents. Implementation follows `docs/SAD.md` for architecture decisions and `docs/PRD.md` for product requirements.

**尚无应用代码。** 仓库目前仅包含架构与产品文档。实现以 `docs/SAD.md` 架构决策和 `docs/PRD.md` 产品需求为准。

---

## What This System Is / 系统是什么

**EN:**  
JobCopilot is a production-grade, multi-tenant intelligent job-search management platform. It uses a multi-AI-agent architecture (LangGraph) to auto-discover and analyze LinkedIn job listings, match them against the user's resume, and manage the full application pipeline. A global AI assistant (Vercel AI SDK + LangGraph ReAct Agent) lets users trigger any action through natural language.

**中文：**  
JobCopilot 是一个生产级、多租户的智能求职管理平台。系统采用多 AI Agent 架构（LangGraph）自动发现并分析 LinkedIn 岗位，与用户简历进行匹配，并管理完整的投递流程。全局 AI 助手（Vercel AI SDK + LangGraph ReAct Agent）让用户通过自然语言触发任意操作。

---

## Architecture / 架构

Full design in `docs/SAD.md`. Key design constraints (violating any one blocks launch) / 完整设计见 `docs/SAD.md`。关键约束（违反任意一条则不满足上线条件）：

- **API-first**: Kong gateway fronts all services; no service is directly internet-accessible.
- **Multi-tenant isolation**: Every DB query against tenant-scoped tables **must** include `WHERE tenant_id = :tenant_id`. Cross-schema JOINs are forbidden.
- **Stateless services**: Application pods carry no local state; all state lives in PostgreSQL, Qdrant, or Redis.
- **Per-user LinkedIn Cookie**: Never use a shared scraping account. Each user's cookie is stored AES-256-GCM encrypted.
- **Secrets never in code**: All credentials injected via environment variables / K8s Secrets; never committed to Git.
- **Non-root containers**: All production Docker images run as `uid=1000`.

---

## Microservices / 微服务拆分

| Service | Tech | K8s Unit | Owned DB Schema |
|---|---|---|---|
| **Kong API Gateway** | Kong 3.x + KIC | `Deployment` | — |
| **Auth Service** | Keycloak 24 | `StatefulSet` | `keycloak_schema` |
| **Profile Service** | Python 3.11 + FastAPI | `Deployment` (HPA) | `profile_schema` |
| **Job Service** | Python 3.11 + FastAPI | `Deployment` (HPA) | `job_schema` |
| **Discovery Service** | Python 3.11 + FastAPI + Playwright + Temporal Worker | `Deployment` | `discovery_schema` |
| **Agent Service** | Python 3.11 + FastAPI + LangGraph | `Deployment` (KEDA) | `agent_schema` |
| **Notification Service** | Python 3.11 + FastAPI | `Deployment` | `notification_schema` |
| **Frontend** | Next.js 14 + TypeScript | `Deployment` | — |

---

## Tech Stack / 技术选型

### Backend / 后端
| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| Web Framework | FastAPI |
| ORM | SQLAlchemy 2.x async + asyncpg |
| DB Migrations | Alembic |
| AI Orchestration | LangGraph (stateful graphs, conditional edges) |
| Workflow Engine | Temporal (durable execution, scheduling) |
| LLM Provider | DashScope (OpenAI-compatible endpoint) |
| LLM Observability | LangSmith |
| Browser Automation | Playwright (LinkedIn crawling) |
| Message Queue | RabbitMQ (`aio-pika` client) |
| Cache | Redis |
| Vector Store | Qdrant |
| Resilience | `tenacity` (retry / circuit-breaker) |

### Frontend / 前端
| Component | Choice |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS + shadcn/ui |
| AI Chat | Vercel AI SDK (`useChat`) + assistant-ui |
| State | Zustand (client) + TanStack Query (server) |
| HTTP Client | Axios / fetch |

### Infrastructure / 基础设施
| Component | Choice |
|---|---|
| API Gateway | Kong 3.x |
| Auth | Keycloak 24 (OIDC / JWT RS256) |
| Container Orchestration | Kubernetes (EKS / GKE / AKS compatible) |
| Elastic Scaling | KEDA (MQ depth) + HPA (CPU) |
| Local Dev | Docker Compose |
| CI/CD | GitHub Actions |

### Observability / 可观测性
| Component | Choice |
|---|---|
| Metrics | Prometheus (metric prefix: `jobcopilot_`) |
| Logs | Loki + Promtail (structured JSON) |
| Traces | Tempo + OpenTelemetry SDK |
| Dashboards | Grafana |
| LLM Traces | LangSmith |

### Dev Tools / 开发工具
| Tool | Purpose |
|---|---|
| Ruff | Linting + formatting |
| mypy | Static type checking |
| pytest | Unit + integration tests |
| gitleaks | Secret scanning in CI |
| Trivy / Snyk | Container vulnerability scanning (blocks Critical CVE) |

---

## Directory Structure / 目录结构

```
JobCopilot/
├── services/
│   ├── profile/          # Profile Service (FastAPI)
│   ├── job/              # Job Service (FastAPI)
│   ├── discovery/        # Discovery Service (FastAPI + Playwright + Temporal Worker)
│   ├── agent/            # Agent Service (FastAPI + LangGraph)
│   │   ├── graphs/       # AnalyzerGraph, ResumeGraph, InterviewGraph, ReActGraph
│   │   ├── tools/        # ReAct tool definitions
│   │   └── prompts/      # All LLM prompt templates
│   └── notification/     # Notification Service (FastAPI)
├── frontend/             # Next.js 14 application
│   ├── app/              # App Router pages
│   ├── components/       # shadcn/ui + custom components
│   └── lib/              # API clients, store, utils
├── packages/
│   └── shared/           # Shared models, logging, exceptions (imported by all services)
├── infra/
│   ├── docker-compose.yml        # Local development
│   ├── k8s/                      # Kubernetes manifests per service
│   └── temporal/                 # Temporal server config
├── docs/
│   ├── PRD.md            # Product Requirements Document (bilingual)
│   ├── SAD.md            # Software Architecture Design (bilingual, with Mermaid diagrams)
│   └── agents/           # Per-agent design docs
├── data/                 # Seed / test data
├── .github/
│   └── workflows/        # CI/CD pipelines
└── CLAUDE.md
```

---

## Development Conventions / 开发规范

### Environment Variables / 环境变量
```bash
# LLM
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LANGSMITH_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/jobcopilot
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379

# Auth
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=jobcopilot
KEYCLOAK_CLIENT_ID=api

# Secrets (AES-256 key for encrypting LinkedIn cookies + API keys)
ENCRYPTION_KEY=<32-byte hex>

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=jobcopilot
```

### Code Style / 代码规范
- Ruff for linting and formatting (`ruff check .` + `ruff format .`)
- mypy for type checking (strict mode per service)
- No inline SQL strings — use SQLAlchemy ORM or text() with bound parameters
- Structured JSON logging via shared `packages/shared/logging.py`; every log entry includes `trace_id`, `tenant_id`, `service`
- All API responses include `X-Request-Id` header

### API Conventions / API 规范
- All external endpoints versioned: `/v1/`
- Internal service-to-service endpoints: `/internal/` (Kong blocks external access)
- Error response shape: `{ "error": { "code": "...", "message": "..." } }` — no internal stack traces
- Health probes: `GET /healthz/live` (liveness) and `GET /healthz/ready` (readiness)
- Streaming (AI chat): Server-Sent Events (`text/event-stream`)

### Database / 数据库
- Alembic for all schema changes — no manual `ALTER TABLE`
- Every query against a tenant-scoped table must include `WHERE tenant_id = :tenant_id`
- `SELECT *` is forbidden; always list columns explicitly
- Parameterized queries only; no string-interpolated SQL

### LLM / AI
- Default model: `qwen-max` via DashScope; switchable via `LLM_MODEL` env var
- LangGraph dev mode: `langgraph dev` (development only, never deployed to cluster)
- All LangGraph graphs must define explicit input/output state schemas (TypedDict)
- Prompts live in `services/agent/prompts/`; never inline prompts in graph code

### Security / 安全
- LinkedIn cookies and API keys: AES-256-GCM encrypted before any persistence
- Bcrypt (cost ≥ 12) for password hashing
- No `logging.debug(credential)` or any credential in log output
- `gitleaks` blocks commits containing secrets patterns

---

## CI Requirements / CI 必须覆盖

1. **Lint**: `ruff check .` + `ruff format --check .`
2. **Type Check**: `mypy` per service
3. **Unit Tests**: `pytest` (no real DB/queue)
4. **Integration Tests**: `pytest` against real PostgreSQL + Redis + RabbitMQ (Docker Compose in CI)
5. **Secret Scan**: `gitleaks detect`
6. **Image Scan**: Trivy or Snyk — Critical CVE blocks the pipeline

---

## Docs Convention / 文档规范

All documentation files use **bilingual single-file format**:

```markdown
## N. English Title / 中文标题

**EN:** English content...

**中文：** 中文内容...
```

Mermaid diagram labels use English (universal for technical diagrams).  
Mermaid 图表标签使用英文（技术图表通用语言）。
