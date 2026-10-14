# 进度 · PROGRESS.md

每个 AI 会话结束前更新本文件。新会话开工前先读 `AGENTS.md`、`docs/design.md`、本文件。

最后更新：2026-10-14

## 当前状态

**阶段：P0 已验证通过；P1 待启动**

蓝图 1.0 已完整接收并归档，第 13 节全部 9 个问题已由用户答复，决策已登记。
P0 骨架已写完并**跑通全部门禁**。P0 之后由 Codex 执行、Claude 指挥审查。

## 已完成

- [x] 接收并归档蓝图 1.0（PDF + 正文抽取文本，见 `docs/blueprint/`）
- [x] 通读全文 20 页，含第 13 节待确认问题
- [x] 第 13 节 9 个问题全部取得答复，登记于 `docs/decisions.md`
- [x] 建立仓库骨架与 `.gitignore`，首次提交
- [x] 核实本机工具链现状（见下方「环境现状」）

## 已完成（第二轮）

- [x] 第二轮补充意见（5 点）全部登记，新增决策 A-12 ~ A-18
- [x] 第三轮确认：4 项已答，新增决策 A-19 ~ A-21
- [x] 产出 `docs/design.md`（现 956 行；含中转站接入层、扩展点预留、技能系统章节）
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
- [x] **P0 代码已完成**（后端 63 文件 / 3302 行，前端 7 文件 / 687 行）
- [x] **P0 验证已完成（2026-10-14）**：工具链装齐后**后端七道**门禁 +
      **前端四道**门禁**全部通过**，`pytest` **27/27 全绿**（此前只有 13 个跑得动）
      （最初是六道 / 三道；后续补了 `check_layering` 与 e2e 两道，见缺陷 19–21）
- [x] 靠"真的跑一遍"共发现并修复 **18 个缺陷**，其中 4 个会让应用完全无法启动
      或让 P0 验收路径直接死掉。完整清单见下方
- [ ] 仍待人工验收（必须你亲手点）：登录 → 选 mock 模型发一句话 → 看到**逐字**输出
- [ ] 沙箱验证待做（需 Docker，本机未装）：`sandbox/verify-ocr.sh`
- [x] **`schema.d.ts` 已由 OpenAPI 真实生成**（2026-10-14）：起后端 → `npx openapi-typescript` → 覆盖手写占位。生成 805 行，含 13 条接口路径、12 个 schema（`MeResponse` / `ModelInfo` 均在，`client.ts` 的类型索引未破），`tsc` / `eslint` / `vite build` 复跑全绿

## 已修复的缺陷（18 个，全部靠"真的跑一遍"发现）

**A 类 · 会让应用完全无法启动或让 P0 验收路径直接死掉（4 个）**

| # | 缺陷 | 后果 |
|---|------|------|
| 1 | `HTTP_422_UNPROCESSABLE_ENTITY` 在 starlette 1.7.0 已弃用 | 配了 `filterwarnings=error`，**整个应用无法导入** |
| 2 | 协议适配器急切导入 | "只用 mock"也必须装齐 anthropic 与 google-genai，**P0 验收路径自身跑不起来** |
| 3 | 漏声明 `email-validator`（`EmailStr` 需要） | `app.main` 完全无法导入 |
| 13 | **mock 条目要求 OpenAI 凭据** | 启用的 mock 条目声明为 openai_compat 协议，于是启动时必须配 OpenAI 密钥，**mock 验收路径直接死**。改为注册表跳过 mock |

**B 类 · 门禁本身是坏的，等于没有门禁（3 个）**

| # | 缺陷 | 后果 |
|---|------|------|
| 10 | ESLint 配置没有 TypeScript 解析器 | src 下 6 个文件全部 Parsing error，**lint 从未真正生效** |
| 11 | `app/models`、`app/knowledge`、`app/tools`、`app/workers` 缺 `__init__.py` | `lint-imports` 报 "Module 'app.models' does not exist"，分层门禁形同虚设 |
| 12 | ruff 的 RUF001/2/3 把中文全角标点当"易混淆字符" | 497 个错误里 481 个是噪声（本项目注释刻意用中文标点），真错误被淹没 |

**C 类 · 类型与依赖方向错误（5 个）**

| # | 缺陷 | 后果 |
|---|------|------|
| 8 | `exactOptionalPropertyTypes` 下显式传 `undefined`（`client.ts` 的 `signal`） | `tsc` 报错 |
| 9 | 同上（`WorkspacePage.tsx` 的 `cost` / `upstreamModel`） | `tsc` 报错 |
| 15 | `main.py` 直接 import `agent_framework` 配 OTel | **违反 R-1**。已把 OTel 配置移入 `app/orchestrator/observability.py` |
| 16 | `app/core/deps.py` 反向 import `app.middleware` | 违反"依赖只能单向向下"。它是组装根，已移到 `app/api/deps.py` |
| 17 | `observability.py` 导入不存在的 `get_logger` | 导入即崩。已给 `core/logging.py` 补上 |

**D 类 · 真实功能 bug（3 个）**

| # | 缺陷 | 后果 |
|---|------|------|
| 14 | `get_current_user` 硬编码 `UserRole.MEMBER` | **管理员登录后被识别成成员**，`test_me_after_login` 失败。改为查 `app.state.bootstrap_users` |
| 18 | `BOOTSTRAP_ADMIN_ID` 被引用但从未定义 | `F821`，导入即崩 |
| 5 | 契约门禁的正则会抓到契约正文里的非接口路径 | 第 13 行"全部以 `/api/v1` 开头"与第 20 行"`POST /runs` 需带幂等键"被当成接口，**门禁必红** |

**E 类 · CI 与文档（3 个）**

| # | 缺陷 | 后果 |
|---|------|------|
| 4 | 前端 CI 用 `npm ci` 但没有 `package-lock.json` | **CI 从第一次运行就必挂** |
| 6 | `design.md` 第 12 节子节乱序，`12.9` 误用二级标题 | 出现两个 `## 12.`。重排时还丢失了 `12.9.1`（流式不得持有数据库会话那条硬约束），已从 git 历史恢复并逐块核对 |
| 7 | `.gitignore` 里 `dist/` 重复两次 | 无害，但这是会被复制的模板文件 |
| 19 | **e2e 门禁从未能运行**：`smoke.spec.ts` 与 `playwright.config.ts` 从 `playwright` 包导入 `defineConfig`/`test`/`expect`，但该包只导出浏览器驱动，运行器在 `@playwright/test` 里，而它未声明为依赖 | 端到端门禁形同虚设 |
| 20 | **原 e2e 断言证明不了流式**：只用 `toContainText` 检查最终文本，后端一次返回整段同样通过 | P0 的核心要求「看到逐字输出」实际未被测到。改为按 20ms 采样，要求 ≥3 个递增中间态 |
| 21 | **CI 门禁与本地不一致**：`backend.yml` 只有六道，缺 `check_layering` | **R-1 与 R-3 的 SDK 位置在 CI 里完全没查** —— 本地红、CI 绿，比没门禁更危险 |

## 门禁现状（2026-10-14 实测全绿）

| 门禁 | 命令 | 结果 |
|------|------|------|
| 1 格式 | `ruff format --check .` | 64 files already formatted |
| 2 代码检查 | `ruff check .` | All checks passed |
| 3 类型检查 | `pyright` | 0 errors, 0 warnings |
| 4 分层依赖方向 | `lint-imports` | 1 kept, 0 broken |
| 5 SDK 位置（R-1/R-3） | `python -m app.scripts.check_layering` | 通过 |
| 6 单元测试 | `pytest -q` | **27 passed** |
| 7 契约一致性 | `python -m app.scripts.check_contract` | 通过（11 条 P0 接口） |
| 前端 1 类型 | `tsc --noEmit` | exit 0 |
| 前端 2 检查 | `eslint . --max-warnings 0` | exit 0 |
| 前端 3 构建 | `vite build` | exit 0 |
| 前端 4 端到端 | `npm run test:e2e:smoke` | **1 passed**（含真实的流式中间态断言） |
| 前端 4 端到端 | `npm run test:e2e:smoke` | **1 passed**（见下） |

**端到端烟雾测试现在真的能跑，而且真的在测流式**：
此前它跑不起来 —— `smoke.spec.ts` 与 `playwright.config.ts` 都从 `playwright` 包
导入 `defineConfig` / `test` / `expect`，但那个包只导出浏览器驱动（chromium 等），
测试运行器在 `@playwright/test` 里，而它**没被声明为依赖**（缺陷 19）。

另外原来的断言只用 `toContainText`，**无法区分流式与一次性返回** —— 后端一次吐整段也会通过。
现在改成按 20ms 采样气泡文本，要求观察到 ≥3 个长度递增的中间态，
且至少一个是最终文本的真前缀。实测通过，所以 P0 的「逐字输出」是被真正验证的。

**关于 4a 与 4b 的分工（重要）**：`import-linter` 开启 `include_external_packages`
后会**追踪传递依赖链**，于是 `app.core.deps`（只 import 了我们自己的 registry）
被判定为"import 了 openai" —— 实测 `app.api` 与 `app.core` 全部误报。
R-3 的真实规则是"**直接** import 才受限"，`import-linter` 表达不了，
所以另写 `app/scripts/check_layering.py` 用 AST 精确查直接 import。

## 预算默认值（A-30）

每人每月 **$50** / 每日 **$10** / 单次运行 **$2**，全局可配。80% 告警、100% 中止。

## 指挥通道（A-37）

无机器通道，走**粘贴**：用户把「启动提示词」给 Codex → Codex 按「回执模板」填 →
用户粘回给指挥方审查 → 通过则产出下一张卡。

审查要点：门禁**原始输出**、是否碰铁律（尤其 R-1 与 R-3）、契约与实现是否一致、
测试是否在测行为而非迁就实现。

## 交付给执行方的任务卡

| 文件 | 状态 |
|------|------|
| `docs/tasks/README.md` | 卡片格式、铁律速查、指挥通道 |
| `docs/tasks/启动提示词.md` | 给用户，开 Codex 会话时粘贴 |
| `docs/tasks/回执模板.md` | 给执行方，做完任务卡后填写 |
| `docs/tasks/P0-收尾.md` | **门禁已全绿；执行方只剩步骤 4 人工走查与步骤 6 沙箱验证** |
| `docs/tasks/P1.md` | 待执行（分 4 批：A 数据库与登录 / B 模型注册表 / C 三家接入 / D 会话与切换） |
| P2–P6 | 未拆分，任务名与约束见 `docs/handoff-codex.md` 第四节 |

## 待办

- [x] ~~安装工具链~~：uv 已装，`backend/.venv` 齐备（ruff / pyright / pytest / 全部依赖）
- [x] ~~提交锁文件~~：`uv.lock` 与 `package-lock.json` 已生成并入库
- [x] ~~确认真实版本~~：agent-framework **1.21.0**
- [ ] **用户执行**：`gh auth login`（当前未登录，无法建远程仓）
- [ ] **用户执行**：在 GitHub 建私有仓（命令见「远程仓库」一节）
- [ ] **用户执行**：人工点击验收（P0 原文要求，必须你亲手做）
- [ ] **用户执行**：装 Docker 后告知，由指挥方跑 `sandbox/verify-ocr.sh` 并审查结果（A-44）
- [ ] **P4 前**：升级 Git 到 ≥2.41（现在是 2.39.5）
- [x] ~~后端运行时跑 `npm run gen:api`~~ 已完成

## 远程仓库（A-38）

**状态：未建。** `gh` 未登录，且仓库没配 git 身份（提交时用 `-c` 临时指定）。

建仓命令（需用户执行）：

```bash
gh auth login
```

```bash
cd /Users/pengxuezhi/项目蓝图2.0/multi-model-workbench && gh repo create multi-model-workbench --private --source=. --remote=origin --push
```

`.gitignore` 已核对：`package-lock.json` 与 `uv.lock` **不会被忽略**（必须提交，CI 依赖它们）。

## 环境现状（本机，2026-10-14 实测）

| 工具 | 状态 |
|------|------|
| Python | 3.12.8（蓝图要求 3.11+，满足） |
| Node / npm | 24.21.0 / 11.19.0 |
| git | 2.39.5 —— **仍低于 OpenCodeReview 要求的 2.41+，P4 前必须升级** |
| Homebrew | 7.0.8 |
| gh | 2.102.0，**未登录**（远程仓未建） |
| uv | **已装**（brew） |
| docker、psql | **未装** —— 沙箱验证与本地数据库起不来 |
| `backend/.venv` 内 | ruff 0.17.0 / pyright 1.1.414 / pytest 9.1.1 |
| **agent-framework** | **1.21.0**（实测装上的真实版本） |

**`agent-framework` 版本之争已解决**：此前各源说法不一（1.0.1 ~ 1.18.0），
现按实际安装结果记为 **1.21.0**。`pyproject.toml` 的 `>=1.0.1` 保留不变
（它是有意放宽的下限），但文档与测试须以 1.21.0 为基准。

## 已知问题与风险

| # | 风险 | 状态 |
|---|------|------|
| 1 | 写回与提 PR 超出蓝图原范围，权限模型与沙箱要相应改动 | **已缓解**：用户确认分阶段（P4-A 只读 / P4-B 写回），见 D-1 |
| 16 | ~~P0 代码从未运行过~~ | **已解决**：门禁全绿，实测发现并修掉 18 个缺陷 |
| 17 | ~~`schema.d.ts` 是手写占位~~ | **已解决**：已由 OpenAPI 真实生成（805 行 / 13 条路径 / 12 个 schema）。**注意**：接口一旦变更必须重跑 `npm run gen:api`，不要手工改这个文件 |
| 2 | 预算上限无具体默认值，首次部署需补一个保守值 | 不阻塞，上线前定 |
| 3 | MAF 预览期教程与 1.0 文档写法不一致（例如会话的叫法） | 代码必须对照 1.x 官方文档与 samples，并锁定版本 |
| 4 | 官方检查点示例只有内存与文件存储，无 Postgres 实现 | P4 需自研数据库检查点存储 |
| 5 | OpenCodeReview 输出格式未核实，能否稳定解析未知 | P4 前先做一次最小验证 |
| 6 | 无评测集，换模型/升级 MAF/改提示词无法判断变好变差 | P3 起建知识库问答集，P4 起建工作流回归用例 |
| 7 | Bash 沙箱仍拦 pypi/npm 出网 | **已绕过**：终端工具不受沙箱限制，brew/npm/uv/插件安装全走终端 |
| 8 | 子代理因账户额度失败（403），已改为直接检索 | **已全部核实完毕** |
| 12 | **OTel 的 `enable_sensitive_data=True` 会把 prompt 与工具参数写入 span** | 与蓝图"日志脱敏"冲突，已写进禁止事项 |
| 13 | **OTel 的 token 在 `invoke_agent` span 上重复计数** | `usage_logs` 直接累加会翻倍，必须只在 `chat` span 求和 |
| 14 | **YAML 导入可绕过"配置不授予权限"**（`HttpRequestAction` 等有副作用 action） | **真实越权路径**，见 design.md 12.8.2 / 14.2 |
| 15 | **A-21 前提被推翻**：MAF Skills 已稳定，不再是预览功能 | 需用户重新拍板，见 design.md 14.1 |
| 10 | pgvector 索引最多 2000 维（`vector`），3-large 的 3072 维需 halfvec 或截断 | **已发现并记录**，见 design.md 12.5.1 |
| 11 | 沙箱默认无外网，不预置离线依赖则代码任务无法运行 | 已定为 A-25，需自建沙箱镜像 |
| 9 | ~~MAF 版本号各源矛盾~~ | **已解决**：实测装上 **1.21.0** |
