# 进度 · PROGRESS.md

每个 AI 会话结束前更新本文件。新会话开工前先读 `AGENTS.md`、`docs/design.md`、本文件。

最后更新：2026-10-14

## 当前状态

**阶段：规划期（尚未进入 P0）**

蓝图 1.0 已完整接收并归档，第 13 节全部 9 个问题已由用户答复，决策已登记。
用户明确本轮只产出规划文档，不写生产代码。

## 已完成

- [x] 接收并归档蓝图 1.0（PDF + 正文抽取文本，见 `docs/blueprint/`）
- [x] 通读全文 20 页，含第 13 节待确认问题
- [x] 第 13 节 9 个问题全部取得答复，登记于 `docs/decisions.md`
- [x] 建立仓库骨架与 `.gitignore`，首次提交
- [x] 核实本机工具链现状（见下方「环境现状」）

## 已完成（第二轮）

- [x] 第二轮补充意见（5 点）全部登记，新增决策 A-12 ~ A-18
- [x] 第三轮确认：4 项已答，新增决策 A-19 ~ A-21
- [x] 产出 `docs/design.md`（538 行，含中转站接入层、扩展点预留、技能系统章节）
- [x] 产出 `docs/api-contract.md`（草案，P0 细化）
- [x] 产出两份 `AGENTS.md`（后端 101 行、前端 79 行）
- [x] 产出 `docs/tooling.md`（开发期工具 + 产品内置技能系统，两部分）
- [x] 产出 5 份 ADR + ADR 索引
- [x] 核实 MAF 部分事实（部分检索受阻，见 design.md 12.1）

## 工作模式变更（2026-10-14）

用户确认：**P0 之后交给 Codex 执行，Claude 负责指挥、审查与验收把关，不直接写代码。**
执行手册见 [`handoff-codex.md`](handoff-codex.md)。

## 进行中

- [x] **外部核实全部完成**：MAF（检查点 / HITL / OTel / YAML / Skills / base_url）、
  OpenCodeReview CLI、嵌入模型、pgvector 维度上限、中文检索方案
- [x] A-21 已修订为 A-26（方案乙：MAF 稳定 Skills API + 自研 DbSkillsSource）
- [x] **P0 代码已完成**（后端 56 文件 ~2,900 行，前端 7 文件 ~685 行）
- [x] **P0 部分验证**：语法检查全通过；**13/27 个测试实际跑过并全绿**；
      跑起来后发现并修复 3 个真实缺陷
- [ ] ⚠️ **P0 剩余验证交给 Codex**（A-33）：本机 pypi 与 npm 均被沙箱拒绝，
      装不上 `email-validator` / anthropic / google-genai / asyncpg / pgvector，
      且有 14 个测试、ruff/pyright/lint-imports、前端依赖与端到端验收从未跑过。
      收尾清单见 `handoff-codex.md` 第五节 P0-V1 ~ P0-V7。

## 已修复的缺陷（靠"真的跑一遍"发现）

| # | 缺陷 | 后果 | 修法 |
|---|------|------|------|
| 1 | `HTTP_422_UNPROCESSABLE_ENTITY` 已弃用（starlette 1.7.0） | 配了 `filterwarnings=error`，**整个应用无法导入** | 改用字面量状态码 |
| 2 | 协议适配器急切导入 | "只用 mock"也必须装齐 anthropic 与 google-genai，**P0 验收路径自身跑不起来** | PEP 562 惰性导入 + 只处理启用中条目 |
| 3 | 漏声明 `email-validator` | `EmailStr` 导致 `app.main` 完全无法导入 | 改 `pydantic[email]>=2.9` |

## 预算默认值（A-30）

每人每月 **$50** / 每日 **$10** / 单次运行 **$2**，全局可配。80% 告警、100% 中止。

## 交付给执行方的任务卡

| 阶段 | 文件 | 状态 |
|------|------|------|
| P0 收尾 | `docs/tasks/P0-收尾.md` | 待执行（执行方第一件事） |
| P1 | `docs/tasks/P1.md` | 待执行（分 4 批：A 数据库与登录 / B 模型注册表 / C 三家接入 / D 会话与切换） |
| P2–P6 | 未拆分 | 任务名与约束见 `docs/handoff-codex.md` 第四节 |

## 待办

- [ ] P0 开工前：升级 Git 到 ≥2.41、安装 uv/ruff/pyright/docker/psql、`gh auth login`
- [ ] P0 开工前：跑 `uv pip index versions agent-framework` 确认真实版本
- [ ] 用户答复 `docs/decisions.md` 第七节的遗留项

## 环境现状（本机，2026-10-14 实测）

| 工具 | 状态 |
|------|------|
| Python | 3.12.8（蓝图要求 3.11+，满足） |
| Node / npm | 24.21.0 / 11.19.0 |
| git | 2.39.5 |
| Homebrew | 7.0.8 |
| gh | 2.102.0，**未登录** |
| uv、ruff、pyright、docker、psql、caddy | **均未安装** |

注意：git 2.39.5 低于 OpenCodeReview 要求的 Git 2.41+，P4 前需升级。

## 已知问题与风险

| # | 风险 | 状态 |
|---|------|------|
| 1 | 写回与提 PR 超出蓝图原范围，权限模型与沙箱要相应改动 | **已缓解**：用户确认分阶段（P4-A 只读 / P4-B 写回），见 D-1 |
| 16 | **P0 代码从未运行过**（编写方装不上测试依赖） | 未验证代码必然有错，P0-V2/V3 会红，属预期 |
| 17 | `frontend/src/api/schema.d.ts` 目前是手写占位，非 OpenAPI 生成 | 必须跑 `npm run gen:api` 覆盖 |
| 2 | 预算上限无具体默认值，首次部署需补一个保守值 | 不阻塞，上线前定 |
| 3 | MAF 预览期教程与 1.0 文档写法不一致（例如会话的叫法） | 代码必须对照 1.x 官方文档与 samples，并锁定版本 |
| 4 | 官方检查点示例只有内存与文件存储，无 Postgres 实现 | P4 需自研数据库检查点存储 |
| 5 | OpenCodeReview 输出格式未核实，能否稳定解析未知 | P4 前先做一次最小验证 |
| 6 | 无评测集，换模型/升级 MAF/改提示词无法判断变好变差 | P3 起建知识库问答集，P4 起建工作流回归用例 |
| 7 | 本会话沙箱基本拦截出网，依赖安装需你在终端执行 | 我给命令，你执行 |
| 8 | 子代理因账户额度失败（403），已改为直接检索 | **已全部核实完毕** |
| 12 | **OTel 的 `enable_sensitive_data=True` 会把 prompt 与工具参数写入 span** | 与蓝图"日志脱敏"冲突，已写进禁止事项 |
| 13 | **OTel 的 token 在 `invoke_agent` span 上重复计数** | `usage_logs` 直接累加会翻倍，必须只在 `chat` span 求和 |
| 14 | **YAML 导入可绕过"配置不授予权限"**（`HttpRequestAction` 等有副作用 action） | **真实越权路径**，见 design.md 12.8.2 / 14.2 |
| 15 | **A-21 前提被推翻**：MAF Skills 已稳定，不再是预览功能 | 需用户重新拍板，见 design.md 14.1 |
| 10 | pgvector 索引最多 2000 维（`vector`），3-large 的 3072 维需 halfvec 或截断 | **已发现并记录**，见 design.md 12.5.1 |
| 11 | 沙箱默认无外网，不预置离线依赖则代码任务无法运行 | 已定为 A-25，需自建沙箱镜像 |
| 9 | MAF 版本号各源矛盾（1.0.1 ~ 1.18.0） | 装依赖前必须自己跑 `uv pip index versions` 确认 |
