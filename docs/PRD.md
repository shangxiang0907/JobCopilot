# JobCopilot — Product Requirements Document / 产品需求文档

Version / 版本：v0.1  
Status / 状态：Draft / 草稿  
Last Updated / 最后更新：2026-06-10

---

## 1. Product Overview / 产品概述

**EN:**  
JobCopilot is a production-grade, multi-tenant intelligent job-search management platform. The system uses a multi-AI-agent architecture to automatically discover and analyze job listings, provides resume match scoring and optimization suggestions, manages the entire application pipeline via a Kanban board, and supports natural-language actions through a global AI assistant.

**中文：**  
JobCopilot 是一个生产级、多租户的智能求职管理平台。系统通过多 AI Agent 架构自动发现并分析岗位，结合个人简历提供匹配评分与优化建议，以看板形式管理全部投递进程，并通过全局 AI 助手支持自然语言触发任意操作。

**Core Value Propositions / 核心价值主张：**

| Value / 价值 | EN | 中文 |
|---|---|---|
| Save time | Auto-discovers jobs from LinkedIn, no manual searching | 自动从 LinkedIn 发现符合条件的岗位，无需手动搜索 |
| Higher hit rate | AI analyzes JD + resume, pinpoints gaps, gives tailored suggestions | AI 分析 JD + 简历，精准找出差距并给出定制化建议 |
| Never forget | Kanban board + multi-channel smart reminders | 看板 + 多渠道智能提醒，确保每条投递都有跟进 |
| AI always on | Global AI assistant for natural-language-triggered actions | 全局 AI 助手支持自然语言触发任意后台动作 |

---

## 2. Target Users / 目标用户

**EN:**

| Role | Description | Core Need |
|---|---|---|
| **Job Seeker** (primary) | Actively job-hunting, tracking multiple positions simultaneously | Efficient discovery, precise matching, never miss a follow-up |
| **Tenant Admin** | Company/team purchasing multi-seat plan, managing member accounts | Member management, AI usage monitoring, quota control |

**中文：**

| 角色 | 描述 | 核心诉求 |
|---|---|---|
| **求职者**（主要用户） | 正在主动求职，同时跟进多个职位 | 高效发现岗位、精准匹配、不遗漏跟进 |
| **租户管理员** | 企业/团队购买多席位，管理成员账号 | 成员管理、AI 用量监控、配额控制 |

---

## 3. Feature Modules / 功能模块

### 3.1 Job Discovery / 岗位发现

**EN:**
- User configures search criteria: keywords, city, job type, posting date range, salary range
- User provides their own LinkedIn Session Cookie; system uses Playwright to simulate login and crawl (each user's cookie is isolated)
- Supports **manual one-time crawl** and **scheduled auto-crawl** (user-configured Cron interval)
- Deduplication based on job URL to avoid repeated listings
- Discovery list: multi-dimensional filters (company, city, salary) and sorting (time, match score)
- **Manual add**: paste any LinkedIn job URL or enter JD text manually; AI analyzes automatically

**中文：**
- 用户配置搜索条件：关键词、城市、岗位类型、发布时间范围、薪资区间
- 用户提供自己的 LinkedIn Session Cookie，系统用 Playwright 模拟登录爬取（每用户独立 Cookie，互不干扰）
- 支持**手动触发**单次爬取 + **定时自动爬取**（用户配置 Cron 周期）
- 基于岗位 URL 去重，避免重复展示
- 发现列表：多维筛选（公司、城市、薪资）和排序（时间、匹配度）
- **手动添加**：粘贴任意 LinkedIn 岗位 URL 或手动填写 JD，AI 自动分析

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
- **Company blacklist**: suppress jobs from a company during crawling (not interested / previously rejected)

**中文：**
- 收藏感兴趣的公司，添加备注（规模、文化印象、待遇评价等）
- 公司详情页：该公司下所有发现岗位与投递记录
- 公司**黑名单**：屏蔽爬取时该公司的岗位

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

### 3.8 Analytics / 数据分析

**EN:**
- Application funnel: conversion rates across statuses (Discovered → Applied → Interview → Offer)
- Channel analysis: auto-discovered vs. manually added effectiveness
- Time trend: weekly application volume
- Offer rate broken down by company / industry

**中文：**
- 投递漏斗：各状态转化率（发现→投递→面试→Offer）
- 渠道分析：自动发现 vs 手动添加的对比效果
- 时间趋势：每周投递量变化
- 公司 / 行业维度的 Offer 率分析

### 3.9 AI Assistant / AI 助手

**EN:**
- Global floating sidebar, accessible from any page without interrupting the current workflow
- Supports natural-language tool-call actions:

  | Example Input | Action Triggered |
  |---|---|
  | "Analyze this job: [URL]" | Add to job analysis queue |
  | "Mark the ByteDance job as Applied" | Update Kanban status |
  | "I have an interview tomorrow, help me prep" | Generate interview questions |
  | "Which applications haven't moved in 7+ days?" | Query overdue applications |
  | "Search for senior frontend roles in Beijing" | Trigger job discovery |

- Tech: Vercel AI SDK (`useChat`) + LangGraph ReAct Agent + assistant-ui components
- Multi-turn context: agent is aware of the current page context (job / company being viewed)

**中文：**
- 全局悬浮侧边栏，随时唤出，不打断当前页面工作流
- 支持自然语言触发后台动作（Tool Use）：

  | 示例输入 | 触发动作 |
  |---|---|
  | "帮我分析这个岗位 [URL]" | 加入岗位分析队列 |
  | "把字节跳动那个岗位标记为已投递" | 更新看板状态 |
  | "我明天有面试，帮我准备" | 生成当前岗位面试题 |
  | "最近有哪些投递超过 7 天没动静？" | 查询逾期投递列表 |
  | "搜索北京的高级前端岗位" | 触发岗位发现 |

- 技术：Vercel AI SDK + LangGraph ReAct Agent + assistant-ui 组件
- 多轮对话，Agent 知晓当前页面上下文

### 3.10 Notifications / 通知与提醒

**EN:**
- **Reminder rules** (user-configurable):
  - N days after applying with no status change → remind to follow up (default: 7 days)
  - N days after interview with no feedback → remind to confirm result (default: 3 days)
- **Notification channels** (independent toggle per channel):
  - In-app notifications (web notification center, real-time)
  - Email (SMTP / AWS SES)
  - WeChat Webhook (WeCom / personal WeChat bot)
  - DingTalk Webhook
- Notification center: history list, read/unread management, click to jump to related job

**中文：**
- **提醒规则**（用户可配置）：
  - 投递后 N 天无状态变更 → 提醒跟进（默认 7 天）
  - 面试后 N 天无反馈 → 提醒确认结果（默认 3 天）
- **通知渠道**（每个渠道独立开关）：
  - 站内通知（Web 通知中心，实时）
  - 邮件（SMTP / AWS SES）
  - 微信 Webhook（企业微信 / 个人微信机器人）
  - 钉钉 Webhook
- 通知中心：历史列表，已读/未读管理，点击跳转关联岗位

### 3.11 Account & Settings / 账号与设置

**EN:**
- **Account**: email registration (with email verification) + Google OAuth login, password change, avatar
- **Credential configuration**:
  - LinkedIn Session Cookie (AES-256 encrypted at rest; shows validity status and last verified time)
  - DashScope / OpenAI-compatible API Key (encrypted at rest; user can bring their own or use platform key)
- **Notification preferences**: channel toggles + webhook URL config + reminder threshold settings
- **Tenant Admin**:
  - Member management: invite (email), deactivate, role assignment (Admin / Member)
  - Usage overview: AI call count, crawl count, quota remaining, monthly consumption trend

**中文：**
- **账号**：邮箱注册（邮件验证）+ Google OAuth 登录、修改密码、头像
- **凭证配置**：
  - LinkedIn Session Cookie（AES-256 加密存储，显示有效期状态与最后验证时间）
  - DashScope / OpenAI 兼容 API Key（加密存储，可自带 Key 或使用平台 Key）
- **通知偏好**：渠道开关 + Webhook URL 配置 + 提醒规则阈值
- **租户管理员**：
  - 成员管理：邀请（邮件）、停用账号、角色分配（Admin / Member）
  - 用量概览：AI 调用次数、爬取次数、配额剩余、本月消耗趋势

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
| Analytics / 数据分析 | `/analytics` | Authenticated / 登录后 |
| Notifications / 通知中心 | `/notifications` | Authenticated / 登录后 |
| Settings - Account / 账号 | `/settings/account` | Authenticated / 登录后 |
| Settings - Credentials / 凭证 | `/settings/credentials` | Authenticated / 登录后 |
| Settings - Notifications / 通知 | `/settings/notifications` | Authenticated / 登录后 |
| Member Management / 成员管理 | `/admin/members` | Tenant Admin / 租户管理员 |
| Usage Overview / 用量概览 | `/admin/usage` | Tenant Admin / 租户管理员 |

---

## 5. Core User Stories / 核心用户故事

| ID | Role / 角色 | Story / 故事 | Acceptance Criteria / 验收标准 |
|---|---|---|---|
| US-01 | Job Seeker | After configuring search criteria, the system auto-discovers matching LinkedIn jobs | Discovery list shows jobs with title, company, location, salary, and posting date after crawl completes |
| US-02 | Job Seeker | I paste a job URL and AI analyzes it against my resume | Returns structured analysis, match score (0–100), skill gap list, and optimization suggestions within 5 minutes |
| US-03 | Job Seeker | I manage all applications on a Kanban board; drag to change status | Status updates instantly on drag; change event is logged with timestamp |
| US-04 | Job Seeker | I receive a reminder when an application has had no activity for 7 days | Reminder arrives on all configured channels at the correct threshold |
| US-05 | Job Seeker | The AI assistant understands natural language and executes actions | Recognizes commands like "analyze this link" and completes the action with streaming confirmation |
| US-06 | Job Seeker | AI generates targeted interview questions before an interview | Produces ≥ 10 questions (behavioral/technical/situational) with reference answer outlines based on the JD and my resume |
| US-07 | Tenant Admin | I manage team member accounts and monitor usage | Can invite/deactivate members; view per-member AI call count and remaining quota |

---

## 6. Out of Scope (v1) / 非目标

**EN:**
- Automatically submitting applications on behalf of users (bot-apply)
- Email inbox parsing to auto-update application status (Gmail OAuth)
- Mobile app (responsive web layout as substitute)
- LinkedIn Official API integration (requires partner credentials)
- Multi-language i18n (Chinese UI by default)
- Built-in resume builder (users upload their own resume files)

**中文：**
- 自动代替用户投递简历（机器人投递）
- 邮件收件箱解析自动更新投递状态（Gmail OAuth 集成）
- 移动端 App（Web 响应式布局作为替代）
- LinkedIn 官方 API 集成（需合作伙伴资质）
- 多语言国际化（默认中文界面）
- 内置简历生成器（用户自行上传简历文件）
