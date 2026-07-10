# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.  
本文件为 Claude Code 在本仓库协作开发时提供上下文与约定。

All documentation in this repo is **bilingual (English / Chinese)** in a single-file sectioned format.  
本仓库所有文档采用**双语（英文 / 中文）单文件分节**格式。

---

## Project Status / 项目状态

**EN:**  
All application code is implemented, verified end-to-end, and **live in production** at `https://arnoldshang.com` (single-node Docker Compose on Hetzner, deployed via `infra/scripts/deploy.sh` — CI builds → GHCR → digest-pinned pull; production is never a build/debug environment). The full stack — 5 backend microservices, shared library, Next.js 15 frontend, and infrastructure (PostgreSQL, Redis, RabbitMQ, Qdrant, Temporal, Kong, Keycloak, Caddy edge with TLS + observability) — is committed, pushed, and healthy. Implementation follows `docs/SAD.md` for architecture decisions and `docs/PRD.md` for product requirements.

**Milestone status (updated 2026-07-08):**
1. ✅ Auth chain (Keycloak OIDC, JWT RS256, tenant_id claim)
2. ✅ E2E manual verification (login → profile → jobs list/detail/tracking → AI assistant streaming chat → discovery) — completed 2026-07-06, incl. the `/jobs` list page and a full frontend↔backend contract reconciliation
3. ✅ Kubernetes manifests (`infra/k8s/`) — written; future scaling path (current deployment is Compose)
4. ✅ Hetzner production deployment (Caddy TLS edge, security hardening, Prometheus/Loki/Grafana observability)
5. ✅ AI assistant tool-chain repair (2026-07-08, prod @ `e801133`) — all 5 ReAct tools wired to real Job Service internal endpoints (4 previously called endpoints that never existed and failed silently); HTTP self-calls replaced with in-process shared services; shared structlog config fixed (it crashed on every log call, turning all services' handled errors into bare 500s); tool activity now streamed to the chat UI. See "AI Assistant Tool Contract" below.
6. ✅ Contract testing in CI (2026-07-09) — three enforcement layers: shared MQ event models (`jobcopilot_shared.events`, publishers construct / consumers validate), consumer-driven HTTP contract tests (`tests/contracts/` — every consumer call site asserted against the provider's real OpenAPI), and OpenAPI-generated frontend types (`openapi/*.json` → `frontend/lib/gen/` via `npm run gen:api-types`; entity types in `lib/api.ts` are re-exports — NEVER hand-write them). CI "Contract Checks" job fails on any drift.

**Next milestone: not yet defined** — decide with the user before starting new feature work. Known open items: Tempo + OpenTelemetry tracing (roadmap), offsite backup enablement (awaiting S3 credentials), production test-account cleanup before public launch, single-URL job scrape pipeline (analyze_job for untracked postings), bulk re-embed backfill job (embeddings are only created on upload; required before any post-launch Qdrant storage migration).

**Local test account:** `testuser@example.com` / `Test1234!` (Keycloak realm: `jobcopilot`; production uses a separate strong-password account — see session memory, never commit it here)

**中文：**  
所有应用代码已实现、完成端到端验证并已**上线生产** `https://arnoldshang.com`（Hetzner 单节点 Docker Compose，经 `infra/scripts/deploy.sh` 部署——CI 构建 → GHCR → digest 钉死拉取；生产环境绝不用于构建或调试）。完整技术栈——5 个后端微服务、共享库、Next.js 15 前端、基础设施（PostgreSQL、Redis、RabbitMQ、Qdrant、Temporal、Kong、Keycloak、Caddy TLS 边缘 + 可观测性）——均已提交推送并处于健康状态。实现以 `docs/SAD.md` 架构决策和 `docs/PRD.md` 产品需求为准。

**里程碑状态（2026-07-08 更新）：**
1. ✅ 认证链路（Keycloak OIDC、JWT RS256、tenant_id claim）
2. ✅ 端到端手动验证（登录 → 简历 → 职位列表/详情/跟踪 → AI 助手流式对话 → 职位发现）——2026-07-06 收官，含 `/jobs` 列表页与前后端契约全面对齐
3. ✅ Kubernetes 清单文件（`infra/k8s/`）——已编写，作为未来扩容路径（当前部署为 Compose）
4. ✅ Hetzner 生产部署（Caddy TLS 边缘、安全加固、Prometheus/Loki/Grafana 可观测性）
5. ✅ AI 助手工具链修复（2026-07-08，生产 @ `e801133`）——5 个 ReAct 工具全部接通真实的 Job Service 内部端点（此前 4 个调用的端点从不存在、静默失败）；HTTP 自调用改为进程内共享服务；修复共享 structlog 配置（原先每次日志调用都崩溃，全部服务的业务异常退化为裸 500）；工具调用过程实时透出到聊天 UI。详见下文「AI 助手工具契约」。
6. ✅ 契约测试纳入 CI（2026-07-09）——三层强制：共享 MQ 事件模型（`jobcopilot_shared.events`，发布方构造/消费方校验）、消费者驱动的 HTTP 契约测试（`tests/contracts/`——每个消费方调用点对提供方真实 OpenAPI 断言）、OpenAPI 生成前端类型（`openapi/*.json` → `frontend/lib/gen/`；`lib/api.ts` 中的实体类型均为 re-export——**严禁手写**）。CI 的 "Contract Checks" job 对任何漂移直接失败。

**下一个里程碑：尚未确定**——开始新功能开发前先与用户确认。已知待办：Tempo + OpenTelemetry 链路追踪（roadmap）、异地备份启用（等 S3 凭据）、正式对外前清理生产测试账号、任意 URL 职位抓取分析管线、批量重嵌入回填任务（embedding 目前仅在上传时生成；上线后任何 Qdrant 存储迁移的前置条件）。

**本地测试账号：** `testuser@example.com` / `Test1234!`（Keycloak realm: `jobcopilot`；生产使用独立强口令账号——见会话记忆，切勿写入本文件）

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
| **Frontend** | Next.js 15 + TypeScript | `Deployment` | — |

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
| Framework | Next.js 15 (App Router) |
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
| Component | Choice | Status |
|---|---|---|
| Metrics | Prometheus — every service exposes `/metrics` via shared `jobcopilot_shared.metrics` (prefix `jobcopilot_`, identical names across services, distinguished by the scrape `job` label; multi-worker services use `PROMETHEUS_MULTIPROC_DIR`) | ✅ implemented |
| Logs | Loki + Grafana Alloy (Docker discovery; Promtail is deprecated by Grafana) | ✅ implemented |
| Dashboards | Grafana — datasources & dashboards provisioned as code in `infra/grafana/` | ✅ implemented |
| Traces | Tempo + OpenTelemetry SDK | ⬜ roadmap |
| LLM Traces | LangSmith (enabled via `LANGCHAIN_TRACING_V2` + API key) | ✅ implemented |

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
├── frontend/             # Next.js 15 application
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

### Running Python Commands / 运行 Python 命令

**EN:**  
This project uses a **uv workspace** with a single `.venv` at the repo root shared by all services. Always run Python commands through `uv run` — never call `python` directly or use `uv run --package`.

```bash
# Run tests (add env vars as needed)
~/.local/bin/uv run pytest services/<name>/tests/ -v
DATABASE_URL=postgresql+asyncpg://... ENCRYPTION_KEY=... ~/.local/bin/uv run pytest services/job/tests/ -v

# Lint and format
~/.local/bin/uv run ruff check .
~/.local/bin/uv run ruff format .

# Type check
~/.local/bin/uv run mypy services/<name>/

# After changing any pyproject.toml, sync the lock file
~/.local/bin/uv sync
```

**中文：**  
本项目使用 **uv workspace**，所有服务共享仓库根目录的单一 `.venv`。始终通过 `uv run` 运行 Python 命令——不得直接调用 `python`，也不得使用 `uv run --package`。

### Running Docker Commands / 运行 Docker 命令

**EN:**  
Never use `--parallel` with `docker compose build`. Use the plain form instead:

```bash
# Build all services (let Compose manage concurrency)
docker compose build

# Build specific services
docker compose build profile-service job-service discovery-service agent-service notification-service
```

`--parallel` causes multiple build processes to simultaneously call the `desktop.exe` credential helper (configured via `credsStore` in `~/.docker/config.json`). Concurrent calls overwhelm the WSL–Docker Desktop vsock channel, producing `UtilAcceptVsock: accept4 failed 110` and credential errors for every registry pull — including public images that need no authentication. Docker Compose v2 already parallelizes builds intelligently without the flag.

**中文：**  
不得对 `docker compose build` 使用 `--parallel` 参数，直接使用不带该参数的形式：

在 WSL2 + Docker Desktop 环境下，`--parallel` 会导致多个构建进程同时调用 `desktop.exe` 凭据助手，并发调用使 WSL 与 Docker Desktop 之间的 vsock 通道过载，即使是无需认证的公开镜像也会拉取失败。Docker Compose v2 本身已会自动智能并行，无需手动指定。

### Code Style / 代码规范
- Ruff for linting and formatting (`ruff check .` + `ruff format .`)
- mypy for type checking (strict mode per service)
- No inline SQL strings — use SQLAlchemy ORM or text() with bound parameters
- Structured JSON logging via shared `packages/shared/logging.py`; every log entry includes `trace_id`, `tenant_id`, `service`
- `packages/shared/logging.py` is a **pure native structlog** pipeline (PrintLogger → JSON on stdout). Never add stdlib-only processors (e.g. `structlog.stdlib.add_logger_name`) — they crash every log call in every service, including the exception handlers (regression test: `packages/shared/tests/test_logging.py`). / 共享日志是**纯原生 structlog** 管线，禁止混入 stdlib 专用处理器（如 `add_logger_name`）——会使全部服务的每次日志调用崩溃，连异常处理器一起（回归测试见 `packages/shared/tests/test_logging.py`）。
- All API responses include `X-Request-Id` header

### API Conventions / API 规范
- All external endpoints versioned: `/v1/`
- Internal service-to-service endpoints: `/internal/` (Kong blocks external access)
- **Every `/v1` collection endpoint returns `PaginatedResponse` (`{items, total, page, size, has_next}`)** — never a bare JSON array; the frontend reads `.items` everywhere. / **所有 `/v1` 集合端点统一返回 `PaginatedResponse`**，不得返回裸数组。
- `POST /internal/jobs` is an **idempotent upsert by URL** (returns the existing job refreshed, never 409) — discovery re-runs re-publish the same URLs; callers key their records by the returned `job_id`. / `POST /internal/jobs` 为**按 URL 幂等 upsert**，调用方以响应中的 `job_id` 为准。
- MQ event contracts: `job.discovered` carries NO job_id (consumer must upsert the job first to obtain one); `cookie.expired` MUST carry `user_id` + `tenant_id` + `run_id`. / MQ 事件契约：`job.discovered` 不含 job_id（消费者先 upsert 职位换取真实 id）；`cookie.expired` 必须携带 `user_id`、`tenant_id`、`run_id`。
- Error response shape: `{ "error": { "code": "...", "message": "..." } }` — no internal stack traces
- Health probes: `GET /healthz/live` (liveness) and `GET /healthz/ready` (readiness)
- Streaming (AI chat): Server-Sent Events (`text/event-stream`)

### Database / 数据库
- Alembic for all schema changes — no manual `ALTER TABLE`
- Every query against a tenant-scoped table must include `WHERE tenant_id = :tenant_id`
- `SELECT *` is forbidden; always list columns explicitly
- Parameterized queries only; no string-interpolated SQL
- SQLAlchemy async sessions **autobegin** on the first statement — never call `session.begin()` after a query on the same session (raises `InvalidRequestError`; this 500'd `/v1/agent/match` + `/interview` in prod). Service-layer functions own their unit of work: query → mutate → `commit()`. / SQLAlchemy 异步会话在第一条语句时**自动开启事务**——同一会话查询后不得再调 `session.begin()`（必抛 `InvalidRequestError`，曾导致两个生产端点必然 500）。服务层函数自持工作单元：查询 → 变更 → `commit()`。

### LLM / AI
- Default model: `qwen-max` via DashScope; switchable via `LLM_MODEL` env var
- LangGraph dev mode: `langgraph dev` (development only, never deployed to cluster)
- All LangGraph graphs must define explicit input/output state schemas (TypedDict)
- Prompts live in `services/agent/prompts/`; never inline prompts in graph code

### AI Assistant Tool Contract / AI 助手工具契约

**EN:**  
The 5 ReAct tools (`services/agent/.../tools/job_tools.py`) bind to real, tested endpoints — never invent one. Capabilities living in the Agent Service itself run **in-process** through the shared service layer (`services/analysis.py` / `interview.py` / `matching.py`), which the `/v1/agent/*` endpoints call too. Never HTTP-self-call your own service. Tools calling tenant-unscoped internal getters (e.g. `GET /internal/jobs/{job_id}`) must verify `tenant_id` on the response and treat a mismatch as "not found".

| Tool | Binding |
|---|---|
| `analyze_job(job_id)` | `GET /internal/jobs/{job_id}` (tenant-checked) → in-process AnalyzerGraph via `run_job_analysis` |
| `search_jobs(query)` | `GET /internal/jobs?tenant_id&q&limit` |
| `get_applications(status?)` | `GET /internal/applications?user_id&tenant_id&status&limit` |
| `update_kanban(job_id, status)` | `PATCH /internal/applications/by-job/{job_id}` (status state machine enforced server-side) |
| `prepare_interview(job_id)` | in-process InterviewGraph via `prepare_interview_questions` |

Chat SSE streams tool activity: `{"type":"tool_call","id","name","args"}` and `{"type":"tool_result","id","name","result"}`. The Next.js `/api/chat` proxy maps them to Vercel AI SDK data-stream parts `9:`/`a:`; `ChatPanel` renders them from `message.toolInvocations`. The contract spans three layers (agent SSE → proxy → UI) — change them together.

**中文：**  
5 个 ReAct 工具必须绑定真实存在、有测试覆盖的端点——不得杜撰。能力在 Agent Service 自身的，必须**进程内**走共享服务层（analysis / interview / matching），与 `/v1/agent/*` 端点共用同一代码路径——严禁 HTTP 自调用。调用无租户过滤的内部端点时必须校验响应中的 `tenant_id`，不匹配按"不存在"处理。聊天 SSE 的 tool_call / tool_result 事件（含 id、result）由前端代理映射为 AI SDK 数据流 `9:`/`a:` 部分，`ChatPanel` 据 `toolInvocations` 渲染；该契约横跨三层（agent SSE → 代理 → UI），修改时必须三层同步。

### Security / 安全
- LinkedIn cookies and API keys: AES-256-GCM encrypted before any persistence
- Bcrypt (cost ≥ 12) for password hashing
- No `logging.debug(credential)` or any credential in log output
- `gitleaks` blocks commits containing secrets patterns

### Dependency Version Integrity / 依赖版本完整性

**EN:**  
LLMs generate version numbers from training data, not from live registry lookups. A version that looks plausible may not exist, or may exist for one package but not its sibling. Every version written into a dependency file must be verifiable.

Rules:
- **Before writing any version number**, verify it exists: `npm view <pkg>@<ver> version`, `pip index versions <pkg>`, or `docker pull <image>:<tag>`.
- **Lock files are mandatory and must be committed**. They are the primary defence against version hallucinations — a missing or non-existent version causes an immediate install failure rather than a silent runtime surprise.
  - npm: generate and commit `package-lock.json` (`npm install` inside the target Node image) at the same time the code is scaffolded.
  - Python: `uv.lock` is already committed at the workspace root. Always run `uv sync` after changing any `pyproject.toml` so the lock file stays current.
  - Docker Compose: run `docker pull <image>:<tag>` to confirm every image tag exists before committing.
- **Version–feature consistency**: when using a feature that belongs to a specific version (e.g. `next.config.ts` requires Next.js 15+), pin the package to that version — never mix a feature from version N with a pin at version N-1.
- **Align sibling packages**: related packages (e.g. `temporalio/auto-setup` and `temporalio/admin-tools`) must use the same version tag. Never assume version parity across packages with independent release cadences.
- **Infra compose images are digest-pinned** (`tag@sha256:...` in `infra/docker-compose*.yml`): upstream re-tags (e.g. `postgres:15-alpine` security rebuilds) must arrive as Dependabot PRs through CI, never as silent `docker compose pull` surprises. Never add an unpinned infra image; app images (`ghcr.io/...`) are pinned per-deploy by `deploy.sh` instead.
- **Every image/version change requires human review — NO auto-merge, ever** (owner decision, 2026-07-10): CI proves a new image runs, not that it should be trusted; a human reviewing the Dependabot PR is the final supply-chain gate. Stateful components additionally need release-notes review + a local upgrade test against existing data before merging.

**中文：**  
LLM 生成的版本号来源于训练数据，而非实时查询包注册表。看起来合理的版本号可能并不存在，或者在某个包中存在但在其兄弟包中不存在。所有写入依赖文件的版本号都必须可以验证。

规则：
- **写任何版本号前**，先验证其存在：`npm view <pkg>@<ver> version`、`pip index versions <pkg>` 或 `docker pull <image>:<tag>`。
- **锁文件必须存在且必须提交**。锁文件是防止版本幻觉的第一道防线——不存在的版本会在安装时立即报错，而不是在运行时悄悄出问题。
  - npm：在脚手架代码生成的同时，在目标 Node 镜像内执行 `npm install` 并提交 `package-lock.json`。
  - Python：`uv.lock` 已在工作区根目录提交 ✅。每次修改任何 `pyproject.toml` 后都必须运行 `uv sync` 保持锁文件更新。
  - Docker Compose：提交前执行 `docker pull <image>:<tag>` 确认每个镜像 tag 确实存在。
- **版本–功能一致性**：使用某个特定版本才有的功能（如 `next.config.ts` 需要 Next.js 15+），就必须将包固定到该版本，不得将版本 N 的功能与版本 N-1 的 pin 混用。
- **兄弟包版本对齐**：相关联的包（如 `temporalio/auto-setup` 与 `temporalio/admin-tools`）必须使用相同的版本 tag。不得假设发版节奏独立的包之间版本号对等。
- **基础设施 compose 镜像一律钉 digest**（`infra/docker-compose*.yml` 中 `tag@sha256:...`）：上游对同一 tag 的重发（如 `postgres:15-alpine` 安全重建）必须以 Dependabot PR 的形式经 CI 进入，绝不通过 `docker compose pull` 静默生效。不得新增未钉定的基础设施镜像；应用镜像（`ghcr.io/...`）由 `deploy.sh` 按部署钉定。
- **任何镜像/版本变更必须人工审查——永不开启自动合并**（Owner 决策，2026-07-10）：CI 只能证明新镜像能运行，不能证明它值得信任；人工审阅 Dependabot PR 是供应链的最后一道闸。有状态组件合并前还须过 release notes + 本地带存量数据升级验证。

---

### Engineering Philosophy / 工程原则

**EN:**  
Always prefer the proper, maintainable solution over a quick workaround. Before implementing any fix, validate it against industry best practices. If a shortcut is tempting, name it explicitly and propose the correct approach instead. Temporary hacks compound into long-term maintenance debt and block future extensibility.

Concretely:
- When an infrastructure/config error occurs, fix the root cause — do not patch the symptom.
- If two options exist (quick hack vs. proper fix), present both with trade-offs and default to the proper one.
- **When choosing among multiple _legitimate_ options, the recommendation MUST be driven by architectural correctness — NEVER by "smallest change / least effort / least risk / smallest diff." Never list minimal change as a pro of the recommended option. If unsure which option is the best practice, research it before recommending.**
- **Never use production as a debug loop.** Reproduce and verify every fix locally (via `docker compose up`) or in staging BEFORE deploying. Deploy only changes already verified elsewhere — production must not be the test bed. When debugging a frontend↔backend integration, audit BOTH sides of the contract together (schemas + both endpoints) in one pass so all mismatches are caught at once; read-only code tracing alone is insufficient — run it end-to-end. Batch related fixes into a single deploy instead of one-commit-per-bug round-trips.
- **Exercise error paths and service-to-service contracts end-to-end, not just happy paths.** "Contract" includes agent-tool ↔ internal-endpoint bindings and exception-handler paths, not only frontend↔backend. A tool that "fails gracefully" (returns error JSON) hides a missing endpoint — the LLM confabulates a fluent answer on top of it, so nothing looks broken (2026-07-08: 4 of 5 ReAct tools had called nonexistent endpoints since launch, and the shared logging bug turning handled errors into bare 500s was only caught by E2E-running an error path).
- Only proceed with a workaround if the user explicitly accepts it after understanding the trade-offs.
- This applies to: Dockerfiles, Docker Compose, Alembic config, K8s manifests, CI pipelines, framework rendering models, and all architectural decisions.

**中文：**  
任何情况下优先选择正确、可维护的方案，而非临时变通。在实现任何修复之前，先验证其是否符合行业最佳实践。如果临时方案很诱人，明确说明并提出正确做法。临时方案会积累成长期维护债务，并阻碍后续扩展。

具体要求：
- 遇到基础设施/配置错误，修复根本原因，不要仅打补丁。
- 如果存在两个选项（临时方案 vs. 正确方案），列出各自权衡，默认选正确方案。
- **在多个_合法_方案中选择时，推荐必须以架构正确性为准——绝不以「改动最小 / 最省事 / 风险最低 / diff 最小」作为依据，也不得把「改动小」列为推荐方案的优点。若不确定哪个是最佳实践，先研究再推荐。**
- **绝不把生产环境当调试循环。** 每个修复都必须先在本地（`docker compose up`）或 staging 端到端复现并验证，再部署；生产只接收已在别处验证过的变更，不得拿生产试错。调试前后端集成时，一次把契约两侧（schema + 两端端点）审全，一并抓出所有不一致；只靠只读追踪代码不够，必须端到端跑通。相关修复合并成一次部署，不要一个 bug 一次生产往返。
- **错误路径与服务间契约也必须端到端跑通，不能只测正常路径。** 「契约」不止前端↔后端，还包括 Agent 工具↔内部端点的绑定和异常处理器路径。「优雅失败」的工具（返回错误 JSON）会掩盖端点缺失——LLM 会在其上编出流畅的回答，表面看一切正常（2026-07-08 教训：5 个 ReAct 工具中 4 个自上线起调用的端点根本不存在；共享日志缺陷把所有业务异常变成裸 500，也是靠端到端跑一条出错路径才暴露）。
- 只有在用户明确理解权衡后主动接受时，才可以采用临时方案。
- 适用范围：Dockerfile、Docker Compose、Alembic 配置、K8s manifest、CI 流水线、框架渲染模型及所有架构决策。

---

## Pre-Push Checklist / 推送前必查清单

**EN:**  
Run these checks locally **before every `git push`**. CI runs the same steps — a push that fails CI wastes a round-trip and blocks the team. All checks must pass with exit code 0.

```bash
# 1. Lint — must produce zero errors
~/.local/bin/uv run ruff check .

# 2. Format — must produce zero diffs  
~/.local/bin/uv run ruff format --check .

# 3. Type check — run for every service you touched
~/.local/bin/uv run mypy services/<name>/

# 4. Unit tests — run for every service you touched (no real DB/queue needed)
~/.local/bin/uv run pytest services/<name>/tests/ -v -m "not integration"

# 5. Contract checks — ALWAYS when any API schema, router, event, or frontend
#    type changed. Regenerate + commit openapi/ and frontend/lib/gen/ if they diff.
~/.local/bin/uv run pytest tests/contracts -v
~/.local/bin/uv run python scripts/export_openapi.py
(cd frontend && npm run gen:api-types)
git diff --exit-code -- openapi frontend/lib/gen

# 6. Secret scan — must produce zero findings
gitleaks detect --no-git
```

**Ruff per-file-ignores policy:**
- New lint suppressions must go in `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml`, not inline `# noqa` comments — this keeps suppression rationale in one place.
- Adding a new per-file-ignore requires a one-line comment explaining *why* the rule is intentionally suppressed for that path.

**CN:**  
每次 `git push` 前在本地运行以上检查。CI 执行完全相同的步骤——推送后才发现 CI 失败等于浪费一次往返并影响协作。所有检查必须以退出码 0 通过。

Ruff 规则豁免政策：新增 lint 豁免必须写入 `pyproject.toml` 的 `per-file-ignores`，不得使用行内 `# noqa` 注释；每条豁免必须附一行注释说明*为何*对该路径有意关闭该规则。

---

## CI Requirements / CI 必须覆盖

1. **Lint**: `ruff check .` + `ruff format --check .`
2. **Type Check**: `mypy` per service
3. **Unit Tests**: `pytest` (no real DB/queue)
4. **Contract Checks**: `pytest tests/contracts` (consumer call sites vs provider OpenAPI) + OpenAPI/TS-type freshness (`scripts/export_openapi.py` → `npm run gen:api-types` → `git diff --exit-code -- openapi frontend/lib/gen`)
5. **Integration Tests**: `pytest` against real PostgreSQL + Redis + RabbitMQ (Docker Compose in CI)
6. **Secret Scan**: `gitleaks detect`
7. **Image Scan**: Trivy or Snyk — Critical CVE blocks the pipeline

---

## Git Commit Convention / Git 提交规范

**EN:**  
All commit messages must be **bilingual (English / Chinese)**. Write the subject line in English (following Conventional Commits), then add a Chinese summary in the body.

```
feat(service): add feature X

新增功能 X 的描述（中文）。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**中文：**  
所有提交信息必须**中英双语**。标题行用英文（遵循 Conventional Commits），正文中附上中文说明。

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
