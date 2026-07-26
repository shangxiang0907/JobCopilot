# JobCopilot — Product Requirements Document / 产品需求文档

Version / 版本：v0.3  
Status / 状态：Active / 生效  
Last Updated / 最后更新：2026-07-26

> **v0.3 change summary / 变更摘要：** Corrects a **layering inversion**, not the feature set. v0.2 shipped with AI as a load-bearing component: adding a job posting — a basic write operation — was reachable only through the LLM chat assistant, and `analyze` / `match` / `interview` had no non-AI entry point at all. Meanwhile the manual CRUD the v0.2 page inventory already specified (`/companies`, `/kanban`, manual job create/edit) was never implemented, so this is as much implementation drift as it is a re-scope. v0.3 establishes an explicit two-layer product: a **complete non-AI core** (resume library, job library, company library, application pipeline — all fully manual CRUD) with **AI strictly as an augmentation layer on top**. New requirements: per-application resume selection, `is_active` → default-resume semantics, resume labels, company auto-linking by name, and a hard acceptance criterion that the product remains fully usable with AI entirely disabled. Browser-extension job ingestion is recorded as a design (SAD ADR-009) but deliberately not scheduled. / 本次修正的是**分层倒置**，而非功能范围。v0.2 上线后 AI 成了承重构件：连"添加一个岗位"这种最基础的写操作也只能通过 LLM 聊天助手完成，`analyze` / `match` / `interview` 更是没有任何非 AI 入口；同时 v0.2 页面清单里早已写明的手动 CRUD（`/companies`、`/kanban`、手动新建/编辑岗位）从未实现——因此这既是重新定位，也是对实现偏离的纠正。v0.3 确立明确的两层产品结构：**完备的非 AI 基础层**（简历库、岗位库、公司库、投递流程，全部支持手动增删改查），**AI 严格作为其上的叠加层**。新增需求：按投递选择简历、`is_active` 语义改为默认简历、简历标签、按公司名自动挂接，以及一条硬性验收标准——AI 全部关闭时产品仍然完整可用。浏览器插件式岗位录入已记录为设计（SAD ADR-009），但刻意不排期。

> **v0.2 change summary / 变更摘要：** Re-scoped from LinkedIn-centric B2B/B2C hybrid to a general-purpose B2C platform. Credential-based LinkedIn crawling removed in favor of no-login public job sources plus three manual JD entry paths (URL / pasted text / screenshot). Tenant-admin (multi-seat B2B) features removed; Platform Admin (operator) introduced. Analytics module removed. Notifications converged to email. Dual deployment modes for LLM key sourcing. / 从 LinkedIn 中心的 B2B/B2C 混合定位重构为通用 B2C 平台：移除凭证式 LinkedIn 爬取，改为无登录公开职位源 + 三种手动 JD 录入（URL / 文本粘贴 / 截图）；删除租户管理员（多席位 B2B）功能，引入平台管理员（运营者）；删除数据分析模块；通知收敛为邮件；LLM Key 按部署形态双模式。

---

## 1. Product Overview / 产品概述

**EN:**  
JobCopilot is a production-grade intelligent job-search management platform. The system uses a multi-AI-agent architecture to discover job listings from public job boards and analyze them, provides resume match scoring and optimization suggestions, manages the entire application pipeline via a Kanban board, and supports natural-language actions through a global AI assistant. Users can add any job posting from any site via URL, pasted JD text, or a screenshot.

The project is open source and runs in two deployment modes:
- **Self-hosted**: anyone can deploy the full stack; the operator/users configure their own OpenAI-compatible LLM API key.
- **Official hosted site**: users sign up and use the platform-provided LLM API (bring-your-own-key is disabled there).

**中文：**  
JobCopilot 是一个生产级智能求职管理平台。系统通过多 AI Agent 架构从公开职位站点发现并分析岗位，结合个人简历提供匹配评分与优化建议，以看板形式管理全部投递进程，并通过全局 AI 助手支持自然语言触发操作。用户可以通过 URL、粘贴 JD 文本或截图，把任意站点的岗位加入系统。

项目开源，支持两种部署形态：
- **自部署**：任何人可部署完整技术栈，由部署者/用户自行配置 OpenAI 兼容的大模型 API Key。
- **官方托管站**：用户注册后使用平台提供的大模型 API（托管站不开放自带 Key）。

**Core Value Propositions / 核心价值主张：**

| Value / 价值 | EN | 中文 |
|---|---|---|
| Save time | Auto-discovers jobs from public job boards; add any posting in one paste | 自动从公开职位源发现岗位，任意岗位一键粘贴录入 |
| Higher hit rate | AI analyzes JD + resume, pinpoints gaps, gives tailored suggestions | AI 分析 JD + 简历，精准找出差距并给出定制化建议 |
| Never forget | Kanban board + email reminders | 看板 + 邮件智能提醒，确保每条投递都有跟进 |
| AI always on | Global AI assistant for natural-language-triggered actions | 全局 AI 助手支持自然语言触发后台动作 |

---

## 2. Target Users / 目标用户

**EN:**

| Role | Description | Core Need |
|---|---|---|
| **Job Seeker** (primary) | Actively job-hunting, tracking multiple positions; self-registers on the platform | Efficient discovery, precise matching, never miss a follow-up |
| **Platform Admin** (operator) | The owner operating the hosted site | User account management, per-user usage visibility |

Multi-tenancy note: each user is provisioned as their own tenant. `tenant_id` isolation remains a hard architectural boundary (see SAD), but no user-facing team/seat management exists.

**中文：**

| 角色 | 描述 | 核心诉求 |
|---|---|---|
| **求职者**（主要用户） | 正在主动求职，同时跟进多个职位；自助注册使用平台 | 高效发现岗位、精准匹配、不遗漏跟进 |
| **平台管理员**（运营者） | 托管站的所有者 | 用户账号管理、按用户查看用量 |

多租户说明：每个用户即一个租户。`tenant_id` 隔离仍是硬性架构边界（见 SAD），但不存在面向用户的团队/席位管理功能。

---

## 3. Feature Modules / 功能模块

### 3.0 Layering Principle / 分层原则 (v0.3)

**EN:**
The product has exactly two layers, and the dependency direction between them is one-way.

| Layer | Contents | Rule |
|---|---|---|
| **Core / 基础层** (non-AI) | Resume library, job library, company library, application pipeline + status machine, notifications, account settings. Every entity supports **manual create / read / update / delete** through an ordinary form — no LLM involved. | Must be complete and usable on its own. Never depends on the AI layer. |
| **AI / 叠加层** | Match scoring & gap analysis, JD parsing from text/screenshot, interview question generation, company research, the chat agent. | May depend on the Core layer. Is always an *addition* to a manual path that already exists. |

Binding rules (all four are testable, not aspirational):
1. **One-way dependency.** Core code must never import or call the AI layer. Enforced as an `import-linter` contract in CI, like the existing service-independence contracts.
2. **No AI-only entry points.** Every capability that writes data must have a non-AI path. AI may offer a faster path to the same operation; it may never be the only path.
3. **AI output is always overwritable.** Anything AI produces (match score, gap analysis, company research, interview questions) must be editable or replaceable by hand, and must be stamped with its provenance (`source: ai | manual`, model, generated timestamp). AI must never silently overwrite a value the user typed.
4. **No-AI mode is an acceptance criterion.** With AI fully disabled (no key configured, AI features switched off), the product must still be a complete job-search tracker. Guarded by a dedicated E2E test, not by inspection.

Why this matters (the v0.2 failure mode): because job entry ran through the chat agent, a used-up daily AI quota, a missing API key, or a silently-degrading LLM call each took out a *basic data-entry function*. It also made every test of a basic feature cost tokens, which conflicts with the project's token-frugality rule.

**中文：**
产品只有两层，且层间依赖方向单向。

| 层 | 内容 | 规则 |
|---|---|---|
| **基础层**（非 AI） | 简历库、岗位库、公司库、投递流程与状态机、通知、账号设置。每个实体都能通过普通表单**手动增删改查**，不涉及任何 LLM。 | 必须独立完整可用，永不依赖 AI 层。 |
| **AI 叠加层** | 匹配评分与差距分析、从文本/截图解析 JD、面试题生成、企业调查、聊天 Agent。 | 可以依赖基础层；永远是对**已存在的手动路径**的增强。 |

约束规则（四条都可测，不是口号）：
1. **单向依赖**：基础层代码绝不 import 或调用 AI 层。以 `import-linter` 契约在 CI 中固化，与现有的服务独立性契约同一机制。
2. **不存在纯 AI 入口**：任何写数据的能力都必须有非 AI 路径。AI 可以提供更快的同等操作路径，但绝不能是唯一路径。
3. **AI 产出永远可覆写**：AI 生成的一切（匹配分、差距分析、企业调查、面试题）都必须可手动编辑或替换，并标注来源（`source: ai | manual`、模型、生成时间）。AI 绝不静默覆盖用户手填的值。
4. **无 AI 模式是验收标准**：AI 全部关闭时（未配置 Key、AI 功能关停），产品仍须是一个完整的求职跟踪工具。由专门的 E2E 测试守卫，而非人工检查。

为什么重要（v0.2 的真实故障模式）：由于录入岗位要经过聊天 Agent，每日 AI 配额用尽、未配置 Key、或一次静默降级的 LLM 调用，都会直接打掉一个**基础录入功能**；同时也使得测试基础功能必须消耗 token，与项目的 token 节俭规则直接冲突。

### 3.1 Job Discovery / 岗位发现 `[Core + AI]`

**EN:**
- User configures search criteria: keywords, city, job type, posting date range, salary range
- The system crawls **only public, no-login job sources** (source list defined per deployment; must be crawl-friendly). **No user account credentials are ever collected or used for crawling.**
- Supports **manual one-time crawl** and **scheduled auto-crawl** (user-configured Cron interval)
- Deduplication based on job URL to avoid repeated listings
- Discovery list: multi-dimensional filters (company, city, salary) and sorting (time, match score)
- **Manual add — one plain-form path plus three assisted paths** (any site, including login-walled ones like LinkedIn, via content the user copies out themselves). The plain form is the **baseline that must always work**; the other three only save typing (v0.3):
  0. **Plain form (Core, no AI)** — the user types/pastes title, company, URL, location, salary and JD text into an ordinary form on `/jobs`. Available regardless of AI configuration or quota. This is the fallback of last resort for every other path and the path all non-AI tests use.
  1. **Paste a job URL** — the system fetches and parses the page; if the page cannot be fetched or parsed (anti-bot, JS-rendered, login wall), the UI degrades gracefully and pre-fills the plain form for the user to complete — never a dead-end error
  2. **Paste JD text** — AI parses it into structured fields and pre-fills the form; the user confirms before it is saved
  3. **Paste a JD screenshot** — parsed by a multimodal model; on self-hosted deployments this entry requires the configured key to support a vision model, otherwise it is disabled with a clear notice pointing at path 0

**中文：**
- 用户配置搜索条件：关键词、城市、岗位类型、发布时间范围、薪资区间
- 系统**只爬取无需登录的公开职位源**（源清单按部署配置；须对爬虫友好）。**绝不收集或使用用户账号凭证进行爬取。**
- 支持**手动触发**单次爬取 + **定时自动爬取**（用户配置 Cron 周期）
- 基于岗位 URL 去重，避免重复展示
- 发现列表：多维筛选（公司、城市、薪资）和排序（时间、匹配度）
- **手动添加——一条普通表单路径 + 三条辅助路径**（任意站点均可，包括 LinkedIn 等登录墙站点，由用户自行复制内容）。普通表单是**必须始终可用的基线**，其余三条只是省去打字（v0.3）：
  0. **普通表单（基础层，无 AI）**——用户在 `/jobs` 页的普通表单中填写/粘贴职位名称、公司、URL、地点、薪资与 JD 文本。不受 AI 配置与配额影响。它既是其他所有路径的最终兜底，也是所有非 AI 测试所走的路径。
  1. **粘贴岗位 URL**——系统抓取并解析页面；无法抓取或解析时（反爬、JS 渲染、登录墙），界面优雅降级，把已获取的内容预填进普通表单交由用户补全——绝不以报错告终
  2. **粘贴 JD 文本**——AI 解析为结构化字段并预填表单，由用户确认后保存
  3. **粘贴 JD 截图**——由多模态模型解析；自部署形态下该入口要求所配置的 Key 支持视觉模型，否则明确提示并禁用，并指向路径 0

### 3.2 AI Job Analysis / AI 岗位分析 `[AI]`

**EN:**
- Automatically extracts structured information from JD: required skills, responsibilities, salary range, highlights, implicit requirements
- Computes a **match score** (0–100) against the user's resume, plus a skill gap list
- Generates **tailored resume optimization suggestions** specific to that JD (not generic advice)
- Results are persisted; the same job is not re-analyzed

**中文：**
- 自动提取 JD 结构化信息：技能要求、工作职责、薪资区间、岗位亮点、隐性要求
- 对比用户简历计算**匹配评分**（0–100）及技能差距清单
- 针对该岗位生成**简历优化建议**（定向修改，非通用建议）
- 分析结果持久化存储，相同岗位不重复分析

### 3.3 Application Kanban / 投递看板 `[Core]`

**EN:**
- Swim lane statuses: `Discovered` → `Applied` → `Interviewing` → `Offer` → `Withdrawn / Rejected`
- Drag cards to change status; status-change events and timestamps are recorded automatically
- Both **Kanban view** (drag-and-drop) and **List view** (sortable/filterable)
- Card detail side panel: JD summary, AI analysis, application notes, event timeline

**中文：**
- 泳道状态：`发现` → `已投递` → `面试中` → `已拿 Offer` → `已放弃 / 已拒`
- 拖拽卡片切换状态，状态变更事件与时间戳自动记录
- 支持**看板视图**（拖拽）和**列表视图**（排序/筛选）
- 卡片详情侧边栏：JD 摘要、AI 分析结果、投递备注、事件时间线

### 3.4 Job Detail / 岗位详情 `[Core + AI]`

**EN:**

*Core (no AI):*
- Full JD text; all job fields **editable in place** (title, company, URL, location, salary, type, JD text) and the job can be deleted
- **Company linkage**: the job's company is resolved by name within the tenant and linked automatically on create/update; the user can re-point it to another company or clear it
- **Apply with a chosen resume** (v0.3): creating/advancing an application records *which resume was used*; defaults to the default resume, changeable per application and afterwards
- Application notes (rich text) + event timeline (interview rounds, communications, etc.)

*AI layer (each an explicit button on this page, never the only way in):*
- AI-structured analysis (tabs: required skills / responsibilities / salary / highlights)
- Match score + skill gap list vs. the resume attached to this application
- Tailored resume optimization suggestions for this specific JD
- Every AI result shows its model and generation time, and can be discarded or overwritten by hand

**中文：**

*基础层（无 AI）：*
- JD 原文全文展示；岗位所有字段**可原地编辑**（职位名称、公司、URL、地点、薪资、类型、JD 文本），岗位可删除
- **公司挂接**：创建/更新岗位时按公司名在本租户内解析并自动挂接；用户可改指向其他公司或清空
- **选择简历投递**（v0.3）：创建/推进投递时记录**本次使用的是哪份简历**；默认取默认简历，可按投递单独选择，事后也可修改
- 投递备注（富文本）+ 事件时间线（面试轮次、沟通记录等）

*AI 叠加层（在本页均为显式按钮，绝不作为唯一入口）：*
- AI 结构化解析结果（分栏：技能要求 / 职责 / 薪资 / 亮点）
- 与**本次投递所用简历**的匹配评分 + 技能差距清单
- 针对该岗位的简历优化建议
- 每个 AI 结果都显示所用模型与生成时间，且可丢弃或手动覆写

### 3.5 Resume & Profile / 简历与个人资料 `[Core]`

**EN:**
- Upload resume (PDF/DOCX); text extraction is deterministic (no LLM) — a resume is usable the moment it is uploaded
- **Resume library, not a single active resume** (v0.3): a user keeps several resumes for different role directions. Each carries a user-editable **label** ("backend", "AI engineer") and free-text notes; the file name alone is not a usable identity
- **Default resume** (v0.3, replaces "active"): exactly one resume is the default, used to pre-fill new applications and AI actions. Per-application resume choice always wins over the default (see 3.4). The first resume a user uploads becomes the default automatically
- Manual editing of personal info and skill tags; resume metadata (label, notes) is editable, and any resume can be deleted
- Job preference configuration: desired role direction, salary range, work city, industry preference

**中文：**
- 上传简历（PDF/DOCX）；文本抽取是确定性的（不经 LLM）——简历上传后即刻可用
- **简历库，而非单一激活简历**（v0.3）：用户会为不同岗位方向保留多份简历。每份带有用户可编辑的**标签**（"后端""AI 工程"）和自由备注；仅靠文件名无法作为可用的标识
- **默认简历**（v0.3，取代"激活"概念）：有且仅有一份简历为默认，用于预填新投递与 AI 操作。按投递单独选择的简历始终优先于默认（见 3.4）。用户上传的第一份简历自动成为默认
- 手动编辑个人信息与技能标签；简历元数据（标签、备注）可编辑，任意简历可删除
- 求职偏好配置：期望岗位方向、薪资范围、工作城市、行业偏好

### 3.6 Target Company Tracker / 目标公司管理 `[Core]`

**EN:**
- **Full manual CRUD** (v0.3): create, edit and delete company records by hand — name, industry, size, website, notes. A company can exist before any job from it does
- Notes are free text, owned by the user (team size, culture impression, compensation assessment)
- **Auto-linked from jobs** (v0.3): when a job is created or imported, its company is resolved by name within the tenant — an existing record is reused, otherwise a minimal one is created. Companies are never left as orphaned name strings on jobs
- Company detail page: all jobs and applications for that company
- **Company blacklist**: suppress jobs from a company during discovery (not interested / previously rejected)
- Company records are **per-tenant private** (owner decision, 2026-07-26): each user's company list, notes and blacklist are their own. A shared cross-user company catalog is explicitly out of scope (see §6)
- *AI layer (v0.4)*: company research writes findings into the notes field tagged `source: ai`, appended alongside — never overwriting — the user's own notes

**中文：**
- **完整手动增删改查**（v0.3）：可手动新建、编辑、删除公司记录——名称、行业、规模、官网、备注。公司记录可以先于该公司的任何岗位存在
- 备注为用户自有的自由文本（规模、文化印象、待遇评价等）
- **由岗位自动挂接**（v0.3）：岗位创建或导入时，按公司名在本租户内解析——已有记录直接复用，否则创建一条最小记录。岗位上绝不留下无归属的公司名字符串
- 公司详情页：该公司下所有岗位与投递记录
- 公司**黑名单**：岗位发现时屏蔽该公司的岗位
- 公司记录**按租户私有**（owner 决策，2026-07-26）：每个用户的公司清单、备注与黑名单都属于自己。跨用户共享的公司档案库明确排除在范围外（见 §6）
- *AI 叠加层（v0.4）*：企业调查将结论写入备注字段并标注 `source: ai`，与用户自己的备注并存——绝不覆盖

### 3.7 Interview Preparation / 面试准备 `[AI]`

**EN:**
- Based on JD + personal resume, AI generates structured interview questions (behavioral + technical + situational)
- Each question includes a reference answer outline
- Questions can be marked as prepared / to-do
- Results are stored per-job; revisit any time

**中文：**
- 基于 JD + 个人简历，AI 生成结构化面试题（行为题 + 技术题 + 情景题）
- 每道题附参考回答思路
- 支持标记题目状态（已准备 / 待准备）
- 按岗位维度存储，进入即可查看历史生成结果

### 3.8 AI Assistant / AI 助手 `[AI]`

**EN:**
- Global floating sidebar, accessible from any page without interrupting the current workflow
- Supports natural-language tool-call actions:

  | Example Input | Action Triggered |
  |---|---|
  | "Analyze this job: [URL]" | Fetch + parse the URL, add to list, run analysis |
  | *pastes JD text or screenshot* "Add this job" | Parse the pasted content, add to list, run analysis |
  | "Mark the ByteDance job as Applied" | Update Kanban status |
  | "I have an interview tomorrow, help me prep" | Generate interview questions |
  | "Which applications haven't moved in 7+ days?" | Query overdue applications |
  | "Search for senior frontend roles in Beijing" | Trigger job discovery |

- Tech: Vercel AI SDK (`useChat`) + LangGraph ReAct Agent + assistant-ui components; tool activity is streamed live into the chat UI
- Multi-turn context: agent is aware of the current page context (job / company being viewed)

**中文：**
- 全局悬浮侧边栏，随时唤出，不打断当前页面工作流
- 支持自然语言触发后台动作（Tool Use）：

  | 示例输入 | 触发动作 |
  |---|---|
  | "帮我分析这个岗位 [URL]" | 抓取解析 URL、加入列表并分析 |
  | *粘贴 JD 文本或截图*"帮我加进去" | 解析粘贴内容、加入列表并分析 |
  | "把字节跳动那个岗位标记为已投递" | 更新看板状态 |
  | "我明天有面试，帮我准备" | 生成当前岗位面试题 |
  | "最近有哪些投递超过 7 天没动静？" | 查询逾期投递列表 |
  | "搜索北京的高级前端岗位" | 触发岗位发现 |

- 技术：Vercel AI SDK + LangGraph ReAct Agent + assistant-ui 组件；工具调用过程实时透出到聊天 UI
- 多轮对话，Agent 知晓当前页面上下文

### 3.9 Notifications / 通知与提醒 `[Core]`

**EN:**
- **Reminder rules** (user-configurable):
  - N days after applying with no status change → remind to follow up (default: 7 days)
  - N days after interview with no feedback → remind to confirm result (default: 3 days)
- **Channel: email** (SMTP / AWS SES), per-user toggle + reminder threshold settings
- Deferred (roadmap, see §6): in-app notification center; IM webhook channels

**中文：**
- **提醒规则**（用户可配置）：
  - 投递后 N 天无状态变更 → 提醒跟进（默认 7 天）
  - 面试后 N 天无反馈 → 提醒确认结果（默认 3 天）
- **渠道：邮件**（SMTP / AWS SES），按用户开关 + 提醒规则阈值设置
- 暂缓（roadmap，见 §6）：站内通知中心、IM Webhook 渠道

### 3.10 Account & Settings / 账号与设置 `[Core]`

**EN:**
- **Account**: self-service email registration (with email verification) + Google OAuth login, password change, avatar
- **LLM access, by deployment mode**:
  - *Self-hosted*: user configures their own OpenAI-compatible API Key (encrypted at rest, AES-256-GCM); required for AI features; screenshot parsing additionally requires the key to support a vision model
  - *Hosted site*: platform-provided LLM API only; the API-key configuration UI is hidden; per-user quota enforcement is deferred (see §6)
- **Notification preferences**: email toggle + reminder threshold settings
- **Platform Admin** (hosted site, operator only):
  - User management: search, deactivate accounts
  - Usage overview: per-user AI call count, crawl count, monthly consumption trend

**中文：**
- **账号**：自助邮箱注册（邮件验证）+ Google OAuth 登录、修改密码、头像
- **LLM 接入，按部署形态**：
  - *自部署*：用户自行配置 OpenAI 兼容 API Key（AES-256-GCM 加密存储）；AI 功能必配；截图解析额外要求该 Key 支持视觉模型
  - *托管站*：只使用平台提供的大模型 API；不展示 API Key 配置界面；按用户的配额强制暂缓（见 §6）
- **通知偏好**：邮件开关 + 提醒规则阈值
- **平台管理员**（托管站，仅运营者）：
  - 用户管理：搜索、停用账号
  - 用量概览：按用户的 AI 调用次数、爬取次数、月消耗趋势

---

## 4. Page Inventory / 页面清单

| Page / 页面 | Route / 路由 | Access / 访问权限 |
|---|---|---|
| Login / 登录 | `/login` | Public / 公开 |
| Register / 注册 | `/register` | Public / 公开 |
| Reset Password / 重置密码 | `/reset-password` | Public / 公开 |
| Dashboard / 首页 | `/` | Authenticated / 登录后 |
| Job Discovery / 岗位发现 | `/discovery` | Authenticated / 登录后 |
| Application Kanban / 投递看板 | `/kanban` | Authenticated / 登录后 |
| Job Detail / 岗位详情 | `/jobs/[id]` | Authenticated / 登录后 |
| Interview Prep / 面试准备 | `/jobs/[id]/prep` | Authenticated / 登录后 |
| Companies / 目标公司列表 | `/companies` | Authenticated / 登录后 |
| Company Detail / 公司详情 | `/companies/[id]` | Authenticated / 登录后 |
| Resume & Profile / 简历资料 | `/profile` | Authenticated / 登录后 |
| Settings - Account / 账号 | `/settings/account` | Authenticated / 登录后 |
| Settings - Credentials / 凭证 | `/settings/credentials` | Authenticated (self-hosted only / 仅自部署形态) |
| Settings - Notifications / 通知 | `/settings/notifications` | Authenticated / 登录后 |
| User Management / 用户管理 | `/admin/users` | Platform Admin / 平台管理员 |
| Usage Overview / 用量概览 | `/admin/usage` | Platform Admin / 平台管理员 |

Removed in v0.2 / v0.2 移除：`/analytics`（module cut / 模块砍除）、`/notifications`（deferred / 暂缓）、`/admin/members`（tenant-admin removed / 随租户管理员移除）。

**Implementation drift as of 2026-07-26 / 实现偏离现状（v0.3 要补齐的部分）：**

**EN:** The routes below have been specified since v0.2 but were **never implemented**; the shipped frontend has only `/dashboard`, `/jobs`, `/jobs/[id]`, `/discovery`, `/profile`, `/admin/users`, `/admin/usage`. Their backend REST endpoints (jobs, companies, applications — full CRUD, status machine and event log) **already exist and are in production**, so closing this gap is predominantly frontend work.

| Route / 路由 | Status / 现状 |
|---|---|
| `/companies`, `/companies/[id]` | Backend CRUD live; **no UI at all** / 后端 CRUD 已上线，**前端完全缺失** |
| `/kanban` | Kanban component exists on the dashboard; no dedicated route / 看板组件在首页，无独立路由 |
| `/jobs/[id]/prep` | Interview prep reachable only through the chat agent / 面试准备仅能通过聊天 Agent 到达 |
| `/settings/account`, `/settings/credentials`, `/settings/notifications` | Merged into `/profile`; notification settings have no UI / 合并进 `/profile`，通知设置无界面 |
| Manual job create / edit / delete UI | v0.3 addition — `POST/PATCH/DELETE /v1/jobs` exist, nothing calls them / v0.3 新增——端点已存在但无调用方 |

**中文：** 上表路由自 v0.2 起就已写入需求，但**从未实现**；已上线前端只有 `/dashboard`、`/jobs`、`/jobs/[id]`、`/discovery`、`/profile`、`/admin/users`、`/admin/usage`。它们对应的后端 REST 端点（岗位、公司、投递——完整 CRUD、状态机与事件日志）**均已存在并在生产运行**，因此补齐这一差距以前端工作为主。

---

## 5. Core User Stories / 核心用户故事

| ID | Role / 角色 | Story / 故事 | Acceptance Criteria / 验收标准 |
|---|---|---|---|
| US-01 | Job Seeker | After configuring search criteria, the system auto-discovers matching jobs from public job sources | Discovery list shows jobs with title, company, location, salary, and posting date after crawl completes; no account credential is ever requested |
| US-02 | Job Seeker | I add a job via URL, pasted JD text, or a screenshot, and AI analyzes it against my resume | All three entries produce a structured analysis, match score (0–100), skill gap list, and optimization suggestions within 5 minutes; when a URL cannot be fetched/parsed, the UI prompts me to paste the JD text instead of erroring out |
| US-03 | Job Seeker | I manage all applications on a Kanban board; drag to change status | Status updates instantly on drag; change event is logged with timestamp |
| US-04 | Job Seeker | I receive an email reminder when an application has had no activity for 7 days | Reminder email arrives at the configured threshold |
| US-05 | Job Seeker | The AI assistant understands natural language and executes actions | Recognizes commands like "analyze this link" and completes the action with streaming confirmation, tool activity visible in the chat |
| US-06 | Job Seeker | AI generates targeted interview questions before an interview | Produces ≥ 10 questions (behavioral/technical/situational) with reference answer outlines based on the JD and my resume |
| US-07 | Platform Admin | I manage user accounts on the hosted site and monitor per-user usage | Can search/deactivate users; view per-user AI call count and crawl count |
| US-08 (v0.3) | Job Seeker | I add, edit and delete jobs, companies and applications entirely by hand, without any AI involvement | Every entity is fully manageable through ordinary forms; **no request in the flow reaches the agent service**, verified by the no-AI E2E test; works with no LLM key configured and with the daily AI quota exhausted |
| US-09 (v0.3) | Job Seeker | I keep several labelled resumes and record which one I sent to each job | Resume carries an editable label + notes; the application stores its own `resume_id`; the job detail page shows the resume used; changing the default resume does not rewrite history on existing applications |
| US-10 (v0.3) | Job Seeker | With AI fully disabled, the product is still a complete job-search tracker | With AI switched off: discovery of public sources, manual job/company/application CRUD, Kanban + status machine, resume library and email reminders all function; AI-only surfaces are hidden or disabled with an explanation, never broken or silently empty |

---

## 6. Out of Scope / 非目标

**EN:**

*Cut or excluded / 砍除或排除:*
- Account-credential-based crawling of login-walled platforms (e.g. LinkedIn session-cookie crawling) — removed in v0.2; users copy content out manually instead
- Analytics dashboards (funnel / channel / trend / offer-rate) — removed in v0.2
- Automatically submitting applications on behalf of users (bot-apply)
- Email inbox parsing to auto-update application status (Gmail OAuth)
- Mobile app (responsive web layout as substitute)
- Multi-language i18n (Chinese UI by default)
- Built-in resume builder (users upload their own resume files)
- **Shared cross-user company catalog** (v0.3): company records stay per-tenant private. A global company master record plus per-user note overlay would need cross-tenant read exceptions, a merge/dedup policy and a write-permission model — a separate, much larger design

*Deferred / 暂缓（记录在案，以后做）:*
- Premium tier (platform-key subscription; Keycloak `premium` role reserved)
- Per-user quota enforcement & anti-abuse rate limiting on the hosted site (prerequisite for large-scale open registration)
- In-app notification center (web notification center, read/unread, `/notifications` page)
- IM webhook notification channels (WeCom / DingTalk)
- **Browser-extension job ingestion** (v0.3 decision: design recorded, deliberately not scheduled). For sites with aggressive anti-bot defences (LinkedIn and similar), an extension would read the posting the user is already looking at in their own logged-in session and, on an explicit click, post it to the API. Design constraints are fixed in SAD **ADR-009** so a later implementation does not have to rediscover them; the manual plain form (§3.1 path 0) is the supported path until then

**中文：**

*砍除或排除：*
- 基于账号凭证爬取登录墙平台（如 LinkedIn Session Cookie 爬取）——v0.2 移除；改由用户自行复制内容录入
- 数据分析看板（漏斗/渠道/趋势/Offer 率）——v0.2 移除
- 自动代替用户投递简历（机器人投递）
- 邮件收件箱解析自动更新投递状态（Gmail OAuth 集成）
- 移动端 App（Web 响应式布局作为替代）
- 多语言国际化（默认中文界面）
- 内置简历生成器（用户自行上传简历文件）
- **跨用户共享公司档案库**（v0.3）：公司记录保持按租户私有。全局公司主数据 + 每用户备注叠加层需要引入跨租户读例外、去重/合并策略与写权限模型——是一个独立且大得多的设计

*暂缓（记录在案，以后做）：*
- Premium 订阅（平台 Key 付费档；Keycloak `premium` 角色已预留）
- 托管站按用户配额强制与防滥用限流（大规模开放注册的前提）
- 站内通知中心（Web 通知中心、已读/未读、`/notifications` 页面）
- IM Webhook 通知渠道（企业微信 / 钉钉）
- **浏览器插件式岗位录入**（v0.3 决策：设计入档，刻意不排期）。对反爬严格的站点（LinkedIn 及类似站点），插件在用户自己已登录的会话中读取其正在浏览的岗位页面，并在用户显式点击后推送到我们的 API。设计约束已固化在 SAD **ADR-009**，避免将来实现时重新摸索；在此之前，受支持的路径是手动普通表单（§3.1 路径 0）
