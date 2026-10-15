# 代码沙箱基础镜像方案

> 对应决策 A-25（预置多语言工具链 + 离线依赖缓存）与 A-28（P0 就写方案）。
> 相关：`design.md` 9.1（写回与提 PR）、`design.md` 12.4（OpenCodeReview）、
> `design.md` 12.6（沙箱预装内容）。

最后更新：2026-10-14
阶段归属：**P0 出方案与最小验证镜像**；完整镜像随 P4-A 交付。

---

## 1. 为什么必须现在做

三个约束叠在一起，使得"沙箱能不能跑代码任务"不是 P4 才该回答的问题：

1. **沙箱默认无外网**（蓝图第 9 节）。不给它预装依赖，容器里连 `pip install`
   和 `npm install` 都失败，只能跑纯标准库脚本 —— 代码任务这个功能等于没做。
2. **OpenCodeReview 需要 Node ≥ 18 与 Git ≥ 2.41**（已核实，见 `design.md` 12.4），
   而本机 Git 只有 2.39.5，低于要求。镜像里的 Git 必须自己保证版本。
3. **写回与提 PR**（A-20）需要一条受控出网通道到 GitHub。
   无外网策略与写回需求直接矛盾，必须**按目标白名单**放行，而不是简单开或关。

## 2. 镜像分层

拆成三层，避免每次改工具链就重建全部：

| 层 | 内容 | 变更频率 |
|----|------|---------|
| `base` | Debian slim + 常用系统工具（git ≥2.41、ripgrep、curl、build-essential、ca-certificates）+ 非 root 用户 | 低 |
| `lang` | Python 3.12 + uv、Node 20 + npm/pnpm、Java (Temurin)、Go、Rust（含 cargo） | 中 |
| `deps` | **离线依赖缓存**：pip wheelhouse、npm cache、maven 本地库、go mod cache、cargo registry | 高（随项目依赖变） |

**为什么拆 `deps`**：`lang` 层体积大且稳定，`deps` 层小且常变。
分开后日常只需重建 `deps`，CI 时间显著下降。

## 3. 离线依赖缓存怎么实现

这是本方案的核心。原则：**容器内永不联网装依赖，一切依赖来自镜像内的本地源。**

### 3.1 Python

- 构建期用 `uv pip download` / `pip download` 把 `requirements-sandbox.txt` 内所有包
  及其传递依赖下载为 wheel 到 `/opt/wheelhouse`。
- 容器内配置 `/etc/pip.conf`：

```ini
[global]
index-url = file:///opt/wheelhouse
no-index = true
```

- 这样容器内 `pip install <包>` 只从本地 wheelhouse 解析，绝不外呼。

### 3.2 Node

- 构建期 `npm cache add` 或预先 `npm install` 到模板项目的 `node_modules`，
  打进镜像。
- 容器内配置 `.npmrc`：`offline=true`、`cache=/opt/npm-cache`。
- 对 `npx`（OpenCodeReview 的 skill 安装方式）要特别注意：**默认会联网**。
  镜像里应**预装** `@alibaba-group/open-code-review`，而不是运行期 `npx` 拉取。

### 3.3 其他语言

Java 用预置 `~/.m2/repository`；Go 用 `GOFLAGS=-mod=mod` + 预置 `GOMODCACHE`；
Rust 用预置 `CARGO_HOME` registry。均设 `*_OFFLINE` 类开关强制离线。

### 3.4 维护流程

成员需要新包 → **申请 → 加进 `requirements-sandbox.txt` / `package-sandbox.json`
→ CI 重建 `deps` 层 → 发布新镜像版本**。
**不允许**容器内临时联网装包，也不允许成员指定镜像（见第 5 节）。

## 4. 网络策略

| 场景 | 策略 |
|------|------|
| P4-A（只读克隆 + 审查） | 默认**全拒**；仅放行模型 API 目标（供 OpenCodeReview 调用模型）与 `github.com` / `api.github.com` 只读 |
| P4-B（写回与提 PR） | 在 P4-A 基础上，按仓库粒度放行 **push** 所需的 GitHub 端点 |
| 其他一切 | 拒绝 |

落地手段：容器加入**独立 Docker network**，默认 `internal: true`（无外网）；
需要出网的运行额外挂一个受控网络，并用**出口白名单代理**限制目标域名。
不要用"直接给外网 + iptables 兜底"的做法，难以审计。

**复核清单（每次改动网络策略都要过）**：
- [ ] 白名单里是否有与代码任务无关的目标？
- [ ] 是否放行了任意端口或任意 IP？
- [ ] DNS 是否可能被用于外泄（建议只允许代理解析）？

## 5. 资源与安全

| 项 | 措施 |
|----|------|
| 用户 | 非 root（`sandbox` 用户，UID 固定） |
| CPU / 内存 | 按任务类型设硬上限（`--cpus` / `--memory`），超限杀进程 |
| 运行时间 | 硬超时（`--stop-timeout` + 任务级超时），必须能干净终止 |
| 文件系统 | 工作目录按任务隔离；根文件系统 `--read-only` + 临时目录 `tmpfs`；仅挂载任务工作区可写 |
| 能力 | `--cap-drop=ALL`、`--security-opt=no-new-privileges` |
| 镜像来源 | **只允许管理员维护的镜像**，禁止成员自定义 Dockerfile 或自选镜像 |
| 凭据 | 任务级临时凭据，**不用个人长期 token**（A-20）；用完即废 |
| 审计 | 每次沙箱运行记录：任务、镜像版本、执行者、起止时间、退出码、是否被资源限制终止 |

**关于"成员自定义镜像"**：你选了"额外多语言工具链 + 离线依赖缓存"，
未选"成员自定义镜像"。这是对的选择 —— 自定义镜像会同时打破离线缓存与安全边界。
若将来确实需要，应改为"管理员维护多个镜像变体，任务按类型选择"。

## 6. 版本管理与构建流程

- 镜像**随项目版本管理**：`sandbox/` 目录下放 Dockerfile 与依赖清单，进 Git。
- 镜像打**内容寻址标签**（`sandbox-deps:<git-sha>`）+ 语义版本别名
  （`sandbox-deps:2026.10`）。
- **每次运行记录所用镜像的确切版本**，否则历史运行不可复现（与 `design.md` 7.4 的
  "历史运行可复现"要求一致）。
- CI：构建 → **漏洞扫描**（Trivy 一类）→ 推送到私有 registry → 更新允许列表。
- 扫描出高危漏洞时**默认阻断发布**，除非显式豁免并记录理由。

## 7. P0 交付物与最小验证

P0 阶段**不做完整镜像**，只做最小验证，目的是尽早回答"OpenCodeReview 在沙箱里能不能跑"：

| # | P0 交付物 | 验收 |
|---|----------|------|
| 1 | `sandbox/Dockerfile.base` | 能构建，`git --version` ≥ 2.41 |
| 2 | `sandbox/Dockerfile.ocr`（最小验证镜像） | 基于 base，预装 Node 20 + `@alibaba-group/open-code-review` |
| 3 | 最小验证脚本 | 容器内对一个小 Git 仓库跑 `ocr review --preview`，成功输出将要审查的文件清单 |
| 4 | 网络策略验证 | 容器内 `curl https://example.com` 必须失败；对白名单目标必须成功 |
| 5 | `sandbox/requirements-sandbox.txt` | 依赖清单骨架 |

### 7.1 验证结果（2026-10-15 实测）

| 检查 | 结果 |
|------|------|
| `Dockerfile.base` 构建 | 通过；容器内 `git version 2.47.1` |
| `Dockerfile.ocr` 构建 | 通过；Node 20 + `ocr` 预装 |
| 容器内 `curl https://example.com` | **失败**（符合预期，`--network none` 生效） |
| `ocr review --preview` | 通过：`Preview: 1 file(s) changed … Will review (1): [A] demo.py` |

构建期依赖：Docker Hub 需走镜像加速器（`auth.docker.io` 直连超时）；
`deb.nodesource.com`、`registry.npmjs.org`、`mirrors.edge.kernel.org` 直连可达。

### 7.2 沙箱运行代码任务的两个固定前提（缺陷 22，P4 执行器必须照做）

第一次跑 `verify-ocr.sh` 在第 4 步失败：`Error: /work is not a git repository`。
根因不是 ocr，是 **Git 的属主检查**：挂载进来的仓库属主是宿主 uid（容器内看到是 0），
而沙箱以 uid 10001 运行，Git ≥ 2.35.2 判定 "dubious ownership" 直接拒绝打开仓库。

每次 `docker run` 必须传：

```
-e HOME=/tmp
-e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/work
```

- `safe.directory=/work`：放行挂载目录。用环境变量而不是改镜像里的 gitconfig，
  因为根文件系统只读，且挂载路径由执行器决定。
- `HOME=/tmp`：根文件系统只读，ocr / git / npm 往 `$HOME` 写缓存或配置会失败。

这两条写进 `verify-ocr.sh` 作为参考实现；**P4-A 的沙箱执行器要用同一组参数**，
否则任何依赖 Git 的工具（ocr、diff、blame）在沙箱里都起不来。

**为什么用 `ocr review --preview`**：它**不调用模型**，零成本。
若连 `--preview` 都跑不通，说明 Node/Git 依赖或离线缓存有问题；
跑通它就能把"能不能装、能不能跑"这两个问题与"模型配置"解耦，先钉死前者。

**这一步的价值**：蓝图原计划 P4 才验证 OpenCodeReview（"它的输出格式我没有核对细节，
P4 开始前要先做一次小验证"）。现在核实到它有 `--format json --audience agent` 与
`--preview`，加上这个最小镜像，**验证可以提前到 P0**，P4 的风险因此显著下降。

## 8. 已知待办

- [x] ~~Git ≥ 2.41 的具体安装方式~~：从 kernel.org 源码编 2.47.1，已验证
- [ ] wheelhouse 的初始包清单（P0 只需 openai/anthropic/google-genai 等最小集）
- [ ] 出口白名单代理的选型（Caddy 不适用，需正向代理，如 tinyproxy + 域名白名单）
- [ ] 镜像体积目标与上限（多语言工具链容易超过 2 GB）
