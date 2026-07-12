# JobCopilot — Operator Observability Guide / 运营者可观测性指南

Version / 版本：v1.0  
Last Updated / 最后更新：2026-07-12

**EN:** How the platform owner inspects the system without reading code. Three layers: Grafana (infrastructure & services), LangSmith (every LLM/agent run), LangGraph Studio (interactive graph debugging).

**中文：** 平台所有者不读代码即可审视系统运行的操作手册。三层：Grafana（基础设施与服务）、LangSmith（每一次 LLM/Agent 运行）、LangGraph Studio（交互式图调试）。

---

## 1. Grafana — Metrics & Logs / 指标与日志

**EN:**
- Local: http://localhost:3001. Production: Grafana is bound to loopback on the server — access via SSH tunnel: `ssh -L 3001:localhost:3001 <server>` then open http://localhost:3001.
- Dashboards and datasources are provisioned as code in `infra/grafana/` — Prometheus metrics (all `jobcopilot_*` series: HTTP rates/latency, LLM call counts, crawl counts, MQ consumption) and Loki logs (structured JSON from every service, filterable by `service`, `trace_id`, `tenant_id`).

**中文：**
- 本地：http://localhost:3001。生产：Grafana 仅绑定服务器回环地址——通过 SSH 隧道访问：`ssh -L 3001:localhost:3001 <server>` 后打开 http://localhost:3001。
- 仪表盘与数据源以代码形式配置于 `infra/grafana/`——Prometheus 指标（全部 `jobcopilot_*` 序列：HTTP 速率/延迟、LLM 调用数、爬取数、MQ 消费）与 Loki 日志（各服务结构化 JSON，可按 `service`、`trace_id`、`tenant_id` 过滤）。

---

## 2. LangSmith — LLM & Agent Traces / LLM 与 Agent 追踪

**EN:**  
LangSmith records every LangGraph run: each node transition, the exact prompt and response of every LLM call, every tool invocation with arguments and results, token usage, latency, and errors — the primary answer to "what did the AI actually do?".

### When is an API key needed? / 什么时候需要 API Key？

LangSmith is a **hosted SaaS**: the tracing SDK sends trace data over the internet to smith.langchain.com, where the web UI displays it. "Local" only describes where the *traced application* runs — the trace store is always their cloud. Therefore **any environment that should record traces needs the key** (one key can serve both environments; `LANGCHAIN_PROJECT` splits them into `jobcopilot-local` / `jobcopilot-prod`). With tracing off (`LANGCHAIN_TRACING_V2=false`, the current default) the application runs perfectly without a key.

### Activation / 激活步骤

**Status: ACTIVE locally since 2026-07-12 (verified: traces arrive in `jobcopilot-local`). Production: pending the privacy decision below.**

1. Register at https://smith.langchain.com (GitHub/Google sign-in; the default workspace is created automatically; free tier suffices).
2. Settings → API Keys → Create API Key. **In a Personal organization choose PERSONAL ACCESS TOKEN — Service Keys are silently rejected with bare 403s even on the correct regional endpoint (empirically verified 2026-07-12).** The key is shown only once — copy it immediately.
3. In the env file set `LANGSMITH_API_KEY=lsv2_...`, `LANGCHAIN_TRACING_V2=true`, and **`LANGSMITH_ENDPOINT` matching your account's region** — a mismatch also produces bare 403s on every endpoint. Our account is AWS US: `https://aws.api.smith.langchain.com` (other regions: `https://eu.api.smith.langchain.com`, `https://apac.api.smith.langchain.com`, GCP-US default `https://api.smith.langchain.com`).
4. Local: `docker compose up -d agent-service`. Production: same variables in the server's env file + redeploy (`infra/scripts/deploy.sh`) — read the privacy note first.
5. Open https://smith.langchain.com → Projects. The `jobcopilot-local` / `jobcopilot-prod` projects are created automatically on the first trace — nothing to pre-create.

Troubleshooting learned the hard way: a bare `403 {"detail":"Forbidden"}` on *every* endpoint means key-type (Service Key in a Personal org) or region mismatch — NOT an invalid key, geo-blocking, or plan problems. Both issues were present simultaneously here.

Reading a trace: each chat message or analysis is one run; expand it to see the node sequence (e.g. `fetch_resume → extract_structure → compute_match`), click any LLM node for the full prompt/response, any tool node for arguments/results. Failed runs are filterable (`error: true`).

### ⚠️ Privacy note / 隐私注意

Traces contain **full prompts and responses** — i.e. users' resume text and JD content leave your server and are stored in LangChain's cloud. Acceptable while the owner is the only user; **before the hosted site opens to the public**, either keep production tracing off (enable only locally / while debugging), disclose it in a privacy policy, or migrate to a self-hosted open-source alternative (e.g. Langfuse — data stays on your server; separate integration work). Decision deferred; recorded here.

**中文：**  
LangSmith 记录每一次 LangGraph 运行：每个节点流转、每次 LLM 调用的完整 prompt 与响应、每次工具调用的参数与结果、token 用量、延迟与错误——回答"AI 到底做了什么"的第一入口。

### 什么时候需要 API Key？

LangSmith 是**托管 SaaS**：追踪 SDK 把数据经互联网发送到 smith.langchain.com，由其网页 UI 展示。"本地"只是指*被追踪的应用*跑在哪里——追踪数据的存储永远在他们云端。因此**任何想记录追踪的环境都需要 Key**（一个 Key 两个环境共用即可；`LANGCHAIN_PROJECT` 将其分流到 `jobcopilot-local` / `jobcopilot-prod` 两个项目）。追踪关闭时（`LANGCHAIN_TRACING_V2=false`，当前默认），应用无 Key 也完全正常运行。

### 激活步骤

**现状：本地追踪已激活（2026-07-12，已验证追踪确实到达 `jobcopilot-local` 项目）。生产：待下方隐私决策后再启用。**

1. 在 https://smith.langchain.com 注册（GitHub/Google 登录即可，默认工作区自动创建，免费档足够）。
2. Settings → API Keys → Create API Key。**个人组织（Personal organization）必须选 PERSONAL ACCESS TOKEN——Service Key 即使在正确的区域端点上也会被静默拒绝、全端点裸 403（2026-07-12 实测验证）**。Key 只显示一次——当场复制。
3. 在 env 文件中设置 `LANGSMITH_API_KEY=lsv2_...`、`LANGCHAIN_TRACING_V2=true`，以及**与账号所在区域匹配的 `LANGSMITH_ENDPOINT`**——区域不匹配同样导致全端点裸 403。本账号在 AWS US 区：`https://aws.api.smith.langchain.com`（其他区域：`https://eu.api.smith.langchain.com`、`https://apac.api.smith.langchain.com`、GCP-US 默认 `https://api.smith.langchain.com`）。
4. 本地：`docker compose up -d agent-service`。生产：在服务器 env 文件设置同样变量并重新部署（`infra/scripts/deploy.sh`）——启用前先阅读隐私注意。
5. 打开 https://smith.langchain.com → Projects。`jobcopilot-local` / `jobcopilot-prod` 项目在首条追踪到达时自动创建——无需预建。

排障经验（学费已付）：所有端点都返回裸 `403 {"detail":"Forbidden"}` 时，原因是 Key 类型（个人组织用了 Service Key）或区域端点不匹配——不是 Key 无效、不是地区封锁、也不是计划问题。本次两个问题同时存在。

看懂一条追踪：每条聊天消息或每次分析是一次 run；展开可见节点序列（如 `fetch_resume → extract_structure → compute_match`），点击 LLM 节点看完整 prompt/响应，点击工具节点看参数/结果。失败的 run 可用 `error: true` 过滤。

### ⚠️ 隐私注意

追踪包含**完整的 prompt 与响应**——即用户的简历文本、JD 内容会离开你的服务器，存储在 LangChain 云端。你是唯一用户时可接受；**托管站对外开放前**，要么生产保持关闭（仅本地/调试时启用），要么写入隐私政策，要么迁移到自部署开源替代（如 Langfuse——数据全留在自己服务器，需另做集成）。该决定暂缓，在此记录。

---

## 3. LangGraph Studio — Interactive Graph Debugging / 交互式图调试

**EN:**  
Studio visualizes the four graphs (Analyzer / Resume / Interview / ReAct) as diagrams and lets you run them step by step: inspect state after every node, edit state and re-run from any point (time travel), and watch tool calls live. **Development only — never deployed.**

Launch (requires the local stack running — `cd infra && docker compose up -d`):

```bash
cd <repo root>
~/.local/bin/uv run langgraph dev
```

This starts a local graph server on http://localhost:2024 and prints a Studio URL (hosted UI at smith.langchain.com/studio connected to your local server — sign in with the same free LangSmith account; no API key required just to use Studio). Graph registration lives in the repo-root `langgraph.json`; the ReAct agent accepts `user_id` / `tenant_id` via the Assistant configuration panel (defaults are dev placeholders).

Note: host-run graphs reach the stack through localhost ports; the required `DATABASE_URL` / `PROFILE_SERVICE_URL` / `JOB_SERVICE_URL` overrides live in `infra/.env` (already set for local dev).

**中文：**  
Studio 将四个图（Analyzer / Resume / Interview / ReAct）可视化为流程图并支持单步运行：查看每个节点后的状态、编辑状态并从任意点重跑（时间旅行）、实时观察工具调用。**仅限开发环境，绝不部署。**

启动（需本地栈已运行——`cd infra && docker compose up -d`）：

```bash
cd <仓库根目录>
~/.local/bin/uv run langgraph dev
```

将在 http://localhost:2024 启动本地图服务器并打印 Studio URL（smith.langchain.com/studio 的托管 UI 连接你的本地服务器——用同一个免费 LangSmith 账号登录；仅用 Studio 不需要 API Key）。图注册见仓库根目录 `langgraph.json`；ReAct Agent 可在 Assistant 配置面板传入 `user_id` / `tenant_id`（默认为开发占位值）。

注：host 侧运行的图经 localhost 端口访问栈内服务；所需的 `DATABASE_URL` / `PROFILE_SERVICE_URL` / `JOB_SERVICE_URL` 覆盖已写入 `infra/.env`（本地开发已就绪）。
