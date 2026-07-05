# JobCopilot — Software Architecture Design / 软件架构设计

Version / 版本：v0.1  
Status / 状态：Draft / 草稿  
Last Updated / 最后更新：2026-06-10

---

## 1. System Overview / 系统概述

**EN:**  
JobCopilot is built on a microservices architecture with five application services behind a Kong API Gateway, a Keycloak-backed authentication layer, and a multi-agent AI pipeline powered by LangGraph and orchestrated by Temporal. The frontend is a Next.js 15 application. All services are designed for horizontal scaling on Kubernetes.

**中文：**  
JobCopilot 采用微服务架构，Kong API Gateway 后方部署五个应用服务，通过 Keycloak 实现身份认证，AI 流水线基于 LangGraph 多 Agent 图并由 Temporal 负责工作流编排。前端为 Next.js 15 应用。所有服务均以水平扩展为目标，运行于 Kubernetes 之上。

---

## 2. C4 Architecture Views / C4 架构视图

### 2.1 Level 1 — System Context / 系统上下文

```mermaid
graph TB
    User["👤 Job Seeker\n求职者"]
    Admin["🔧 Tenant Admin\n租户管理员"]

    subgraph JC["JobCopilot Platform"]
        System["JobCopilot\nMulti-Agent Job Management System\n多 Agent 智能求职管理系统"]
    end

    LinkedIn["🔗 LinkedIn\n(External Platform / 外部平台)"]
    DashScope["🤖 DashScope LLM API\n(OpenAI-compatible / OpenAI 兼容)"]
    LangSmith["🔍 LangSmith\n(LLM Observability / LLM 可观测)"]
    SMTP["📧 Email Service\n邮件服务 (SMTP / AWS SES)"]
    Webhook["💬 IM Webhooks\n微信 / 钉钉 Webhook"]

    User -->|"Manage jobs, view analysis\n管理岗位、查看分析、AI 对话"| System
    Admin -->|"Manage members & usage\n管理成员与用量"| System
    System -->|"Playwright browser automation\nPlaywright 模拟登录爬取"| LinkedIn
    System -->|"LLM inference (OpenAI-compatible)\nLLM 推理"| DashScope
    System -->|"Agent trace & debug\nAgent 追踪与调试"| LangSmith
    System -->|"Send email reminders\n发送邮件提醒"| SMTP
    System -->|"Push IM notifications\n发送即时消息通知"| Webhook
```

### 2.2 Level 2 — Container Diagram / 容器图

```mermaid
graph TB
    Browser["🌐 Next.js 15 Frontend\nTypeScript + Tailwind CSS\nVercel AI SDK + assistant-ui"]

    subgraph Gateway["Gateway Layer / 网关层"]
        Kong["Kong API Gateway 3.x\nRouting · Rate Limiting · Auth Plugin\n路由 · 限流 · 认证插件"]
        Keycloak["Keycloak 24\nAuth Service — OIDC / JWT\n身份认证服务"]
    end

    subgraph AppLayer["Application Services / 应用服务层"]
        ProfileSvc["Profile Service\nFastAPI · Python 3.11\nUser profiles & resumes\n用户画像 & 简历管理"]
        JobSvc["Job Service\nFastAPI · Python 3.11\nJob CRUD & Kanban\n岗位管理 & 投递看板"]
        DiscoverySvc["Discovery Service\nFastAPI · Python 3.11\nPlaywright + Temporal Worker\nLinkedIn 爬取 & 工作流"]
        AgentSvc["Agent Service\nFastAPI · Python 3.11\nLangGraph Multi-Agent\nAI 分析 & 助手"]
        NotifSvc["Notification Service\nFastAPI · Python 3.11\nMulti-channel reminders\n多渠道提醒"]
    end

    subgraph WorkflowLayer["Workflow Layer / 工作流层"]
        Temporal["Temporal Server\nDurable Workflow Orchestration\n耐久工作流编排"]
    end

    subgraph MsgLayer["Messaging Layer / 消息层"]
        RabbitMQ["RabbitMQ\nAsync Message Queue\n异步消息队列"]
    end

    subgraph DataLayer["Data Layer / 数据层"]
        PG[("PostgreSQL\nStructured Data\n结构化数据")]
        Qdrant[("Qdrant\nVector Store\n向量存储")]
        Redis[("Redis\nCache & Session\n缓存与会话")]
    end

    Browser -->|"HTTPS"| Kong
    Kong <-->|"JWT validation\nJWT 校验"| Keycloak
    Kong --> ProfileSvc & JobSvc & DiscoverySvc & AgentSvc & NotifSvc

    ProfileSvc --> PG & Qdrant
    JobSvc --> PG
    DiscoverySvc --> Temporal & RabbitMQ
    AgentSvc --> RabbitMQ & Qdrant & PG
    NotifSvc --> PG & Redis

    Temporal -.->|"schedules\n调度"| DiscoverySvc
    RabbitMQ -.->|"job.discovered\n消费"| AgentSvc
    RabbitMQ -.->|"notification.trigger\n消费"| NotifSvc
    Kong -.->|"auth cache TTL 60s\n认证缓存"| Redis
```

### 2.3 Level 3 — Agent Service Components / Agent Service 组件图

```mermaid
graph TB
    subgraph AgentSvc["Agent Service"]
        API["FastAPI Router\n/agent/* · /chat/*"]

        subgraph Graphs["LangGraph Graphs"]
            AnalyzerG["AnalyzerGraph\nJob deep analysis\n岗位深度分析"]
            ResumeG["ResumeGraph\nResume matching & optimization\n简历匹配与优化"]
            InterviewG["InterviewGraph\nInterview question generation\n面试题生成"]
            ReactG["ReActGraph\nAI Assistant — Tool Use\nAI 助手工具调用"]
        end

        subgraph Tools["ReAct Tools / ReAct 工具集"]
            T1["analyze_job(url)\n分析岗位"]
            T2["update_kanban(job_id, status)\n更新看板"]
            T3["search_jobs(query)\n搜索岗位"]
            T4["get_applications(filters)\n查询投递"]
            T5["prepare_interview(job_id)\n生成面试题"]
        end

        Consumer["RabbitMQ Consumer\njob.discovered queue\n消费发现岗位消息"]
    end

    API --> AnalyzerG & ResumeG & InterviewG & ReactG
    Consumer --> AnalyzerG
    ReactG --> T1 & T2 & T3 & T4 & T5
    T1 -.->|"delegates to\n委托执行"| AnalyzerG
    T5 -.->|"delegates to\n委托执行"| InterviewG
```

---

## 3. AI Agent Architecture / AI Agent 体系

**EN:**  
Four LangGraph graphs share a common DashScope LLM client. Temporal handles durability and scheduling; LangGraph handles agent reasoning logic. These two frameworks are complementary, not competing.

**中文：**  
四个 LangGraph 图共享同一个 DashScope LLM 客户端。Temporal 负责耐久性与调度，LangGraph 负责 Agent 推理逻辑，两者互补而非竞争。

```mermaid
graph LR
    subgraph "Temporal Activity"
        TW["Discovery Workflow\n发现工作流"]
    end

    subgraph "LangGraph Graphs / LangGraph 图"
        AG["AnalyzerGraph\n① Extract JD structure\n② Generate embedding\n③ Compute match score"]
        RG["ResumeGraph\n① Gap analysis\n② Score (0-100)\n③ Tailored suggestions"]
        IG["InterviewGraph\n① Behavioral questions\n② Technical questions\n③ Reference answers"]
        ReactG["ReActGraph (AI Assistant)\n① Parse user intent\n② Select tool\n③ Execute & stream"]
    end

    LLM["DashScope LLM\n(OpenAI-compatible)"]
    LS["LangSmith\nTrace & Debug"]

    TW -->|"crawled job data\n爬取数据"| AG
    AG & RG & IG & ReactG -->|"LLM calls\nLLM 调用"| LLM
    AG & RG & IG & ReactG -.->|"traces\n追踪"| LS
```

---

## 4. Temporal Workflow Design / Temporal 工作流设计

**EN:**  
Discovery workflows are the primary use of Temporal. Each Activity is independently retryable with configurable backoff, so a transient LinkedIn failure does not re-crawl from the beginning.

**中文：**  
岗位发现工作流是 Temporal 的主要应用场景。每个 Activity 均可独立重试并配置退避策略，LinkedIn 暂时性失败不会导致从头重爬。

```mermaid
flowchart TD
    Sched["Temporal Scheduler\nCron / Manual Trigger\n定时 / 手动触发"]

    Sched --> WF["DiscoveryWorkflow\nuser_id · config_id · run_id"]

    WF --> A1["Activity: ValidateCookieActivity\nVerify LinkedIn Cookie validity\n验证 LinkedIn Cookie 有效性\nTimeout: 10s · Retry: 2"]
    A1 -->|"Cookie valid / Cookie 有效"| A2["Activity: SearchLinkedInActivity\nPlaywright: login + paginated search\nPlaywright 模拟登录 + 分页搜索\nTimeout: 5min · Retry: 3"]
    A1 -->|"Cookie expired / Cookie 失效"| NF["Publish: cookie.expired\n→ NotificationService 发送失效通知"]

    A2 --> A3["Activity: ParseJobsActivity\nExtract structured fields from HTML\n从 HTML 提取结构化字段\nTimeout: 30s · Retry: 3"]
    A3 --> A4["Activity: DeduplicateActivity\nFilter by URL against existing jobs DB\n基于 URL 对比已有岗位去重\nTimeout: 10s · Retry: 2"]
    A4 --> A5["Activity: PublishJobsActivity\nBatch publish to RabbitMQ: job.discovered\n批量发布到 RabbitMQ\nTimeout: 30s · Retry: 3"]
    A5 --> Done["Workflow Complete\n工作流完成\nUpdate last_run_at"]

    NF --> End["Workflow End\n工作流结束"]
```

---

## 5. Key Sequence Diagrams / 关键流程时序图

### 5.1 Auto Job Discovery / 自动岗位发现

```mermaid
sequenceDiagram
    actor User
    participant FE as Next.js Frontend
    participant Kong as Kong Gateway
    participant DS as Discovery Service
    participant TW as Temporal
    participant PW as Playwright Activity
    participant LI as LinkedIn
    participant MQ as RabbitMQ
    participant AS as Agent Service
    participant LG as LangGraph (AnalyzerGraph)
    participant LLM as DashScope LLM
    participant JS as Job Service
    participant DB as PostgreSQL
    participant QD as Qdrant

    User->>FE: Configure search criteria & trigger crawl
    FE->>Kong: POST /discovery/runs
    Kong->>DS: JWT verified + forward
    DS->>TW: StartWorkflow(DiscoveryWorkflow, config)
    TW-->>DS: run_id
    DS-->>Kong: 202 Accepted { run_id }
    Kong-->>FE: 202 { run_id }
    FE-->>User: "Crawl job started / 爬取任务已启动"

    Note over TW,LI: Temporal executes workflow asynchronously / Temporal 异步执行工作流

    TW->>PW: ValidateCookieActivity
    PW->>LI: HEAD request to verify cookie
    LI-->>PW: 200 OK
    TW->>PW: SearchLinkedInActivity
    PW->>LI: Playwright login + paginated search
    LI-->>PW: Job listing HTML
    PW-->>TW: raw_jobs[]
    TW->>PW: DeduplicateActivity
    PW-->>TW: new_jobs[] (deduplicated)
    TW->>PW: PublishJobsActivity
    PW->>MQ: publish job.discovered (batch)
    PW-->>TW: published_count

    Note over MQ,AS: Async consumption / 异步消费

    AS->>MQ: consume job.discovered
    AS->>LG: AnalyzerGraph.invoke(job_data)
    LG->>LLM: Extract JD structure + generate embedding
    LLM-->>LG: structured_jd + vector
    LG-->>AS: analysis_result
    AS->>JS: POST /internal/jobs (save)
    JS->>DB: INSERT INTO jobs
    AS->>QD: upsert job embedding
    AS->>MQ: publish notification.job_discovered

    FE-->>User: Discovery list updated (WebSocket push / polling)
```

### 5.2 AI Assistant Tool Call / AI 助手工具调用

```mermaid
sequenceDiagram
    actor User
    participant FE as Next.js (useChat)
    participant Kong as Kong Gateway
    participant AS as Agent Service
    participant LG as LangGraph (ReActGraph)
    participant LLM as DashScope LLM
    participant JS as Job Service
    participant MQ as RabbitMQ

    User->>FE: "Analyze this job https://linkedin.com/jobs/xxx"
    FE->>Kong: POST /agent/chat/stream
    Kong->>AS: JWT verified + forward
    AS->>LG: ReActGraph.stream(message, context)

    LG->>LLM: messages + tool definitions (SSE)
    LLM-->>LG: ToolCall: analyze_job(url="https://...")

    LG->>AS: execute tool: analyze_job
    AS->>MQ: publish job.analyze.priority { url, user_id }
    AS-->>LG: ToolResult { job_id, status: "queued", eta: "2min" }

    LG->>LLM: append ToolResult, request final reply
    LLM-->>LG: stream tokens "Job added to analysis queue..."
    LG-->>AS: token stream (SSE)
    AS-->>Kong: SSE pass-through
    Kong-->>FE: SSE stream
    FE-->>User: "已将岗位加入分析队列，预计 2 分钟后完成 ✓"
```

### 5.3 Resume Matching Analysis / 简历匹配分析

```mermaid
sequenceDiagram
    actor User
    participant FE as Next.js Frontend
    participant Kong as Kong Gateway
    participant AS as Agent Service
    participant LG as LangGraph (ResumeGraph)
    participant LLM as DashScope LLM
    participant PS as Profile Service
    participant JS as Job Service
    participant DB as PostgreSQL

    User->>FE: View job detail → click "Match Analysis / 匹配分析"
    FE->>Kong: POST /agent/match { job_id }
    Kong->>AS: JWT verified + forward

    AS->>PS: GET /internal/profiles/{user_id}
    PS->>DB: SELECT resume + preferences WHERE user_id
    PS-->>AS: resume_data

    AS->>JS: GET /internal/jobs/{job_id}
    JS->>DB: SELECT job + analysis WHERE job_id AND tenant_id
    JS-->>AS: job_data

    AS->>LG: ResumeGraph.invoke(resume_data, job_data)

    LG->>LLM: Identify skill gaps
    LLM-->>LG: skill_gaps[]
    LG->>LLM: Compute match score (0-100)
    LLM-->>LG: match_score
    LG->>LLM: Generate tailored optimization suggestions
    LLM-->>LG: suggestions[]

    LG-->>AS: { match_score, skill_gaps, suggestions }
    AS->>JS: PATCH /internal/applications/{id}/analysis
    JS->>DB: UPDATE applications SET match_score, resume_suggestions

    AS-->>Kong: { match_score, skill_gaps, suggestions }
    Kong-->>FE: Analysis result
    FE-->>User: Display score + gaps + suggestions
```

### 5.4 Notification Reminder Trigger / 通知提醒触发

```mermaid
sequenceDiagram
    participant TS as Temporal Scheduler
    participant NS as Notification Service
    participant DB as PostgreSQL
    participant Redis as Redis
    participant Email as SMTP / SES
    participant WH as WeChat / DingTalk Webhook
    participant FE as Next.js (WebSocket)

    Note over TS,NS: Triggered hourly by Temporal / 每小时由 Temporal 触发

    TS->>NS: CheckRemindersWorkflow
    NS->>DB: SELECT overdue applications\n(status=applied, updated_at < NOW()-N days)
    DB-->>NS: overdue_list[]

    loop For each overdue application / 每条逾期投递
        NS->>DB: SELECT notification_settings WHERE user_id
        NS->>Redis: GET notified:{user_id}:{app_id} (dedup check)

        alt Email channel enabled
            NS->>Email: Send follow-up reminder email
        end
        alt WeChat webhook configured
            NS->>WH: POST WeChat webhook payload
        end
        alt DingTalk webhook configured
            NS->>WH: POST DingTalk webhook payload
        end

        NS->>DB: INSERT INTO notifications (in-app)
        NS->>Redis: SET notified:{user_id}:{app_id} TTL 24h
        NS->>FE: WebSocket push (if user online)
    end
```

---

## 6. Application Status Machine / 投递状态机

**EN:**  
All status transitions are persisted to `application_events` with a timestamp. Transitions from `Rejected` and `Withdrawn` are terminal.

**中文：**  
所有状态转换均记录到 `application_events` 表并附时间戳。`Rejected` 和 `Withdrawn` 为终止状态。

```mermaid
stateDiagram-v2
    [*] --> Discovered : Job found / added\n岗位发现 / 手动添加
    Discovered --> Applied : User submits application\n用户投递
    Discovered --> Withdrawn : User abandons\n用户放弃

    Applied --> Interviewing : Interview invitation received\n收到面试邀请
    Applied --> Rejected : Application rejected\n申请被拒
    Applied --> Withdrawn : User withdraws\n主动放弃

    Interviewing --> Offer : Offer received\n拿到 Offer
    Interviewing --> Rejected : Interview failed\n面试未通过
    Interviewing --> Withdrawn : User withdraws\n主动放弃

    Offer --> [*] : Accept / Decline Offer\n接受 / 拒绝 Offer
    Rejected --> [*]
    Withdrawn --> [*]
```

---

## 7. Data Model / 数据模型

**EN:**  
All tables include `tenant_id` where applicable. Every query against tenant-scoped tables **must** include `WHERE tenant_id = :tenant_id`. Cross-schema JOINs are forbidden; inter-service data exchange uses internal APIs.

**中文：**  
所有表在适用时均含 `tenant_id`。针对租户范围表的每条查询**必须**包含 `WHERE tenant_id = :tenant_id`。禁止跨 Schema JOIN，服务间数据交换通过内部 API 进行。

```mermaid
erDiagram
    TENANTS {
        uuid tenant_id PK
        string name
        string plan
        int quota_ai_calls
        int quota_crawls
        timestamp created_at
    }

    USERS {
        uuid user_id PK
        uuid tenant_id FK
        string email
        string name
        string role
        string keycloak_id
        timestamp created_at
    }

    PROFILES {
        uuid profile_id PK
        uuid user_id FK
        jsonb personal_info
        jsonb preferences
        text linkedin_cookie_enc
        text llm_api_key_enc
        timestamp updated_at
    }

    RESUMES {
        uuid resume_id PK
        uuid user_id FK
        string file_name
        string file_url
        jsonb parsed_data
        vector embedding
        int version
        boolean is_active
        timestamp created_at
    }

    COMPANIES {
        uuid company_id PK
        uuid tenant_id FK
        string name
        string industry
        string size
        string website
        text notes
        boolean is_blacklisted
        timestamp created_at
    }

    USER_COMPANY_WATCHLIST {
        uuid user_id FK
        uuid company_id FK
        timestamp created_at
    }

    JOBS {
        uuid job_id PK
        uuid tenant_id FK
        uuid company_id FK
        string title
        string company_name
        text url
        string source
        text raw_jd
        jsonb analysis
        vector embedding
        int salary_min
        int salary_max
        string location
        string job_type
        timestamp discovered_at
        timestamp created_at
    }

    APPLICATIONS {
        uuid application_id PK
        uuid user_id FK
        uuid job_id FK
        string status
        float match_score
        jsonb resume_suggestions
        text notes
        timestamp applied_at
        timestamp updated_at
        timestamp created_at
    }

    APPLICATION_EVENTS {
        uuid event_id PK
        uuid application_id FK
        string from_status
        string to_status
        text note
        timestamp created_at
    }

    INTERVIEW_PREPS {
        uuid prep_id PK
        uuid application_id FK
        jsonb questions
        timestamp generated_at
    }

    NOTIFICATIONS {
        uuid notif_id PK
        uuid user_id FK
        string type
        string title
        text body
        uuid related_id
        boolean is_read
        timestamp created_at
    }

    NOTIFICATION_SETTINGS {
        uuid setting_id PK
        uuid user_id FK
        jsonb channels
        jsonb rules
        timestamp updated_at
    }

    DISCOVERY_CONFIGS {
        uuid config_id PK
        uuid user_id FK
        text_array keywords
        text_array locations
        text_array job_types
        int salary_min
        boolean is_active
        string schedule_cron
        timestamp last_run_at
        timestamp created_at
    }

    TENANTS ||--o{ USERS : "has"
    USERS ||--o| PROFILES : "has"
    USERS ||--o{ RESUMES : "uploads"
    USERS ||--o{ DISCOVERY_CONFIGS : "configures"
    USERS ||--o| NOTIFICATION_SETTINGS : "configures"
    USERS ||--o{ NOTIFICATIONS : "receives"
    USERS ||--o{ USER_COMPANY_WATCHLIST : "watches"
    TENANTS ||--o{ JOBS : "owns"
    TENANTS ||--o{ COMPANIES : "tracks"
    COMPANIES ||--o{ JOBS : "posts"
    COMPANIES ||--o{ USER_COMPANY_WATCHLIST : "in"
    USERS ||--o{ APPLICATIONS : "creates"
    JOBS ||--o{ APPLICATIONS : "receives"
    APPLICATIONS ||--o{ APPLICATION_EVENTS : "logs"
    APPLICATIONS ||--o| INTERVIEW_PREPS : "has"
```

---

## 8. Inter-Service Communication / 服务间通信规范

**EN:**

| Pattern | Usage | Details |
|---|---|---|
| Sync (internal) | Service-to-service API calls | Via K8s DNS (not through Kong); timeout 500ms |
| Async | Job discovery → AI analysis | RabbitMQ `job.discovered` queue; at-least-once delivery |
| Async | AI analysis done → notification | RabbitMQ `notification.trigger` queue |
| Streaming | AI chat responses | Server-Sent Events (SSE) from Agent Service |
| Push | Real-time in-app notifications | WebSocket from Notification Service |

**中文：**

| 模式 | 用途 | 详细 |
|---|---|---|
| 同步（内部） | 服务间 API 调用 | 通过 K8s DNS（不经 Kong）；超时 500ms |
| 异步 | 岗位发现 → AI 分析 | RabbitMQ `job.discovered` 队列；at-least-once 投递 |
| 异步 | AI 分析完成 → 通知 | RabbitMQ `notification.trigger` 队列 |
| 流式 | AI 聊天响应 | Agent Service 输出 SSE |
| 推送 | 实时站内通知 | Notification Service 维持 WebSocket |

**Queue Definitions / 队列定义：**

| Queue | Producer | Consumer | Dead Letter Queue |
|---|---|---|---|
| `job.discovered` | Discovery Service | Agent Service | `job.discovered.dlq` |
| `job.analyze.priority` | Agent Service (chat tool) | Agent Service | `job.analyze.dlq` |
| `notification.trigger` | Agent Service | Notification Service | `notification.dlq` |
| `cookie.expired` | Discovery Service | Notification Service | — |

---

## 9. Observability Design / 可观测性设计

**EN:**  
All services implement the three pillars of observability. Metric names are prefixed with `jobcopilot_`. LangGraph traces are additionally forwarded to LangSmith for AI-specific debugging.

**中文：**  
所有服务实现可观测性三支柱。指标名称统一前缀 `jobcopilot_`。LangGraph 追踪额外转发至 LangSmith 用于 AI 专项调试。

```mermaid
graph LR
    subgraph Services["Application Services"]
        PS["Profile\nService"]
        JS["Job\nService"]
        DS["Discovery\nService"]
        AS["Agent\nService"]
        NS["Notification\nService"]
    end

    subgraph Logs["Logs / 日志"]
        Promtail["Promtail\nLog collector"]
        Loki["Loki\nLog aggregation"]
    end

    subgraph Metrics["Metrics / 指标"]
        Prometheus["Prometheus\n/metrics scrape"]
    end

    subgraph Traces["Traces / 追踪"]
        OTel["OpenTelemetry\nCollector"]
        Tempo["Tempo\nDistributed tracing"]
    end

    subgraph LLMObs["LLM Observability"]
        LangSmith["LangSmith\nAgent trace & debug"]
    end

    Grafana["📊 Grafana\nUnified dashboards\n统一可视化看板"]

    Services -->|"Structured JSON logs"| Promtail --> Loki
    Services -->|"GET /metrics"| Prometheus
    Services -->|"OTel SDK traces"| OTel --> Tempo
    AS -->|"LangGraph traces"| LangSmith

    Loki --> Grafana
    Prometheus --> Grafana
    Tempo --> Grafana
```

**Required Metrics / 必需指标：**

| Metric | Type | Description |
|---|---|---|
| `jobcopilot_http_requests_total` | Counter | Total HTTP requests by service/endpoint/status |
| `jobcopilot_http_request_duration_seconds` | Histogram | Request latency |
| `jobcopilot_llm_calls_total` | Counter | Total LLM calls by graph/model |
| `jobcopilot_llm_call_duration_seconds` | Histogram | LLM call latency |
| `jobcopilot_crawl_jobs_discovered_total` | Counter | Jobs discovered per crawl run |
| `jobcopilot_mq_messages_consumed_total` | Counter | RabbitMQ messages consumed by queue |
| `jobcopilot_active_temporal_workflows` | Gauge | Active Temporal workflow count |

---

## 10. Security Design / 安全设计

**EN:**

| Area | Requirement |
|---|---|
| Authentication | Keycloak 24 OIDC; JWT RS256; access token TTL 15 min; refresh token TTL 7 days |
| Authorization | RBAC: Admin / Member roles; all queries include `tenant_id` filter |
| Credential storage | LinkedIn Cookie and API Keys encrypted with AES-256-GCM before persistence; plaintext never logged |
| Cookie revocation | Cookie marked invalid within 60 s across all replicas (Redis cache TTL ≤ 60 s) |
| API Key storage | Bcrypt or Argon2 hash; no MD5 / SHA-1; no plaintext in DB or Git |
| SQL injection | Parameterized queries (SQLAlchemy prepared statements) everywhere; string-interpolated SQL is forbidden |
| Input validation | Pydantic schema validation on all API inputs; malformed requests rejected at the API layer |
| Container security | Multi-stage Dockerfile; production stage uses `python:3.11-slim`; runs as non-root (`uid=1000`) |
| Secrets management | All secrets injected via environment variables / K8s Secrets; never baked into images or committed to Git |
| Network policy | K8s NetworkPolicy: services only accept traffic from their allowed callers |
| Rate limiting | Kong rate-limiting plugin: per-tenant sliding window |

**中文：**

| 领域 | 要求 |
|---|---|
| 认证 | Keycloak 24 OIDC；JWT RS256；访问令牌 TTL 15 分钟；刷新令牌 TTL 7 天 |
| 授权 | RBAC：Admin / Member 角色；所有查询必须含 `tenant_id` 过滤条件 |
| 凭证存储 | LinkedIn Cookie 与 API Key 持久化前 AES-256-GCM 加密；明文绝不写入日志 |
| Cookie 吊销 | 60 秒内在所有副本上生效（Redis 缓存 TTL ≤ 60 s） |
| SQL 注入防护 | 全链路 SQLAlchemy 参数化查询；禁止字符串拼接 SQL |
| 输入校验 | 所有 API 入参 Pydantic 校验；格式非法请求在 API 层拒绝 |
| 容器安全 | 多阶段 Dockerfile；生产阶段 `python:3.11-slim`；非 root 用户运行（uid=1000） |
| 密钥管理 | 所有密钥通过环境变量 / K8s Secrets 注入；禁止打入镜像或提交 Git |
| 网络隔离 | K8s NetworkPolicy：每个服务只接受来自授权调用方的流量 |
| 限流 | Kong rate-limiting 插件：按租户滑动窗口限流 |

---

## 11. Deployment Architecture / 部署架构

**EN:**  
All workloads run on Kubernetes. The frontend is served as a static Next.js build. Agent Service scales via KEDA based on RabbitMQ queue depth. Profile and Job Services scale via HPA based on CPU.

**中文：**  
所有工作负载运行于 Kubernetes 之上。前端以 Next.js 静态构建产物方式服务。Agent Service 基于 RabbitMQ 队列积压深度由 KEDA 弹性伸缩；Profile Service 和 Job Service 基于 CPU 由 HPA 伸缩。

```mermaid
graph TB
    Internet["🌐 Internet"]

    subgraph K8s["Kubernetes Cluster"]
        subgraph ingress["ingress-nginx namespace"]
            KIC["Kong Ingress Controller\n+ TLS termination"]
        end

        subgraph auth["auth namespace"]
            KC["Keycloak 24\nStatefulSet"]
        end

        subgraph temporal["temporal namespace"]
            TW["Temporal Server\n+ Temporal UI"]
        end

        subgraph app["jobcopilot namespace"]
            subgraph deps["Deployments"]
                FE["frontend\n(Next.js)\nreplicas: 2"]
                PS["profile-service\nHPA: CPU > 50%"]
                JS["job-service\nHPA: CPU > 50%"]
                DS["discovery-service\nreplicas: 1"]
                AS["agent-service\nKEDA: MQ depth > 20"]
                NS["notification-service\nreplicas: 1"]
            end

            subgraph sts["StatefulSets"]
                PG["PostgreSQL\n(primary + replica)"]
                QD["Qdrant\nStatefulSet"]
                RD["Redis\nStatefulSet"]
                RMQ["RabbitMQ\nStatefulSet"]
            end
        end

        subgraph monitoring["monitoring namespace"]
            Prom["Prometheus"]
            Graf["Grafana"]
            Loki2["Loki"]
            Tempo2["Tempo"]
        end
    end

    Internet --> KIC
    KIC --> FE & PS & JS & DS & AS & NS
    PS & JS & AS --> PG
    AS --> QD
    DS --> RMQ
    AS --> RMQ
    NS --> RD
    DS --> TW
```

**K8s Resource Checklist / K8s 资源清单要求：**

Every application service must provide / 每个应用服务须提供：
- `Deployment` with `terminationGracePeriodSeconds ≥ 30`
- `Service` (ClusterIP)
- `ConfigMap` (non-secret config)
- `HPA` or `ScaledObject` (KEDA)
- `PodDisruptionBudget` (minAvailable: 1)
- `Ingress` / `HTTPRoute` (via Kong)
- Liveness probe: `GET /healthz/live`
- Readiness probe: `GET /healthz/ready`

---

## 12. Architecture Decision Records / 架构决策记录 (ADR)

### ADR-001: LangGraph for AI Agent Orchestration

**EN:** LangGraph is selected because it provides stateful, graph-based agent execution with conditional edges, native streaming, and first-class LangSmith tracing integration. Alternatives (vanilla LangChain chains, AutoGen) lack the same level of controllability and observability.

**中文：** 选用 LangGraph，因为它提供有状态的图式 Agent 执行、条件边、原生流式输出，以及与 LangSmith 的一等公民追踪集成。备选方案（原生 LangChain chains、AutoGen）在可控性和可观测性上不及此方案。

---

### ADR-002: Temporal for Workflow Orchestration

**EN:** Temporal handles durable execution for long-running LinkedIn crawl workflows. It provides built-in retry semantics, timeouts, and visibility—replacing fragile ad-hoc retry loops. LangGraph and Temporal are used together: Temporal manages workflow lifecycle; LangGraph runs within Temporal Activities for AI reasoning.

**中文：** Temporal 负责长时运行的 LinkedIn 爬取工作流的耐久执行，提供内建重试语义、超时控制和可见性，取代脆弱的自定义重试逻辑。Temporal 与 LangGraph 配合使用：Temporal 管理工作流生命周期，LangGraph 在 Temporal Activity 内执行 AI 推理。

---

### ADR-003: Qdrant for Vector Storage

**EN:** Qdrant is chosen over pgvector because it provides dedicated ANN indexing, multi-tenancy via named collections or payload filters, and scales independently of the relational database. pgvector remains available via PostgreSQL for lightweight similarity needs.

**中文：** 选用 Qdrant 而非 pgvector，因为 Qdrant 提供专用 ANN 索引、通过命名集合或 payload 过滤实现多租户隔离，并可独立于关系型数据库扩展。pgvector 仍通过 PostgreSQL 保留，用于轻量级相似度需求。

---

### ADR-004: Per-User LinkedIn Cookie (Not Shared Account)

**EN:** Each user supplies their own LinkedIn Session Cookie. This eliminates single-account ban risk, ensures personalized search results, and removes the legal/ethical concern of a shared scraped account. Cookies are encrypted with AES-256-GCM before persistence.

**中文：** 每个用户提供自己的 LinkedIn Session Cookie，而非共用账号。这消除了单账号被封的风险，确保个性化搜索结果，也避免了共享爬取账号的法律/道德风险。Cookie 在持久化前经 AES-256-GCM 加密。

---

### ADR-005: Vercel AI SDK + assistant-ui for Chat Frontend

**EN:** Vercel AI SDK (`useChat`) handles the SSE streaming protocol and tool-call lifecycle on the frontend. `assistant-ui` provides headless, accessible chat components (Thread, Message, ToolResult) that integrate natively with Vercel AI SDK and support shadcn/ui theming. This avoids building chat UI infrastructure from scratch.

**中文：** Vercel AI SDK (`useChat`) 处理前端 SSE 流式协议和工具调用生命周期。`assistant-ui` 提供 headless、无障碍聊天组件（Thread、Message、ToolResult），与 Vercel AI SDK 原生集成，支持 shadcn/ui 主题。避免从零搭建聊天 UI 基础设施。
