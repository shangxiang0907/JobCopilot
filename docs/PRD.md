# JobCopilot — Product Requirements Document / 产品需求文档

Version / 版本：v0.2  
Status / 状态：Active / 生效  
Last Updated / 最后更新：2026-07-11

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

### 3.1 Job Discovery / 岗位发现

**EN:**
- User configures search criteria: keywords, city, job type, posting date range, salary range
- The system crawls **only public, no-login job sources** (source list defined per deployment; must be crawl-friendly). **No user account credentials are ever collected or used for crawling.**
- Supports **manual one-time crawl** and **scheduled auto-crawl** (user-configured Cron interval)
- Deduplication based on job URL to avoid repeated listings
- Discovery list: multi-dimensional filters (company, city, salary) and sorting (time, match score)
- **Manual add — three mutually-fallback entry paths** (any site, including login-walled ones like LinkedIn, via content the user copies out themselves):
  1. **Paste a job URL** — the system fetches and parses the page; if the page cannot be fetched or parsed (anti-bot, JS-rendered, login wall), the UI degrades gracefully and prompts the user to paste the JD text instead — never a dead-end error
  2. **Paste JD text** — into a designated entry (e.g. the AI chat window); AI parses and adds the job
  3. **Paste a JD screenshot** — parsed by a multimodal model; on self-hosted deployments this entry requires the configured key to support a vision model, otherwise it is disabled with a clear notice

**中文：**
- 用户配置搜索条件：关键词、城市、岗位类型、发布时间范围、薪资区间
- 系统**只爬取无需登录的公开职位源**（源清单按部署配置；须对爬虫友好）。**绝不收集或使用用户账号凭证进行爬取。**
- 支持**手动触发**单次爬取 + **定时自动爬取**（用户配置 Cron 周期）
- 基于岗位 URL 去重，避免重复展示
- 发现列表：多维筛选（公司、城市、薪资）和排序（时间、匹配度）
- **手动添加——三条互为兜底的录入路径**（任意站点均可，包括 LinkedIn 等登录墙站点，由用户自行复制内容）：
  1. **粘贴岗位 URL**——系统抓取并解析页面；无法抓取或解析时（反爬、JS 渲染、登录墙），界面优雅降级、引导用户改为粘贴 JD 文本——绝不以报错告终
  2. **粘贴 JD 文本**——粘贴到指定入口（如 AI 聊天窗口），AI 解析并加入列表
  3. **粘贴 JD 截图**——由多模态模型解析；自部署形态下该入口要求所配置的 Key 支持视觉模型，否则明确提示并禁用

### 3.2 AI Job Analysis / AI 岗位分析

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

### 3.3 Application Kanban / 投递看板

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

### 3.4 Job Detail / 岗位详情

**EN:**
- Full JD text
- AI-structured analysis (tabs: required skills / responsibilities / salary / highlights)
- Match score + skill gap list vs. user's resume
- Tailored resume optimization suggestions for this specific JD
- Application notes (rich text) + event timeline (interview rounds, communications, etc.)

**中文：**
- JD 原文全文展示
- AI 结构化解析结果（分栏：技能要求 / 职责 / 薪资 / 亮点）
- 与我简历的匹配评分 + 技能差距清单
- 针对该岗位的简历优化建议
- 投递备注（富文本）+ 事件时间线（面试轮次、沟通记录等）

### 3.5 Resume & Profile / 简历与个人资料

**EN:**
- Upload resume (PDF/DOCX); AI parses it into structured data (skills, work experience, education)
- Manual editing of personal info and skill tags
- Job preference configuration: desired role direction, salary range, work city, industry preference
- **Resume version management**: retain upload history; choose which version is used for matching

**中文：**
- 上传简历（PDF/DOCX），AI 解析为结构化数据（技能、工作经历、教育背景）
- 手动编辑个人信息、技能标签
- 求职偏好配置：期望岗位方向、薪资范围、工作城市、行业偏好
- **简历版本管理**：保留历史上传记录，可切换哪个版本参与匹配

### 3.6 Target Company Tracker / 目标公司管理

**EN:**
- Bookmark companies of interest; add notes (team size, culture impression, compensation assessment)
- Company detail page: all discovered jobs and applications for that company
- **Company blacklist**: suppress jobs from a company during discovery (not interested / previously rejected)

**中文：**
- 收藏感兴趣的公司，添加备注（规模、文化印象、待遇评价等）
- 公司详情页：该公司下所有发现岗位与投递记录
- 公司**黑名单**：岗位发现时屏蔽该公司的岗位

### 3.7 Interview Preparation / 面试准备

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

### 3.8 AI Assistant / AI 助手

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

### 3.9 Notifications / 通知与提醒

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

### 3.10 Account & Settings / 账号与设置

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

*Deferred / 暂缓（记录在案，以后做）:*
- Premium tier (platform-key subscription; Keycloak `premium` role reserved)
- Per-user quota enforcement & anti-abuse rate limiting on the hosted site (prerequisite for large-scale open registration)
- In-app notification center (web notification center, read/unread, `/notifications` page)
- IM webhook notification channels (WeCom / DingTalk)

**中文：**

*砍除或排除：*
- 基于账号凭证爬取登录墙平台（如 LinkedIn Session Cookie 爬取）——v0.2 移除；改由用户自行复制内容录入
- 数据分析看板（漏斗/渠道/趋势/Offer 率）——v0.2 移除
- 自动代替用户投递简历（机器人投递）
- 邮件收件箱解析自动更新投递状态（Gmail OAuth 集成）
- 移动端 App（Web 响应式布局作为替代）
- 多语言国际化（默认中文界面）
- 内置简历生成器（用户自行上传简历文件）

*暂缓（记录在案，以后做）：*
- Premium 订阅（平台 Key 付费档；Keycloak `premium` 角色已预留）
- 托管站按用户配额强制与防滥用限流（大规模开放注册的前提）
- 站内通知中心（Web 通知中心、已读/未读、`/notifications` 页面）
- IM Webhook 通知渠道（企业微信 / 钉钉）
