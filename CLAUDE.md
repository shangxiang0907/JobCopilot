# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

This file is **English-only** for context efficiency (owner decision, 2026-07-11). All other documentation in this repo (docs/, README) is **bilingual (English / Chinese)** in a single-file sectioned format — see "Docs Convention" below.

---

## Project Status

All application code is implemented, verified end-to-end, and **live in production** at `https://arnoldshang.com` (single-node Docker Compose on Hetzner, deployed via `infra/scripts/deploy.sh` — CI builds → GHCR → digest-pinned pull; production is never a build/debug environment). The full stack — 5 backend microservices, shared library, Next.js 15 frontend, and infrastructure (PostgreSQL, Redis, RabbitMQ, Qdrant, Temporal, Kong, Keycloak 26, Caddy edge with TLS + observability) — is committed, pushed, and healthy. All six original milestones (auth chain, E2E verification, K8s manifests, production deployment, AI tool-chain repair, contract testing in CI) shipped and were verified in production; history lives in git log.

**⚠️ v0.2 re-scope decided 2026-07-11 (PRD v0.2) — NOT YET IMPLEMENTED.** The product was re-scoped: B2C self-registration, credential-free public-source job discovery replacing LinkedIn cookie crawling, JD entry via URL/text/screenshot, email-only notifications, analytics module removed, dual LLM-key deployment modes (self-hosted BYO key vs hosted platform key). `docs/PRD.md` and `docs/SAD.md` describe this **target state**; the current codebase still implements the previous scope (LinkedIn cookie flow, `cookie.expired` event, etc.). Do not assume re-scope features exist in code until the implementation batches below land.

**Work queue (agreed order):**
1. ~~Docs batch — PRD/SAD/README/CLAUDE.md v0.2 alignment~~ ✅ done 2026-07-11
2. ~~Anti-hallucination guardrails~~ ✅ done 2026-07-12: Claude Code hooks (`.claude/hooks/` — PostToolUse ruff on every .py edit, PreToolUse blocks bare python / `--parallel` / `uv run --package`), Playwright E2E smoke (`frontend/e2e/`, runs in CD `e2e-smoke` job against the exact pushed images and gates deploy), Pydantic validation of LLM JSON outputs (`graphs/llm_outputs.py` — schemas mirror prompts, change together), `alembic check` per service in CI (models now declare index/constraint names matching the live DB; env.py filters autogenerate to own schema), ruff TID251 bans `structlog.stdlib`, import-linter service-independence contracts
3. **Operator observability**: surface LangSmith dashboards to the owner; LangGraph Studio (`langgraph dev`, dev-only)
4. **Re-scope implementation**: remove LinkedIn cookie flow → public-source crawling (source list TBD), three JD entry paths, open self-registration (email verification), deployment-mode LLM key switch, analytics teardown, notification convergence, `/admin/users` + `/admin/usage`
- Other open items: offsite backup enablement (awaiting S3 credentials), production test-account cleanup before public launch, bulk re-embed backfill job (embeddings are only created on upload; required before any post-launch Qdrant storage migration)

**Local test account:** `testuser@example.com` / `Test1234!` (Keycloak realm: `jobcopilot`; production uses a separate strong-password account — see session memory, never commit it here)

---

## What This System Is

JobCopilot is a production-grade intelligent job-search management platform. It uses a multi-AI-agent architecture (LangGraph) to discover job listings from public job boards, analyze them against the user's resume, and manage the full application pipeline. Any posting can be added manually via URL, pasted JD text, or screenshot (v0.2). A global AI assistant (Vercel AI SDK + LangGraph ReAct Agent) lets users trigger any action through natural language. Open source, with two deployment modes: self-hosted (BYO LLM key) and the official hosted site (platform LLM key).

Product requirements: `docs/PRD.md` (v0.2). Architecture decisions: `docs/SAD.md` (v0.2). Stack overview and repo layout: `README.md`.

---

## Architecture Constraints

Key design constraints (violating any one blocks launch):

- **API-first**: Kong gateway fronts all services; no service is directly internet-accessible.
- **Multi-tenant isolation**: Every DB query against tenant-scoped tables **must** include `WHERE tenant_id = :tenant_id`. Cross-schema JOINs are forbidden. Each user is provisioned as their own tenant.
- **Stateless services**: Application pods carry no local state; all state lives in PostgreSQL, Qdrant, or Redis.
- **Credential-free crawling** (v0.2, ADR-006): never collect or use user account credentials for crawling; public no-login sources only.
- **Secrets never in code**: All credentials injected via environment variables / K8s Secrets; never committed to Git.
- **Non-root containers**: All production Docker images run as `uid=1000`.

### Microservices

| Service | Tech | Owned DB Schema |
|---|---|---|
| **Kong API Gateway** | Kong 3.x | — |
| **Auth Service** | Keycloak 26 | `keycloak_schema` |
| **Profile Service** | Python 3.11 + FastAPI | `profile_schema` |
| **Job Service** | Python 3.11 + FastAPI | `job_schema` |
| **Discovery Service** | Python 3.11 + FastAPI + Playwright + Temporal Worker | `discovery_schema` |
| **Agent Service** | Python 3.11 + FastAPI + LangGraph | `agent_schema` |
| **Notification Service** | Python 3.11 + FastAPI | `notification_schema` |
| **Frontend** | Next.js 15 + TypeScript | — |

### Stack conventions that matter when coding

(Full stack tables: `README.md` §3 and `docs/SAD.md`.)

- ORM: SQLAlchemy 2.x async + asyncpg; migrations via Alembic only.
- MQ: RabbitMQ via `aio-pika`; event payloads are shared Pydantic models in `jobcopilot_shared.events`.
- LLM: DashScope OpenAI-compatible endpoint; default model `qwen-max`, switchable via `LLM_MODEL`.
- Metrics: every service exposes `/metrics` via shared `jobcopilot_shared.metrics` — prefix `jobcopilot_`, identical names across services (distinguished by scrape `job` label); multi-worker services need `PROMETHEUS_MULTIPROC_DIR`.
- Logs: Loki + **Grafana Alloy** (Promtail is deprecated by Grafana). Grafana datasources/dashboards provisioned as code in `infra/grafana/`.
- Traces: Tempo + OpenTelemetry is **roadmap only**; LangSmith tracing is live (`LANGCHAIN_TRACING_V2` + API key).
- Resilience: `tenacity` for retry/circuit-breaker.

---

## Development Conventions

### Environment Variables

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

# Secrets (AES-256 key for encrypting user API keys)
ENCRYPTION_KEY=<32-byte hex>

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=jobcopilot
```

### Running Python Commands

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

### Running Docker Commands

Never use `--parallel` with `docker compose build`. Use the plain form:

```bash
docker compose build
docker compose build profile-service job-service discovery-service agent-service notification-service
```

`--parallel` causes multiple build processes to simultaneously call the `desktop.exe` credential helper (configured via `credsStore` in `~/.docker/config.json`). Concurrent calls overwhelm the WSL–Docker Desktop vsock channel, producing `UtilAcceptVsock: accept4 failed 110` and credential errors for every registry pull — including public images that need no authentication. Docker Compose v2 already parallelizes builds intelligently without the flag.

### Code Style

- Ruff for linting and formatting (`ruff check .` + `ruff format .`)
- mypy for type checking (strict mode per service)
- No inline SQL strings — use SQLAlchemy ORM or `text()` with bound parameters
- Structured JSON logging via shared `packages/shared/logging.py`; every log entry includes `trace_id`, `tenant_id`, `service`
- `packages/shared/logging.py` is a **pure native structlog** pipeline (PrintLogger → JSON on stdout). Never add stdlib-only processors (e.g. `structlog.stdlib.add_logger_name`) — they crash every log call in every service, including the exception handlers (regression test: `packages/shared/tests/test_logging.py`).
- All API responses include `X-Request-Id` header

### API Conventions

- All external endpoints versioned: `/v1/`
- Internal service-to-service endpoints: `/internal/` (Kong blocks external access)
- **Every `/v1` collection endpoint returns `PaginatedResponse` (`{items, total, page, size, has_next}`)** — never a bare JSON array; the frontend reads `.items` everywhere.
- `POST /internal/jobs` is an **idempotent upsert by URL** (returns the existing job refreshed, never 409) — discovery re-runs re-publish the same URLs; callers key their records by the returned `job_id`.
- MQ event contracts: `job.discovered` carries NO job_id (consumer must upsert the job first to obtain one).
- Error response shape: `{ "error": { "code": "...", "message": "..." } }` — no internal stack traces
- Health probes: `GET /healthz/live` (liveness) and `GET /healthz/ready` (readiness)
- Streaming (AI chat): Server-Sent Events (`text/event-stream`)

### Database

- Alembic for all schema changes — no manual `ALTER TABLE`
- Every query against a tenant-scoped table must include `WHERE tenant_id = :tenant_id`
- `SELECT *` is forbidden; always list columns explicitly
- Parameterized queries only; no string-interpolated SQL
- SQLAlchemy async sessions **autobegin** on the first statement — never call `session.begin()` after a query on the same session (raises `InvalidRequestError`; this 500'd `/v1/agent/match` + `/interview` in prod). Service-layer functions own their unit of work: query → mutate → `commit()`.

### LLM / AI

- Default model: `qwen-max` via DashScope; switchable via `LLM_MODEL` env var. JD screenshot parsing (v0.2) requires a vision model (e.g. qwen-vl) on the same endpoint.
- LangGraph dev mode: `langgraph dev` (development only, never deployed)
- All LangGraph graphs must define explicit input/output state schemas (TypedDict)
- Prompts live in `services/agent/prompts/`; never inline prompts in graph code

### AI Assistant Tool Contract

The 5 ReAct tools (`services/agent/.../tools/job_tools.py`) bind to real, tested endpoints — never invent one. Capabilities living in the Agent Service itself run **in-process** through the shared service layer (`services/analysis.py` / `interview.py` / `matching.py`), which the `/v1/agent/*` endpoints call too. Never HTTP-self-call your own service. Tools calling tenant-unscoped internal getters (e.g. `GET /internal/jobs/{job_id}`) must verify `tenant_id` on the response and treat a mismatch as "not found".

| Tool | Binding |
|---|---|
| `analyze_job(job_id)` | `GET /internal/jobs/{job_id}` (tenant-checked) → in-process AnalyzerGraph via `run_job_analysis` |
| `search_jobs(query)` | `GET /internal/jobs?tenant_id&q&limit` |
| `get_applications(status?)` | `GET /internal/applications?user_id&tenant_id&status&limit` |
| `update_kanban(job_id, status)` | `PATCH /internal/applications/by-job/{job_id}` (status state machine enforced server-side) |
| `prepare_interview(job_id)` | in-process InterviewGraph via `prepare_interview_questions` |

Chat SSE streams tool activity: `{"type":"tool_call","id","name","args"}` and `{"type":"tool_result","id","name","result"}`. The Next.js `/api/chat` proxy maps them to Vercel AI SDK data-stream parts `9:`/`a:`; `ChatPanel` renders them from `message.toolInvocations`. The contract spans three layers (agent SSE → proxy → UI) — change them together.

### Security

- User LLM API keys: AES-256-GCM encrypted before any persistence
- Bcrypt (cost ≥ 12) for password hashing
- No `logging.debug(credential)` or any credential in log output
- `gitleaks` blocks commits containing secrets patterns

### Dependency Version Integrity

LLMs generate version numbers from training data, not from live registry lookups. A version that looks plausible may not exist, or may exist for one package but not its sibling. Every version written into a dependency file must be verifiable.

Rules:
- **Before writing any version number**, verify it exists: `npm view <pkg>@<ver> version`, `pip index versions <pkg>`, or `docker pull <image>:<tag>`.
- **Lock files are mandatory and must be committed**. They are the primary defence against version hallucinations — a missing or non-existent version causes an immediate install failure rather than a silent runtime surprise.
  - npm: generate and commit `package-lock.json` (`npm install` inside the target Node image) at the same time the code is scaffolded.
  - Python: `uv.lock` is committed at the workspace root. Always run `uv sync` after changing any `pyproject.toml`.
  - Docker Compose: run `docker pull <image>:<tag>` to confirm every image tag exists before committing.
- **Version–feature consistency**: when using a feature that belongs to a specific version (e.g. `next.config.ts` requires Next.js 15+), pin the package to that version — never mix a feature from version N with a pin at version N-1.
- **Align sibling packages**: related packages (e.g. `temporalio/auto-setup` and `temporalio/admin-tools`) must use the same version tag. Never assume version parity across packages with independent release cadences.
- **Infra compose images are digest-pinned** (`tag@sha256:...` in `infra/docker-compose*.yml`): upstream re-tags (e.g. postgres security rebuilds) must arrive as Dependabot PRs through CI, never as silent `docker compose pull` surprises. Never add an unpinned infra image; app images (`ghcr.io/...`) are pinned per-deploy by `deploy.sh` instead.
- **Every image/version change requires human review — NO auto-merge, ever** (owner decision, 2026-07-10): CI proves a new image runs, not that it should be trusted; a human reviewing the Dependabot PR is the final supply-chain gate. Stateful components additionally need release-notes review + a local upgrade test against existing data before merging.

### Infra Image Upgrades

Runbook distilled from the 2026-07 campaign (7 components upgraded, several traps found only by local rehearsal — CI is structurally blind to stateful data-path issues: it runs fresh volumes, and its postgres/redis/rabbitmq come from `ci.yml` services, not compose).

**Per-PR flow (stateful components):** `@dependabot rebase` → official release-notes/upgrading-guide review → **local rehearsal against EXISTING data** (never a fresh volume) → merge → CD green → deploy → prod verify (data reconciliation + real login). Batch multiple verified upgrades into one deploy.

**Choose the migration strategy by what the data IS:**
- **Derived/rebuildable state** (qdrant embeddings, rabbitmq topology+empty queues, redis cache/dedup): fresh-volume recreate is a legitimate — often superior — migration. Preconditions: verify emptiness/rebuildability at cutover (`/collections`, `list_queues`), confirm the rebuild path exists (idempotent redeclare-on-connect; lazy collection creation), and snapshot anyway.
- **Source-of-truth state** (postgres): `pg_dumpall` logical migration with DUAL backups (SQL dump + volume tarball, kept on the server as rollback). Cutover order matters because `up -d` lets clients initialize fresh DBs (alembic / keycloak realm import) before restore: stop clients → dump+tarball → rm container+volume → deploy → stop clients again → `DROP DATABASE ... WITH (FORCE)` one statement per `psql -c` (multi-statement `-c` wraps in a transaction and DROP fails) → restore → `up -d` → reconcile counts + login test.

**Traps already paid for (do not rediscover):**
- `postgres:18+` images store data in a versioned subdir — the volume must mount `/var/lib/postgresql`, NOT `.../data` (docker-library#1259); wrong mount = crash loop.
- Qdrant forbids skipping minor versions on single-node in-place upgrades.
- RabbitMQ 3.13→4.x officially requires a 4.2 hop + all feature flags enabled first (fresh-volume path sidesteps both).
- `temporalio/admin-tools` ≥1.29.7 only ships composite tags (`1.29.7-tctl-…`); its ENTRYPOINT is `tini -- sleep infinity`, so one-shot uses must override `entrypoint: ["sh","-c"]` or the command never runs.
- Dependabot proposes each sibling's registry-latest independently — enforce temporal sibling alignment manually on the PR branch.
- CI integration services in `ci.yml` must be bumped alongside prod versions or they silently drift.

### Engineering Philosophy

Always prefer the proper, maintainable solution over a quick workaround. Before implementing any fix, validate it against industry best practices. If a shortcut is tempting, name it explicitly and propose the correct approach instead. Temporary hacks compound into long-term maintenance debt and block future extensibility.

Concretely:
- When an infrastructure/config error occurs, fix the root cause — do not patch the symptom.
- If two options exist (quick hack vs. proper fix), present both with trade-offs and default to the proper one.
- **When choosing among multiple _legitimate_ options, the recommendation MUST be driven by architectural correctness — NEVER by "smallest change / least effort / least risk / smallest diff." Never list minimal change as a pro of the recommended option. If unsure which option is the best practice, research it before recommending.**
- **Never use production as a debug loop.** Reproduce and verify every fix locally (via `docker compose up`) or in staging BEFORE deploying. Deploy only changes already verified elsewhere — production must not be the test bed. When debugging a frontend↔backend integration, audit BOTH sides of the contract together (schemas + both endpoints) in one pass so all mismatches are caught at once; read-only code tracing alone is insufficient — run it end-to-end. Batch related fixes into a single deploy instead of one-commit-per-bug round-trips.
- **Exercise error paths and service-to-service contracts end-to-end, not just happy paths.** "Contract" includes agent-tool ↔ internal-endpoint bindings and exception-handler paths, not only frontend↔backend. A tool that "fails gracefully" (returns error JSON) hides a missing endpoint — the LLM confabulates a fluent answer on top of it, so nothing looks broken (2026-07-08: 4 of 5 ReAct tools had called nonexistent endpoints since launch, and the shared logging bug turning handled errors into bare 500s was only caught by E2E-running an error path).
- Only proceed with a workaround if the user explicitly accepts it after understanding the trade-offs.
- This applies to: Dockerfiles, Docker Compose, Alembic config, K8s manifests, CI pipelines, framework rendering models, and all architectural decisions.

---

## Pre-Push Checklist

Run these checks locally **before every `git push`**. CI runs the same steps — a push that fails CI wastes a round-trip. All checks must pass with exit code 0.

```bash
# 1. Lint — must produce zero errors
~/.local/bin/uv run ruff check .

# 2. Format — must produce zero diffs
~/.local/bin/uv run ruff format --check .

# 2b. Import boundaries — services must not import each other
~/.local/bin/uv run lint-imports

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

---

## CI Requirements

1. **Lint**: `ruff check .` + `ruff format --check .` + `lint-imports` (service independence contracts)
2. **Type Check**: `mypy` per service
3. **Unit Tests**: `pytest` (no real DB/queue)
4. **Contract Checks**: `pytest tests/contracts` (consumer call sites vs provider OpenAPI) + OpenAPI/TS-type freshness (`scripts/export_openapi.py` → `npm run gen:api-types` → `git diff --exit-code -- openapi frontend/lib/gen`). Entity types in `frontend/lib/api.ts` are re-exports of generated types — NEVER hand-write them.
5. **Integration Tests**: `pytest` against real PostgreSQL + Redis + RabbitMQ, then `alembic check` per service (model↔migration drift fails CI)
6. **Secret Scan**: `gitleaks detect`
7. **Image Scan**: Trivy — Critical CVE blocks the pipeline
8. **E2E Smoke** (CD, gates deploy): Playwright journey (Keycloak login → dashboard → jobs/discovery/profile → chat panel) against the stack running the exact images just pushed to GHCR (`frontend/e2e/`, `infra/docker-compose.e2e.yml`, `infra/scripts/create-test-user.sh`). Run locally with `cd frontend && npm run test:e2e` against a running compose stack.

---

## Git Commit Convention

All commit messages must be **bilingual (English / Chinese)**. Write the subject line in English (following Conventional Commits). The body must contain a **detailed English description AND its Chinese counterpart, side by side** — not Chinese-only.

```
feat(service): add feature X

Detailed English description of what changed and why.

变更内容与原因的详细中文描述。
```

---

## Docs Convention

All documentation files under `docs/` and the `README.md` use **bilingual single-file format**:

```markdown
## N. English Title / 中文标题

**EN:** English content...

**中文：** 中文内容...
```

`CLAUDE.md` is exempt: English-only (owner decision, 2026-07-11).

Mermaid diagram labels use English (universal for technical diagrams).
