# JobCopilot — Deployment Runbook / 部署运行手册

Version / 版本：v1.0
Last Updated / 最后更新：2026-08-04

> Design rationale lives in [SAD ADR-010](SAD.md). This file is the procedure:
> what to run, in what order, and what each failure means.
> 设计理由见 [SAD ADR-010](SAD.md)。本文件是操作手册：执行什么、按什么顺序、
> 每种失败意味着什么。

---

## 1. How Production Is Deployed / 生产如何部署

**EN:** CI builds and Trivy-scans images to GHCR on every green `main` commit;
CD then deploys them after a **required owner approval**. The deploy itself runs
**on the server** (`infra/scripts/remote-deploy.sh`), reached through a shim that
the CD SSH key is pinned to. `infra/scripts/deploy.sh` is the manual path and
enters through the same shim, so both paths execute the same code.

Two facts drive everything else in this document:

- **The production secrets are never given to CI.** `infra/.env` lives on the
  server and is installed only by a human `deploy.sh` run. Changing an
  environment variable is therefore *not* a matter of pushing a commit (§6).
- **The shim is host provisioning, not application code.** It is installed by
  hand, once, and is never auto-updated by a deploy (§5).

**中文：** CI 在每个绿色 `main` 提交上构建镜像并经 Trivy 扫描后推送 GHCR；随后
CD 在**必需的 owner 审批**之后完成部署。部署本身在**服务器上**执行
（`infra/scripts/remote-deploy.sh`），入口是 CD SSH 密钥被钉死的那个包装器
（shim）。`infra/scripts/deploy.sh` 是手动路径，经由同一个包装器进入，因此两条
路径执行的是同一份代码。

以下两个事实决定了本文其余全部内容：

- **生产密钥绝不交给 CI。** `infra/.env` 只存在于服务器，仅由人工执行
  `deploy.sh` 时下发。因此修改环境变量**不是**「推一个提交」就能生效的事（§6）。
- **shim 属于主机 provisioning，不是应用代码。** 它由人工安装一次，且永远不会
  被部署流程自动更新（§5）。

---

## 2. Routine Release / 日常发布

**EN:** Push to `main`. CI runs; on green, CD builds, runs the E2E suites and the
Trivy scan, then pauses at the `production` environment. Approve it in the
Actions UI ("Review deployments") and the deploy proceeds. Nothing else is
needed. To confirm afterwards, see §7.

To stop deploying without reverting anything:

```bash
gh variable delete DEPLOY_ENABLED     # deploy job goes back to "skipped"
gh variable set DEPLOY_ENABLED --body true   # re-enable
```

**中文：** 推送到 `main`。CI 运行；通过后 CD 构建镜像、跑 E2E 套件与 Trivy 扫描，
然后停在 `production` 环境等待审批。在 Actions 界面点击 "Review deployments"
批准，部署即继续。除此之外无需任何操作。事后确认见 §7。

要停止自动部署而不回滚任何代码：

```bash
gh variable delete DEPLOY_ENABLED     # deploy job 回到 "skipped"
gh variable set DEPLOY_ENABLED --body true   # 重新启用
```

---

## 3. First-Time CD Setup / 首次 CD 配置

**EN:** Needed once per server. Steps 1–5 run from your machine; 6–8 configure
GitHub. Replace `<SERVER_IP>` throughout.

**1. Generate a dedicated key.** No passphrase — CI cannot type one. Its secrecy
is deliberately *not* the security boundary; step 3 is.

```bash
ssh-keygen -t ed25519 -N '' -C 'jobcopilot-cd' -f ~/.ssh/jobcopilot-cd
```

**2. Create the deploy user.** It needs the docker group and nothing else — CD
must never need root. Idempotent.

```bash
ssh root@<SERVER_IP> 'id deploy >/dev/null 2>&1 || useradd -m -s /bin/bash deploy; usermod -aG docker deploy; install -d -m 700 -o deploy -g deploy /home/deploy/.ssh; chown -R deploy:deploy /opt/jobcopilot'
```

**3. Pin the key to a forced command.** This is the security boundary. The
`printf` avoids the classic failure where a hand-pasted line has a wrong space
or a line break — sshd then silently ignores the entry and the key just "does
not work", with no diagnostic.

```bash
printf 'restrict,command="/usr/local/bin/jobcopilot-deploy" %s\n' "$(cat ~/.ssh/jobcopilot-cd.pub)" \
  | ssh root@<SERVER_IP> 'cat > /home/deploy/.ssh/authorized_keys && chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys'
```

`command=` forces every login with this key to run only the shim; whatever the
client asked for is handed to it in `SSH_ORIGINAL_COMMAND` for validation.
`restrict` disables port/agent/X11 forwarding, pty allocation and `~/.ssh/rc`.

**4. Install the shim** (root-owned so the deploy user cannot rewrite its own
limits):

```bash
scp infra/scripts/jobcopilot-deploy root@<SERVER_IP>:/usr/local/bin/jobcopilot-deploy
ssh root@<SERVER_IP> 'chown root:root /usr/local/bin/jobcopilot-deploy && chmod 755 /usr/local/bin/jobcopilot-deploy'
```

**5. Verify both paths by hand — do not skip.** The refusal path first:

```bash
ssh -i ~/.ssh/jobcopilot-cd deploy@<SERVER_IP> 'cat /opt/jobcopilot/infra/.env'
# MUST print: ERROR: this key may only run: deploy <40-hex-commit-sha>
```

If that prints the file, step 3 did not take effect — stop and fix it. Then the
accept path (idempotent; deploys the current `main`):

```bash
ssh -i ~/.ssh/jobcopilot-cd deploy@<SERVER_IP> "deploy $(git rev-parse origin/main)"
```

**6. Add the repository secrets.** Use `<` for the key: it is multi-line, and
`--body "$(cat ...)"` eats the trailing newline, which some SSH builds reject.

```bash
gh secret set DEPLOY_SSH_KEY < ~/.ssh/jobcopilot-cd
gh secret set DEPLOY_HOST --body '<SERVER_IP>'
gh secret set DEPLOY_KNOWN_HOSTS --body "$(ssh-keyscan -t ed25519 <SERVER_IP> 2>/dev/null)"
```

`DEPLOY_KNOWN_HOSTS` is not optional. Every CD run starts on a fresh runner, so
without a pinned host key every deploy would be a trust-on-first-use — a new
MITM window each time.

**7. Protect the environment** (owner approval + `main` only):

```bash
gh api -X PUT repos/<OWNER>/<REPO>/environments/production \
  -F 'reviewers[][type]=User' -F "reviewers[][id]=$(gh api user --jq .id)" \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api -X POST repos/<OWNER>/<REPO>/environments/production/deployment-branch-policies -f 'name=main'
```

**8. Turn it on:** `gh variable set DEPLOY_ENABLED --body true`. A job-level `if`
cannot read the `secrets` context, which is why the switch is a variable — and
why it doubles as the kill switch in §2.

**中文：** 每台服务器只需配置一次。第 1–5 步在本机执行，第 6–8 步配置 GitHub。
全文中的 `<SERVER_IP>` 请替换为实际地址。

**1. 生成专用密钥。** 不设口令——CI 无人值守无法输入。这把密钥的保密性**刻意
不是**安全边界，第 3 步才是。

```bash
ssh-keygen -t ed25519 -N '' -C 'jobcopilot-cd' -f ~/.ssh/jobcopilot-cd
```

**2. 建立部署用户。** 它只需要 docker 组，别无其他——CD 永远不应需要 root。可重
复执行。

```bash
ssh root@<SERVER_IP> 'id deploy >/dev/null 2>&1 || useradd -m -s /bin/bash deploy; usermod -aG docker deploy; install -d -m 700 -o deploy -g deploy /home/deploy/.ssh; chown -R deploy:deploy /opt/jobcopilot'
```

**3. 将密钥钉死到 forced command。** 这是安全边界所在。使用 `printf` 是为了避免
一个经典失败：手工粘贴时空格或换行出错，sshd 会静默忽略该行，表现为密钥「就是
用不了」，且没有任何诊断信息。

```bash
printf 'restrict,command="/usr/local/bin/jobcopilot-deploy" %s\n' "$(cat ~/.ssh/jobcopilot-cd.pub)" \
  | ssh root@<SERVER_IP> 'cat > /home/deploy/.ssh/authorized_keys && chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys'
```

`command=` 强制该密钥的每次登录都只执行包装器；客户端请求的内容会通过
`SSH_ORIGINAL_COMMAND` 交给它校验。`restrict` 关闭端口/agent/X11 转发、pty 分配
与 `~/.ssh/rc`。

**4. 安装包装器**（由 root 拥有，使部署用户无法改写自身限制）：

```bash
scp infra/scripts/jobcopilot-deploy root@<SERVER_IP>:/usr/local/bin/jobcopilot-deploy
ssh root@<SERVER_IP> 'chown root:root /usr/local/bin/jobcopilot-deploy && chmod 755 /usr/local/bin/jobcopilot-deploy'
```

**5. 手工验证两条路径——不要跳过。** 先验证拒绝路径：

```bash
ssh -i ~/.ssh/jobcopilot-cd deploy@<SERVER_IP> 'cat /opt/jobcopilot/infra/.env'
# 必须输出：ERROR: this key may only run: deploy <40-hex-commit-sha>
```

如果它真把文件打印出来，说明第 3 步未生效——立即停止并修复。然后验证接受路径
（幂等，部署当前 `main`）：

```bash
ssh -i ~/.ssh/jobcopilot-cd deploy@<SERVER_IP> "deploy $(git rev-parse origin/main)"
```

**6. 添加仓库 Secret。** 私钥用 `<` 重定向：它是多行的，而
`--body "$(cat ...)"` 会吃掉尾部换行，某些 SSH 实现会因此拒绝解析。

```bash
gh secret set DEPLOY_SSH_KEY < ~/.ssh/jobcopilot-cd
gh secret set DEPLOY_HOST --body '<SERVER_IP>'
gh secret set DEPLOY_KNOWN_HOSTS --body "$(ssh-keyscan -t ed25519 <SERVER_IP> 2>/dev/null)"
```

`DEPLOY_KNOWN_HOSTS` 不是可选项。每次 CD 都在全新 runner 上启动，若不预置主机公
钥，每次部署都等于一次「首次连接即信任」——每次都开一个中间人窗口。

**7. 保护环境**（owner 审批 + 仅限 `main`）：

```bash
gh api -X PUT repos/<OWNER>/<REPO>/environments/production \
  -F 'reviewers[][type]=User' -F "reviewers[][id]=$(gh api user --jq .id)" \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api -X POST repos/<OWNER>/<REPO>/environments/production/deployment-branch-policies -f 'name=main'
```

**8. 打开开关：** `gh variable set DEPLOY_ENABLED --body true`。job 级 `if` 读不
到 `secrets` 上下文，这正是开关必须是变量的原因——也是它能兼作 §2 停机开关的
原因。

---

## 4. Manual Deploy and Rollback / 手动部署与回滚

**EN:** Requires a clean tree, an authenticated `gh`, and root SSH access.

```bash
SERVER_IP=<SERVER_IP> SSH_KEY=~/.ssh/<root-key> ./infra/scripts/deploy.sh
GIT_REF=<older-sha> SERVER_IP=<SERVER_IP> SSH_KEY=~/.ssh/<root-key> ./infra/scripts/deploy.sh   # rollback
```

A rollback reverts the `infra/` config as well as the images, because the server
checks out the commit being deployed. Only commits that are ancestors of
`origin/main` and whose CD gating jobs went green can be deployed — by either
path.

**中文：** 要求工作树干净、`gh` 已认证、具备 root SSH 访问权限。

```bash
SERVER_IP=<SERVER_IP> SSH_KEY=~/.ssh/<root 密钥> ./infra/scripts/deploy.sh
GIT_REF=<旧提交 SHA> SERVER_IP=<SERVER_IP> SSH_KEY=~/.ssh/<root 密钥> ./infra/scripts/deploy.sh   # 回滚
```

回滚会连同 `infra/` 配置一起回退（不只是镜像），因为服务器会检出所部署的那个提
交。无论走哪条路径，只有位于 `origin/main` 祖先链上、且 CD 把关 job 全绿的提交
才可被部署。

---

## 5. Updating the Shim / 更新包装器

**EN:** The shim is **never** auto-installed. A security control must change
deliberately, visibly and rarely — refreshing it as a side effect of every
routine deploy would mean nobody ever notices it changed.

A deploy therefore **fails** when the installed shim differs from the deployed
commit's copy, which forces the correct order:

1. Install the new shim (§3 step 4) from a checkout of the commit that carries it
2. Deploy that commit

For a rollback to a commit whose shim differs, re-run as **root** with
`JOBCOPILOT_SHIM_DRIFT=allow`. The CD key cannot set this — it cannot pass
environment variables through the shim — so CD always fails closed here.

**中文：** 包装器**永远不会**被自动安装。安全控制必须刻意、可见、罕见地变更——
若把它的刷新变成每次例行部署的副作用，就再不会有人注意到它被改过。

因此，当已安装的包装器与所部署提交内的副本不一致时，部署会**失败**，从而强制正
确的顺序：

1. 从携带该变更的提交的检出中安装新包装器（§3 第 4 步）
2. 再部署该提交

若要回滚到包装器不同的旧提交，请以 **root** 身份并设置
`JOBCOPILOT_SHIM_DRIFT=allow` 重新执行。CD 密钥无法设置它——它无法穿过包装器传
递环境变量——因此 CD 在此处总是失败关闭。

---

## 6. Changing Environment Variables / 修改环境变量

**EN:** Edit your local `infra/.env.production`, then run a **manual** deploy
(§4). CD never carries `infra/.env`, so pushing a commit will not change any
environment variable in production. This applies to LLM keys, SMTP settings,
`LLM_KEY_MODE`, LangSmith tracing — everything in that file.

**中文：** 编辑本机的 `infra/.env.production`，然后执行一次**手动**部署（§4）。
CD 从不下发 `infra/.env`，因此推送提交不会改变生产的任何环境变量。这适用于 LLM
密钥、SMTP 设置、`LLM_KEY_MODE`、LangSmith 追踪——该文件中的一切。

---

## 7. Verifying a Deploy / 验证部署

**EN:** The deploy verifies itself — it compares every running container's OCI
revision label against the deployed commit and fails on any mismatch. To check
independently afterwards:

```bash
# What the containers were built from
ssh root@<SERVER_IP> "docker inspect --format '{{index .Config.Labels \"org.opencontainers.image.revision\"}}' jobcopilot-frontend-1"
# What the running processes report about themselves
ssh root@<SERVER_IP> "curl -s 'http://localhost:9090/api/v1/query?query=jobcopilot_build_info'"
```

The two answer different questions: the label describes the image, the metric
describes the process that is actually serving traffic.

**中文：** 部署会自我验证——它比对每个运行中容器的 OCI revision 标签与所部署的
提交，任何不一致都会使部署失败。事后独立核查：

```bash
# 容器由哪个提交构建
ssh root@<SERVER_IP> "docker inspect --format '{{index .Config.Labels \"org.opencontainers.image.revision\"}}' jobcopilot-frontend-1"
# 运行中的进程如何自报版本
ssh root@<SERVER_IP> "curl -s 'http://localhost:9090/api/v1/query?query=jobcopilot_build_info'"
```

两者回答的是不同问题：标签描述镜像，指标描述真正在处理流量的那个进程。

---

## 8. Fail-Closed Gates / 失败关闭的闸门

**EN:** All three refuse rather than guess. Overrides are root-only by
construction, because the CD key cannot pass environment variables.

| Gate | Fails when | Override |
|---|---|---|
| Supply chain | This commit's CD build / E2E / image-scan jobs are not green, or the GitHub API is unreachable | `JOBCOPILOT_CD_GATE=skip` |
| Shim drift | The installed shim differs from this commit's copy, or is missing | `JOBCOPILOT_SHIM_DRIFT=allow` |
| Revision check | A running container's revision ≠ the deployed commit | none — investigate |

Being unable to *ask* whether the scan passed must never read as "it passed",
which is why an unreachable API fails closed.

**中文：** 三者都是宁可拒绝也不猜测。覆盖开关在设计上仅 root 可用，因为 CD 密钥
无法传递环境变量。

| 闸门 | 何时失败 | 覆盖开关 |
|---|---|---|
| 供应链 | 该提交的 CD 构建 / E2E / 镜像扫描 job 未全绿，或 GitHub API 不可达 | `JOBCOPILOT_CD_GATE=skip` |
| 包装器漂移 | 已安装包装器与该提交的副本不一致，或根本未安装 | `JOBCOPILOT_SHIM_DRIFT=allow` |
| 版本核验 | 运行中容器的 revision ≠ 所部署提交 | 无——需排查 |

无法**询问**扫描是否通过，绝不能被读作「它通过了」——这正是 API 不可达时失败关
闭的原因。
