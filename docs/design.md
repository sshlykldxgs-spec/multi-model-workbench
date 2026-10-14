# 设计文档 · design.md

> 本文件是**蓝图 1.0 的落地版**，由后端会话维护。
> 蓝图原文见 `docs/blueprint/蓝图1.0.pdf`；决策登记见 `docs/decisions.md`。
> 与蓝图冲突时以本文件为准，并在 `docs/decisions.md` 记录偏差理由。
>
> 状态：草案。带 `【待核实】` 标记的段落依赖外部事实核实，见第 12 节。

最后更新：2026-10-14

---

## 0. 产品一句话

面向小团队内部的多模型 AI 工作台：同一界面用 OpenAI / Azure OpenAI / Anthropic Claude /
Google Gemini（**以及各类中转站**），让多个 agent 分工协作、调用工具与 MCP，
并基于上传文件回答问题。任务既含通用知识工作，也含代码任务。

**第一版不做**：公开注册、计费、多租户隔离、多模型并排对比、国内模型与本地模型、
移动端原生应用。但**架构上必须为前四项预留位置**（见第 3 节）。

---

## 1. 分层与依赖规则

五层，依赖只能单向向下。**MAF 只出现在编排层**。

```
┌─────────────────────────────────────────────────────────┐
│ 前端  React + TS + Vite + Tailwind + shadcn/ui           │
│       工作区（用）              配置区 /studio（设计）      │
└───────────────────────┬─────────────────────────────────┘
                        │ REST (OpenAPI) + SSE
┌───────────────────────▼─────────────────────────────────┐
│ API 层  FastAPI                                          │
│   中间件链：请求ID → 认证 → 授权 → 配额/预算 → 内容策略      │
│             → 审计 → 计量                                 │
│   路由只做参数校验，调用 service                            │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│ 编排层  Microsoft Agent Framework 1.x   ← 唯一允许 import  │
│   工作流引擎        RoleExecutor 槽位      中间件           │
│   Planner→Worker→   模型 / 模型组 / 命令行   预算与轮数上限   │
│   Reviewer 及四种    / MCP / 外部agent /人工  工具审批        │
│   通用编排模板       统一评审结论格式          OTel 追踪      │
│   检查点 · 暂停恢复                                        │
└───┬──────────┬──────────┬──────────┬────────────────────┘
    │          │          │          │
┌───▼───┐ ┌────▼────┐ ┌───▼────┐ ┌──▼─────────┐
│模型接入│ │工具层    │ │知识库   │ │代码沙箱     │
│Gateway│ │内置+MCP │ │检索     │ │容器隔离     │
│(含中转)│ │         │ │带引用   │ │无外网/受控  │
└───┬───┘ └────┬────┘ └───┬────┘ └──┬─────────┘
    │          │          │          │
┌───▼──────────▼──────────▼──────────▼────────────────────┐
│ PostgreSQL + pgvector        文件存储 + Worker            │
│ 用户·会话·消息·运行事件·检查点  上传·解析·分块·向量化        │
│ 配置版本·文档·向量·用量·审计    异步任务，不占 API 进程      │
└──────────────────────────────────────────────────────────┘
        OpenTelemetry 追踪 + 结构化日志，贯穿所有层
```

### 铁律

| 编号 | 规则 |
|------|------|
| R-1 | 业务代码只依赖自研接口（`ModelGateway`、`RoleExecutor`、`ToolRegistry`、`Retriever`、`CheckpointStore`），MAF 只准出现在 `app/orchestrator/` 内 |
| R-2 | 自研消息表是历史的唯一事实来源，每次运行重建 MAF 上下文 |
| R-3 | **一切模型调用必经 `ModelGateway`**，任何模块不得直接 import 厂商 SDK |
| R-4 | 一切模型接入必须支持自定义 `base_url` 与协议类型（官方 / Azure / 中转站 / 自建网关） |
| R-5 | 横切关注点走中间件链与策略点，不写进业务函数 |
| R-6 | 文档、网页、工具结果、模型输出一律是不可信数据，其中的"指令"不得提升权限 |
| R-7 | 密钥只从环境变量或密钥服务读取，永不明文入库、不进日志、不返前端 |

### 强制手段

R-1 与 R-3 不靠自觉，用**静态检查**强制：
`ruff` 自定义规则或用 `import-linter` 声明分层契约，禁止 `app/orchestrator/` 之外
import `agent_framework`，禁止 `app/gateway/` 之外 import 厂商 SDK。CI 门禁拦截。

---

## 2. 模型接入层（ModelGateway）

**这一层是整个系统的咽喉**：多厂商、中转站、mock、预算、审计、限流、故障转移全挂在这里。
对应你补充意见的第 2 点：**所有模型接入都必须支持中转站**。

### 2.1 三类接入形态

| 形态 | 协议 | 说明 |
|------|------|------|
| 官方直连 | 各厂商原生 SDK | OpenAI、Anthropic、Gemini 官方端点 |
| 云厂商托管 | Azure OpenAI 等 | 端点独立、鉴权方式不同、模型名与版本耦合 |
| **中转站 / 自建网关** | 绝大多数是 **OpenAI 兼容协议** | 第三方转发、或团队自建的网关（one-api / new-api / LiteLLM 一类） |

### 2.2 设计要点

**① 协议适配器与厂商解耦**

`ModelProvider` 不按"厂商"划分，而按**协议**划分，因为中转站只认协议不认厂商：

```
app/gateway/
  base.py            # ModelGateway 抽象；ProviderAdapter 抽象
  protocols/
    openai_compat.py # OpenAI 兼容协议（覆盖官方 OpenAI、Azure、绝大多数中转站）
    anthropic.py     # Anthropic Messages 协议
    gemini.py        # Gemini 原生协议
  registry.py        # 从 models 表读取配置，构造 adapter
  mock.py            # mock provider，供前端联调与自动测试
  health.py          # 连通性与能力探测
  policy.py          # 路由、重试、降级、限流
```

新增一个中转站通常**只是加一行配置**：`protocol=openai_compat` + `base_url` + 凭据引用。

**② 数据库配置，不写死在代码里**

`models` 表（蓝图已定）在落地时需补齐以下字段：

| 字段 | 用途 |
|------|------|
| `protocol` | `openai_compat` / `anthropic` / `gemini`，决定用哪个适配器 |
| `base_url` | 官方端点、Azure 端点或中转站地址 |
| `credential_ref` | 指向密钥存储的**引用名**，不是密钥本身 |
| `provider_label` | 展示用（"官方 Anthropic"、"XX 中转"），界面上要能区分 |
| `capability_overrides` | **管理员手动覆盖**能力标记，见 ③ |
| `routing_priority` / `fallback_group` | 路由与降级，见 ④ |
| `is_relay` | 是否中转（用于界面上标注数据走向） |

**③ 能力标记必须可手动覆盖（中转站的坑）**

中转站转发时**实际能力常少于官方**：可能不支持 tool calling、不支持流式、看不到真实
上下文长度、图片支持不一、甚至悄悄换模型。所以：

- 自动探测结果只作**建议值**，管理员可手动覆盖；
- 每次运行前，**按目标模型的能力标记检查**（例如会话中途切换模型时：
  目标模型不支持工具调用而历史里有工具消息 → 提前报 `model_unavailable` 而不是运行到一半崩）；
- 界面标注"此模型经中转提供服务，能力可能与官方不同"。

**④ 路由、重试与降级**

- **重试**：仅对可重试错误（连接失败、429、5xx）。已产生输出的流式请求**不重试**，避免重复计费。
- **降级**：同一 `fallback_group` 内按 `routing_priority` 降级到备用条目（例如官方挂 → 中转兜底）。
  降级必须在事件流里**明确告知用户**，不能静默换模型；且降级前后能力的交集决定可用工具。
- **限流**：按条目维度做并发上限与速率限制，避免被中转站封禁。
- **超时**：分连接超时与首字节超时（流式场景首字节超时比总超时更关键）。

**⑤ 计量与审计（收费的前提）**

每次调用记录：`条目`、`上游真实模型名`（中转站可能返回不同的 model 字段）、
输入/输出 token、按**条目单价**计算的费用、耗时、是否降级、是否重试、所属运行与用户。
中转站单价与官方不同，所以**单价挂在条目上，不挂在模型名上**。

**⑥ 凭据归属：团队密钥与个人密钥共存**

凭据**挂在模型条目上**，条目可多个。这样一套抽象同时覆盖两种归属：

| 归属 | 可见范围 | 计量归属 | 预算 |
|------|---------|---------|------|
| 团队条目 | 全体成员可用 | 记入团队成本与个人用量 | 占用团队配额 |
| 个人条目（用户私有） | 仅本人与管理员 | 记入个人用量，**不计团队成本** | 计入个人预算 |

账目上分开显示「团队配额」与「自备额度」。个人条目同样受能力标记校验与审计约束，
不因为「是自己出钱」而放宽工具审批。

**⑦ 数据走向提示**

中转站意味着**数据经第三方转发**。界面上必须能看出当前条目是官方还是中转，
并在选择中转条目时给出提示。这是蓝图第 8 节"数据外发"要求的具体落地。

### 2.3 与 MAF 的关系

蓝图要求"通过 MAF 自带的连接器接入三家模型"。落地时**调整**为：
MAF 的连接器只作为 `ProviderAdapter` 的**可选实现之一**，而不是唯一路径。
理由：中转站与 Azure 的端点、鉴权、能力差异，需要我们自己控制；
且 MAF 预览功能不进核心路径。业务代码永远只依赖 `ModelGateway`（R-1、R-3）。

【待核实】MAF 1.x 各连接器的确切 import 路径与 client 类名，见第 12 节第 1 项。

---

## 3. 横切关注点与扩展点（为收费、封控、监管预留）

对应你补充意见的第 3 点。**第一版不实现这些功能，但必须现在就把位置留对**，
否则将来改造成本极高。

### 3.1 中间件链

API 层与编排层之间是一条**有序中间件链**，每个中间件是一个策略点：

```
请求ID → 认证 → 授权 → 配额/预算 → 内容策略 → 审计 → 计量 → [业务] → 计量落账
```

编排层内部同样有链：`预算检查 → 轮数检查 → 工具审批 → 模型调用 → 计量`。

**规则**：新功能以"插入一个中间件"的方式加入，不改动业务函数。

### 3.2 预留位置一览

| 未来功能 | 预留方式 | 第一版状态 |
|---------|---------|-----------|
| **收费 / 计费** | `usage_logs` 已有；补 `unit_price_snapshot`（计价时点的单价快照，防改价影响历史）、`cost_center`；`/admin/billing` 路由占位；`billing` 中间件占位（空实现） | 只记录用量与费用，不结算 |
| **配额 / 封控** | `quota` 中间件；`users` 补 `is_suspended`、`suspended_reason`；限流器接口；模型/知识库级白名单 | 只做预算上限与基本登录限流 |
| **内容策略 / 审核** | `content_policy` 中间件（入站与出站两个钩子）+ `policy_events` 表 | 空实现，只留钩子 |
| **监管 / 合规** | `audit_logs` 已有并**全量落地**；预留数据留存期配置、导出接口 `/admin/audit/export`、数据出境开关（知识库级模型白名单已能表达） | 审计日志完整实现（蓝图已要求） |
| **多租户** | 关键表加 **`tenant_id`（可空，单租户时全为 NULL）**；查询层统一经 `scope` 过滤 | 不做隔离，只留列 |
| **多模型并排对比** | `runs` 支持同一会话并发多个 run；`messages` 已有 `model` 与 `run_id` | 预留，第二版做 |
| **国内模型 / 本地模型** | 加一个 `protocol` 适配器即可，网关层已解耦 | 预留 |
| **跨会话长期记忆** | `MemoryStore` 接口占位 | 预留 |

**关于 `tenant_id`**：这是最值得现在做的一件事。加一个可空列几乎零成本，
将来要做多租户时不用改所有查询。蓝图明确"不做多租户"，但列为"架构上预留"，
所以**加列不加逻辑**是正确做法。

### 3.3 策略与实现分离

所有可开关的功能走**配置**，不走进代码分支：

```
策略点（代码里的固定接口）  ←  实现（可替换、可空）
   BudgetPolicy              NoopBudgetPolicy / DailyMonthlyBudgetPolicy
   ContentPolicy             NoopContentPolicy / KeywordBlockPolicy / ReviewPolicy
   RateLimitPolicy           NoopRateLimitPolicy / PerUserRateLimitPolicy
   RoutingPolicy             PriorityRoutingPolicy / FallbackRoutingPolicy
```

第一版一律挂 `Noop*` 或最简实现。这样"以后加收费、封控、监管"= 换一个策略实现 + 改配置。

---

## 4. 会话与记忆

- **自研消息表是历史的唯一事实来源**。每次运行把中性格式历史重建为 MAF 上下文。
  理由：中途切换模型需要中性格式；MAF 序列化会话能否跨厂商复用未经证实，不依赖。
- 消息内容分段存储（文本 / 工具调用 / 引用），见蓝图 `messages` 表。
- **长对话裁剪或摘要**策略放在这一层。策略要点：
  - 裁剪以**完整消息为单位**，不切断工具调用与其结果（否则会造出非法的消息序列）。
  - 裁剪遵循各厂商约束：Anthropic 要求首个消息为 user、工具结果必须紧跟对应调用。
  - 摘要本身也要走 `ModelGateway`，并计入预算与用量。
- 跨会话长期记忆第一版不做，只留 `MemoryStore` 接口。
- **切换模型时**：先按目标模型能力标记校验历史兼容性（工具消息、图片、上下文长度），
  不兼容则明确报错并给出"开始新会话"建议，不静默截断。

---

## 5. 工具与 MCP

- **工具注册表**：内置函数工具 + MCP 服务器。每条含名称、来源、风险级别、参数结构、
  超时、结果大小上限。
- **风险分级**：`read_only` / `write` / `destructive`。后两者**默认需人工确认**，
  用 MAF 的 human-in-the-loop 机制实现，工作流暂停等待。
- **只用本进程发起的 MCP**，不用厂商托管 MCP（蓝图已定）。原因：托管 MCP 的调用
  由厂商服务发出，白名单、审批、审计看不到。
- MCP 配置含地址、认证方式（加密存储）、**工具白名单**。白名单是默认拒绝：
  未列入的工具一律不可调用。
- 提示词注入防线（R-6 的落地）：
  - 工具结果与文档内容**带来源标记**进入上下文，与用户/模型直接输出视觉上区分；
  - 该类内容里出现的"指令"不改变工具白名单、不提升权限、不跳过审批；
  - 工具凭据按最小权限发放，不同工具不复用同一凭据。

---

## 6. 知识库

流程：上传 → 校验类型与大小 → 写任务表 → worker 解析/分块/向量化 → 写入 pgvector。

- **支持格式**：txt、md、docx、文字型 PDF。单文件 20 MB 上限。
- **不做**：扫描件 OCR、复杂表格解析。
- **状态机**：`queued` → `processing` → `ready` / `failed`，前端可见。
- **检索以"搜索知识库"工具形式**提供给 agent，由 agent 决定何时检索。
- **引用**：回答附文件名 + 页码或段落位置，前端可点开看原文。
- **删除**同步删除分块。
- **每个分块记录嵌入模型名**，以便将来换模型重建索引。
- **隔离**：检索时按**运行者**可见范围过滤，避免搜到他人私有文件。
  分享的配置不能越权（蓝图规则）。

【待核实】嵌入模型选型、pgvector 版本与索引、中文检索方案，见第 12 节第 3 项。

---

## 6A. 技能系统（Skills）

对应你补充意见的第 4 点。**注意区分两件事**：本节说的是**产品内置**的技能系统
（给工作台里的 agent 用）；**开发本项目时**用到的 AI 工具清单在 `docs/tooling.md`。

### 6A.1 决策已修正（重要）

原 A-21 写的是「自研 `SkillLoader`，MAF Skills 作可选实现」，理由是
「MAF Skills 仍是预览功能」。**核实后发现该理由不成立**：MAF 核心 Skills API
已移除 experimental 标记转为**稳定**（Python PR #6974 移除全部 15 个 API 的
`@experimental` 并删除 `ExperimentalFeature.SKILLS`；.NET PR #6861 同步）。
仅 MCP-based skills（`MCPSkill` / `MCPSkillsSource`，另一套 `MCP_SKILLS` 开关）仍是实验性。

**经用户 2026-10-14 确认，改为方案乙**（新决策 A-26）：

> **运行时用 MAF 稳定的 Skills API；自研 `DbSkillsSource` 实现 `SkillsSource` 接口。**

理由：我们的三项要求（**可配置、可分享、可版本管理**）本质是**存储与权限**问题，
正好由 `DbSkillsSource` 一个接口实现解决；而**运行时行为**（渐进式加载、
资源读取、脚本执行与审批）直接复用框架，没必要自己重写。

### 6A.2 技能格式（沿用 MAF 约定，不再自定义）

一个技能 = 一个目录，主文件 `SKILL.md`：

- YAML front matter：必需 `name`（小写字母数字连字符，≤64 字符）与
  `description`（单行，≤1024 字符）；
- 之后的 Markdown 正文即被注入的指令。

**我们不自定义一套字段**，直接沿用这个约定 —— 这样导出的技能可以被任何支持
Agent Skills 的工具复用，也省掉格式转换层。

### 6A.3 架构

```
SkillsSource（MAF 接口，稳定）
├── DbSkillsSource        自研：技能存数据库，随 config_versions 做版本管理（第一版）
└── （框架自带）FileSkillsSource 等   仅供开发期使用

SkillsProvider（MAF，稳定）  ← 装配 source，暴露 load_skill / read_skill_resource / run_skill_script
```

`DbSkillsSource` 的职责：把数据库里的 `SKILL.md` 正文与资源**装配成 MAF 需要的目录形态**，
并在此处做**可见范围过滤**（私有 / 指定成员 / 全团队）。

可使用的 MAF 抽象（均属稳定 API）：`Skill`、`SkillResource`、`SkillScript`、
`SkillFrontmatter`、`SkillsProvider`、`SkillsSource`、`SkillsSourceContext`、
`SkillScriptRunner`、`CachingSkillsSource`。

### 6A.4 渐进式加载与审批（重要，直接影响体验）

技能的加载是**渐进式**的：agent 先只看到**名称与简短描述**；请求匹配时才调
`load_skill` 取完整指令，`read_skill_resource` 取参考资料，`run_skill_script` 执行附带脚本。

**MAF 默认对这三个操作都要求人工审批。** 若原样上线，每次加载技能都会弹确认，
体验会很啰嗦。据此定我们的审批策略：

| 技能来源 | 加载与读取 | 执行脚本 |
|---------|-----------|---------|
| 管理员发布的**官方技能** | **默认关闭审批**（可信） | **保留审批** |
| 成员**自建技能** | 保留审批 | **保留审批** |

注意：**关闭「加载/读取」审批不等于允许自动执行脚本** —— 框架层面也没有这个等价关系。

### 6A.5 硬约束（不变）

- 技能**不授予权限**。技能不能扩大角色可用的工具集与知识库范围 ——
  那些仍由角色配置与**运行者权限**决定（本文 7.4）。
- 技能正文属**受信配置**（成员自己写的）；技能**附带的外部资源**
  （脚本、下载的文档）仍是**不可信数据**，按 R-6 处理。
- 技能不得包含密钥。需要凭据的能力必须走工具与凭据机制。
- 分享与可见范围**服从现有权限模型**，不另起一套。

### 6A.6 阶段归属

**P5（个性化配置区）**，与角色库、画布、版本管理同批交付。
但 `DbSkillsSource` 的**接口与数据表**建议在 **P0 建库时就把 `skills` 表建出来**
（只建表不加逻辑），避免 P5 改迁移。

---

## 7. 编排层：角色、执行器与工作流

对应你补充意见的第 5 点：**默认提供 Planner–Worker–Reviewer 三个角色，
但配置区可自由创建角色与安排分工，以画布编排。** 下面是它的技术落地。

### 7.1 角色是槽位，不是模型

每个角色（Planner / Worker / Reviewer / 自定义）是一个**槽位**，
由统一的 `RoleExecutor` 接口承接：

```
RoleExecutor（抽象）
├── ModelAgentExecutor     一个模型 + 一段指令
├── ModelPanelExecutor     多模型各审一遍再汇总（取交集或投票）
├── CliToolExecutor        沙箱里跑命令行工具并解析输出（OpenCodeReview）
├── McpToolExecutor        通过 MCP 调外部服务
├── ExternalAgentExecutor  A2A 外部 agent（预留）
└── HumanExecutor          暂停等待人工决定
```

**替换执行器不改工作流**，因为工作流只认槽位与统一输出格式。

### 7.1A 默认三角色的模型分配（A-34）

| 角色 | 厂商 | 理由 |
|------|------|------|
| **Planner** | **Claude** | 把任务拆成步骤清单最见长；规划质量决定整条链的走向 |
| **Worker** | **GPT** | 执行量大，选性价比高的 |
| **Reviewer** | **Gemini** | **与 Worker 不同厂商**，天然满足"评审与执行必须不同模型"；三家各占一角色，P4 一次验证三家接入 |

这份分配是**官方模板的默认值**，配置区可任意改。
关键约束不变：**Reviewer 与 Worker 不能是同一个模型**（蓝图硬要求），
如果用同一个厂商的模型，就必须用不同提示词来制造差异。

### 7.2 统一评审结论格式（关键）

Reviewer 无论由谁担任，**必须**输出同一结构。工作流只认这个格式，
适配器负责把外部工具（OpenCodeReview 等）的输出转换过来：

```json
{
  "passed": false,
  "issues": [
    { "severity": "major", "location": {"file": "a.py", "line": 42},
      "message": "……", "suggestion": "……" }
  ],
  "summary": "……"
}
```

`severity` 取 `blocker` / `major` / `minor` / `info`。外部工具无法给出的字段填空，
**不得让格式差异渗透进工作流**。

### 7.3 核心工作流与通用模板

- **核心模板**：Planner → Worker → Reviewer →（退回或通过）。默认最多重做 2 轮。
- **四种通用模板**：顺序、并发、交接（handoff）、群聊（group chat）。
- 防"自我确认"：**Reviewer 与 Worker 必须用不同模型或不同提示词**（蓝图硬要求）。
- **按任务类型路由评审**：代码任务由 OpenCodeReview 评审（可叠加模型评审），
  通用任务由模型评审。
- **可配置项**：最大轮数、预算上限、规划后是否需人工确认（默认需要）。

### 7.4 配置区与工作区的数据关系

- 配置区的角色与画布存为 `config_versions`（草稿 / 已发布）。
- **工作区只使用已发布版本**；每次运行记录所用配置版本，历史运行可复现。
- **配置只决定"用什么、怎么分工"，不授予权限**。工具审批、预算、知识库可见范围
  **永远按运行者权限计算** —— 别人分享的配置不能让你越权。
- 发布前校验：孤立节点、循环是否设最大轮数、引用的模型/工具/知识库是否可用、
  是否设预算上限。
- 分享默认私有；被分享配置默认只读，可"复制后修改"；管理员可设为官方模板。
- 导出格式尽量贴近 MAF 1.0 的 YAML 声明，画布布局另存。具体字段 P5 前核对。

### 7.5 画布

**基于成熟的流程图组件库实现，不从零手写**（蓝图明确要求，前端最重的一块）。
后端只存图结构（节点、边、条件、布局），校验在发布前做。

---

## 8. 运行、状态与检查点

- **一次"运行"** = 一次对话回合或一次工作流执行。
- **状态**：`queued`、`running`、`waiting_approval`、`succeeded`、`failed`、`cancelled`。
- **事件持久化**：`run_events` 按序号落库，前端断线后按序号续传，支持回放。
- **检查点**：MAF 官方只有内存与文件存储示例，**无 Postgres 实现**，
  故 P4 需自研 `CheckpointStore`（实现 MAF 的检查点接口，落库）。
  【待核实】MAF 检查点接口的确切形状，见第 12 节第 1 项。
- **取消 / 超时 / 预算中止**三条路都要能干净收尾：已产生的输出与用量必须落库，
  状态必须终结，不允许留下"永远 running"的记录。
- **重启恢复**：进程重启后，`running` 状态的运行要么能凭检查点恢复，要么明确标为 `failed`
  并说明原因，**不允许静默丢失**。

---

## 9. 安全与权限

蓝图第 8 节的最大判断：风险不在登录，而在"模型被不可信内容诱导调工具"与"数据外流"。落地要点：

| 领域 | 措施 |
|------|------|
| 账号 | 管理员邀请制；密码 **argon2** 哈希；会话 Cookie 设 `HttpOnly` + `SameSite`；登录限流；角色只有 `admin` / `member` |
| 密钥 | 只存服务端；日志脱敏；定期轮换；中转站密钥同等级对待；**每个条目独立凭据，不复用** |
| 工具调用 | 白名单 + 风险分级；`write`/`destructive` 默认人工确认；不可信内容不得提升权限；工具最小权限凭据 |
| 代码任务 | 沙箱容器内运行；限制网络、CPU、内存、运行时间；工作目录按任务隔离；默认无外网 |
| 文件 | 类型白名单 + 大小上限；解析在 worker；存储路径不由用户决定；下载需鉴权 |
| 知识库 | 检索按可见范围过滤 |
| 数据外发 | 界面标明；可按知识库限制允许的模型；中转条目额外标注 |
| 审计 | 登录、工具审批、文件上传与删除、配置变更**全部**写审计日志 |

### 9.1 代码任务写回与提 PR（范围放大项，见 decisions.md D-1）

你选择了写回并提 PR，蓝图原推荐是不做。这两者的安全模型不同：

- **只读克隆**：凭据只需 read 权限。
- **写回与提 PR**：需要 write 权限，且**一次运行会永久改变远端仓库状态**，
  与"对话"语义完全不同，必须按副作用操作对待。

落地要求：
- 凭据用**最小权限的 App / deploy key**，禁止使用个人长期 token；
- **禁止直推默认分支**，只能推特性分支；
- **推送前人工确认**（与 `write` 级工具同等对待）；
- 每次推送记审计日志（谁、哪个运行、哪个仓库、哪个分支、哪个 commit）；
- 沙箱只放行代码托管这一个出网目标。

**已确认分阶段交付**（用户 2026-10-14 确认）：

| 子阶段 | 内容 | 验收 |
|--------|------|------|
| **P4-A** | 只读克隆 + 代码审查（蓝图原范围） | 可独立验收 |
| **P4-B** | 写回与提 PR（独立增量） | 单独一道验收关 |

这样 P4 不会因写回未完成而整体卡住。凭据用**最小权限 GitHub App**（A-20），
禁止个人长期 token；沙箱只放行 `github.com` 与 `api.github.com`。

---

## 10. 数据模型要点

蓝图第 6 节的表结构基本可直接落地。落地时需补的字段：

| 表 | 补充字段 | 原因 |
|----|---------|------|
| `models` | `protocol`、`base_url`、`credential_ref`、`provider_label`、`capability_overrides`、`routing_priority`、`fallback_group`、`is_relay` | 支持中转站、路由降级、能力覆盖 |
| `usage_logs` | `unit_price_snapshot`、`cost_center`、`upstream_model`、`is_fallback` | 计量准确、降级可追溯、为计费预留 |
| `users` | `is_suspended`、`suspended_reason` | 为封控预留 |
| 各业务表 | `tenant_id`（可空） | 为多租户预留 |
| `audit_logs` | `request_id`、`ip`、`user_agent`、`result` | 合规与追溯 |
| 新增 `policy_events` | 内容策略命中记录 | 为监管与内容审核预留 |

**密钥不进数据库明文**：`credential_ref` 只存引用名，实际密钥在环境变量或密钥服务。

---

## 11. 部署与运维

- **单台服务器，Docker Compose 一条命令起停**，Caddy 反向代理。
- 组件：Caddy、API、worker、PostgreSQL（含 pgvector）、前端静态文件、代码沙箱容器。
- 配置用环境变量，提供 `.env.example`；密钥不进仓库、不进数据库明文。
  **MAF 不会自动读 `.env`，启动时显式加载。**
- 可观测性：开 MAF 自带 OpenTelemetry；日志带 `run_id`、`user_id` 并脱敏；
  指标含请求量、延迟、错误率、token、费用。
- 成本控制：每人每日/每月预算、单次运行预算上限、工作流最大轮数、模型白名单；
  **80% 告警、100% 自动中止**。（具体数值见 decisions.md D-2，暂未定。）
- 备份：Postgres 每日 + 上传目录同步 + 定期恢复演练。
- 升级：依赖全锁；MAF 升级单独提交并跑完回归再合并。

---

## 12. 待核实项清单（进对应阶段前必须验证）

| # | 待核实 | 何时必须清楚 | 状态 |
|---|--------|------------|------|
| 1 | MAF 1.x 实际 API：包名与版本、各连接器 import 路径、工作流 API、检查点接口与是否有 Postgres 实现、MCP 注册方式、human-in-the-loop 机制、OTel 开启方式、YAML 声明支持、预览功能清单 | **P0 开工前**（决定骨架怎么写） | **已核实**：见 12.1–12.3、12.8 |
| 2 | OpenCodeReview：npm 包名与安装、`ocr review` 确切子命令与参数、依赖的 Git 版本、输出是否可稳定结构化解析、沙箱内能否跑通 | **P4 开工前**（蓝图也要求先做小验证） | **已核实**：见 12.4。`--format json --audience agent` 可稳定解析 |
| 3 | 嵌入模型选型与中文检索：最新嵌入模型型号/维度/定价、pgvector 版本与索引、Postgres 中文全文检索方案 | **P3 开工前** | **已核实**：见 12.5。**注意 pgvector 2000 维索引上限** |
| 4 | MAF 1.0 的 YAML 声明字段 | P5 开工前 | **已核实**：见 12.8.2，**但发现权限模型的严重冲突，见 12.8.2 末** |
| 5 | 本机工具链升级：Git 需 ≥2.41（当前 2.39.5）、uv/ruff/pyright/docker/psql 待安装 | P0 开工前 | 待用户执行 |

---

## 12.9 规模相关参数（团队 6–15 人，A-36）

| 项 | 初始值 | 备注 |
|----|--------|------|
| API 进程数 | 2 | SSE 是长连接，进程数不是越多越好 |
| API 连接池 | `pool_size=10, max_overflow=10` | 见下方 12.9.1 的硬约束 |
| worker 进程 | 2 | 与 API 分开，文件解析与向量化不占 API |
| 每人并发运行 | ≤1 | 防止一个人占满连接与预算 |
| 预算默认值 | $50/月 · $10/日 · $2/次 | A-30；15 人上限 $750/月 |
| pgvector 索引 | HNSW `m=16, ef_construction=64` | 这个量级用默认值足够；**别忘 2000 维上限** |

### 12.9.1 硬约束：流式处理不得持有数据库会话

**这是一个必现的故障，不是理论风险。**

一次运行可持续数十秒到数分钟（多轮评审更久）。若 SSE 处理函数在整条流的生命周期内
持有一个数据库会话：

```
15 人同时运行  →  15 个 SSE 连接各持有一个 session 持续数分钟
默认池（5 + 10 overflow = 15）→ 第 16 个请求永久等待
```

**规定**：流式处理函数**不得在流的生命周期内持有数据库会话**。
需要写库时**短事务取用、用完立即归还**；`runs` 状态推进靠短事务，不用长事务包住整次运行。

这条要在 P1 实现连接池时写进注释 —— 否则接手的人一定会踩。

## 13. 与蓝图 1.0 的偏差汇总

| 偏差 | 内容 | 记录位置 |
|------|------|---------|
| D-1 | 代码任务支持写回与提 PR（蓝图推荐不做） | decisions.md D-1、本文 9.1 |
| D-2 | 预算上限无具体默认值 | decisions.md D-2 |
| D-3 | MAF 连接器降级为 `ProviderAdapter` 的可选实现，而非唯一接入路径 | 本文 2.3 |
| D-4 | `models` 等表补充中转站、路由、计量相关字段 | 本文第 10 节 |
| D-5 | 服务器区域定为**美国**（蓝图只要求"支持地区"） | 本文 12.7 |
| D-6 | 三个默认角色**分属三家厂商**（蓝图只要求 Reviewer 与 Worker 不同） | 本文 12.7 |
| D-7 | 界面**仅中文**，不做 i18n（蓝图未规定，但前端工作量为零成本项） | 本文 12.7 |
| D-8 | 沙箱**预置离线依赖缓存**（蓝图只说"限制网络"，没说怎么让任务能跑） | 本文 12.6 |
| D-9 | 默认三角色**明确到厂商**：Planner=Claude / Worker=GPT / Reviewer=Gemini | 本文 7.1A |
| D-10 | 按 6–15 人定连接池与并发参数，并新增「流式处理不得持有数据库会话」的硬约束 | 本文 12.9 |

### 12.7 第三轮确认（2026-10-14）

| 项 | 决定 | 影响 |
|----|------|------|
| 服务器区域 | **美国** | 三家厂商原生支持最完整、Azure OpenAI 可用性最好；代价是亚洲团队每次对话多 150–250ms |
| 默认角色模型分配 | **三角色分属三家**：Planner / Worker / Reviewer 各一家 | 天然满足"Reviewer 与 Worker 不同模型"，无需额外提示词，且顺带验证三家接入 |
| 界面语言 | **仅中文界面**，代码与标识符全英文 | 前端零额外工作量；文案集中管理以便将来加 i18n |
| 沙箱 | Python + Node + 多语言工具链 + **离线依赖缓存** | 见 12.6 |

### 12.1 MAF 已核实事实（2026-10-14）

来自公开包索引与微软官方升级指南。**未列为已核实的，一律当作不确定。**

| 项 | 结论 |
|----|------|
| PyPI 包名 | `agent-framework`（元包，拉全量）；`agent-framework-core`（精简核心） |
| 稳定版起始 | 1.0.0 于 **2026-04-02**，1.0.1 于 2026-04-10（与蓝图「2026 年 4 月发布 1.0」一致） |
| 当前版本 | 索引源互相矛盾：一处显示到 1.0.1，另一处显示 1.16–1.18。**安装时必须自己确认**，见下方命令 |
| Python 要求 | >= 3.10（本机 3.12.8 满足） |
| 厂商分包 | rc6 起按 provider 拆分：`agent-framework-openai`、`-foundry`、`-foundry-local` 等；`agent-framework-github-copilot` 要求 Python 3.11+ |
| 精简安装 | `agent-framework-core` 不含厂商连接器，**MCP 需手动添加**；省事就用 `agent-framework` 元包 |
| rc6 破坏性变更 | OpenAI 客户端更名；移除旧的 Azure/OpenAI 兼容层，改用 provider 原生客户端；Foundry 移到 `agent_framework.foundry` |
| rc5 破坏性变更 | 运行时参数拆成 `function_invocation_kwargs` 与 `client_kwargs`；工具改用 `FunctionInvocationContext` / `ctx.session` |

**P0 第一天必做**：在装依赖前先跑

```bash
uv pip index versions agent-framework
```

以实际返回为准，并把版本锁进 `pyproject.toml` 与 `uv.lock`。

**至此第 12 节开列的核实项已全部完成**，结论见 12.2–12.8。

### 12.2 检查点：已核实（重大，直接改变 P4 做法）

**结论：确认无官方 Postgres 实现，蓝图判断正确，P4 必须自研。** 但接口形状已明确：

- 检查点存储是**协议（protocol）**，内置 `InMemoryCheckpointStorage`、`FileCheckpointStorage`；
  另有 **Cosmos DB** 实现（`agent-framework-azure-cosmos`，预发布）。
- Cosmos 实现需满足 **6 个方法**，这就是自研 Postgres 实现要实现的接口：
  `save`、`load`、`list_checkpoints`、`delete`、`get_latest`、`list_checkpoint_ids`。
- 接入方式：把存储传给 builder，**每个 superstep 结束时自动写检查点**：

```python
workflow = WorkflowBuilder(
    start_executor=start,
    checkpoint_storage=checkpoint_storage,
).build()
latest = checkpoint_storage.get_latest(workflow_name=workflow.name)
await workflow.run(checkpoint_id=latest.checkpoint_id)   # 恢复
```

- **执行器必须自己声明要持久化的状态**（只存存储不够）：覆写 `on_checkpoint_save()` 返回 dict，
  `on_checkpoint_restore(state)` 读回。
- 检查点捕获四样东西：各执行器局部状态（`ctx.set_executor_state()`）、跨执行器共享状态
  （`ctx.set_state()`）、待处理消息队列、工作流位置。

#### 12.2.1 序列化是真正的坑（必读）

内置的 File / Cosmos / Foundry 检查点存储对 JSON 处理不了的类型**用 pickle**，
且**默认启用受限 unpickler**：只允许内置安全类型、框架类型、OpenAI SDK 类型；
**辅助函数与非类型全局对象一律拒绝**。

自定义类型必须注册，否则加载抛 `WorkflowCheckpointException`：

- 单实例：`allowed_checkpoint_types=["my_app.models:MyState"]`（`module:qualname` 格式）
- 进程级：`agent_framework.register_checkpoint_type(MyState)`
  —— 对**所有**后端生效，包括调用前已创建的存储实例。另有 `register_state_type`。

官方明确把检查点存储当作**信任边界**：存储必须是可信的私有基础设施，
**绝不可从不可信来源加载检查点**（pickle 有任意代码执行风险）。

**自研 Postgres 检查点的两条硬要求**：
1. 实现上述 6 个方法；事务性与并发写语义官方未定义，**必须自己定清楚并写测试**。
2. 状态用 JSON 优先；必须 pickle 的类型要显式注册，并确保反序列化只来自我们自己的库表。

### 12.3 人工确认（human-in-the-loop）

- 工具侧用**审批标记**声明：`approval_mode="always_require"` 一类（文档中 C# 为
  `@tool(approval_mode="always_require")`，Python 侧写法 P0 前确认）。
  这正好对应我们的 `write` / `destructive` 风险级别 —— **风险级别→审批标记的映射是机械的**。
- 已知限制（官方 issue）：审批响应目前**只带布尔值**，不能附带意见或修改后的参数；
  托管 Agent 形态下的人工审批存在问题。
  → 影响：我们的 `approvals` 表要**自己存**意见、修改后的参数、决定人（蓝图已如此设计，正确）。

### 12.4 OpenCodeReview：已核实（蓝图遗留问题解决）

蓝图中"它的输出格式我没有核对细节，P4 前要做一次小验证" —— **现已可确认可解析**：

| 项 | 结论 |
|----|------|
| npm 包名 | **`@alibaba-group/open-code-review`**（官方） |
| 安装 | `npm install -g @alibaba-group/open-code-review`，命令为 `ocr` |
| 依赖 | **Git ≥ 2.41**、**Node ≥ 18**、一个 LLM API 密钥 |
| 许可 | Apache 2.0 |
| **结构化输出** | **`ocr review --format json --audience agent`** —— 机器可读，专为 CI/agent 设计 |
| 常用命令 | `ocr review`（工作区改动）、`--from main --to <branch>`（分支范围）、`--commit <sha>`、`ocr scan`（全文件） |
| 预览 | `ocr review --preview` 不调模型，只看会审什么 |
| 模型配置 | 兼容 **OpenAI 与 Anthropic 风格**端点，支持本地模型 |
| 可调参数 | `--concurrency`、`--timeout`、`--background/-b`（业务上下文） |
| 规则 | `--rule <path>` → `<repo>/.opencodereview/rule.json` → `~/.opencodereview/rule.json` → 内置 |
| 可观测 | 内置 OpenTelemetry |
| 生态 | 可作 Claude Code 插件（`/plugin marketplace add alibaba/open-code-review`）、Codex 插件、技能 `npx skills add alibaba/open-code-review --skill open-code-review` |

**对我们的三点意义**：
1. `--format json --audience agent` 让"适配器把工具输出转成统一评审结论"有了稳定输入，
   P4 的 `CliToolExecutor` 风险大幅下降。
2. `--preview` 可在不花钱的前提下做连通性验证 → **P0/P2 就能提前验证**，不必等到 P4。
3. 它支持 OpenAI 与 Anthropic 风格端点 → 可指向我们的**中转条目**，与其他调用共用预算与审计。
   注意它自己调模型，用量要纳入预算（蓝图已提示）。

### 12.5 嵌入模型与中文检索：已核实

**OpenAI 仍是 2024 年 1 月那三个模型，无换代**（价格两年未变）：

| 模型 | 默认维度 | 可截断至 | 最大输入 | 单价 / 1M token |
|------|---------|---------|---------|----------------|
| `text-embedding-3-large` | 3072 | 256 | 8191 | **$0.13** |
| `text-embedding-3-small` | 1536 | 256 | 8191 | **$0.02** |
| `text-embedding-ada-002`（旧） | 1536 固定 | — | 8191 | $0.10 |

两个 v3 模型用 Matryoshka 表示学习训练，**可截断维度且质量损失远小于 PCA**：
官方数据是 3-large 截到 256 维仍优于 ada-002 的 1536 维。

#### 12.5.1 pgvector 的维度上限是硬约束（重要）

**pgvector 的 HNSW 与 IVFFlat 索引：`vector` 最多 2000 维，`halfvec` 最多 4000 维。**

→ **`text-embedding-3-large` 的 3072 维默认值无法作为普通 `vector` 列建索引。**
必须二选一：用 `halfvec` 列，或通过 `dimensions` 参数截断。

单向量存储开销 `4 * 维度 + 8` 字节。1536 维、100 万向量的索引约 6 GB（FP32）。

**本项目选型建议**（你三家都有、内容以中文为主）：

| 方案 | 维度 | 优点 | 缺点 |
|------|------|------|------|
| **`text-embedding-3-small`（1536）** | 1536 | 便宜（$0.02）、可直接建 HNSW 索引、无需 halfvec | 中文质量中等 |
| `text-embedding-3-large` + `halfvec` | 3072 | 质量最好 | 需 halfvec；成本 6.5 倍；运维复杂一点 |
| `text-embedding-3-large` 截断 1024 | 1024 | 质量与成本折中，可普通索引 | 需先跑评测集确认损失 |
| 多语言开源模型自托管（BGE-M3 / Qwen3-Embedding 一类） | 视模型 | 中文可能更好、数据不出境 | 需自托管 GPU；与"单台服务器"冲突 |

**建议**：先固定 `text-embedding-3-small`（1536 维），把接口与"分块记录嵌入模型名"做好
（蓝图已要求），等 P3 评测集出来再决定是否换。**换模型必须重建全部索引，所以别提前优化。**

#### 12.5.2 中文全文检索

Postgres 原生全文检索对中文**需要额外扩展**（默认分词器不切中文）。可选方案与状态：

| 方案 | 状态 | 备注 |
|------|------|------|
| **pg_bigm** | 有实测可用报告 | 二元分词，中文召回尚可，安装相对简单 |
| zhparser / pg_jieba | 需编译 SCWS 等分词引擎 | 分词质量好，但部署麻烦，多用于发行版镜像 |
| pgroonga | 部分环境需**外部 PostgreSQL** | 功能强（支持 CJK），但部署约束多 |

**建议维持蓝图决定**：第一版**纯向量检索**，P3 起用评测集看效果，
再决定是否加 pg_bigm 做混合检索（向量 + 关键词用 RRF 融合）。
纯向量对**专有名词、编号**的召回确实差（蓝图第 12 节第 8 项已点名），
所以**评测集里必须包含专有名词与编号类问题**，否则测不出这个短板。

### 12.6 代码沙箱（用户 2026-10-14 确认）

| 项 | 决定 |
|----|------|
| 基础工具链 | **Python 3.11+ 与 Node 20+**、git、ripgrep 等 |
| 多语言 | **额外装编译型语言工具链**（Java / Go / Rust 一类） |
| 离线依赖 | **预置 pip/npm 离线镜像与包缓存** ← 关键 |

**为什么离线缓存是关键**：沙箱**默认不开放外网**（蓝图第 9 节），
若不预置依赖，沙箱内 `pip install` / `npm install` 一律失败，
代码任务只能跑纯标准库脚本 —— 等于这个功能白做。

**落地要求**：
- 自建沙箱基础镜像，预置常用包缓存，版本固定；
- 镜像本身随项目版本管理，CI 里构建与扫描；
- 成员若需额外包，走"申请→加进镜像"的流程，**不允许沙箱临时联网装**；
- 镜像体积要控制（多语言工具链会显著变大），必要时拆成多个镜像按任务类型选择。

### 12.8 其余四项 MAF 事实：已核实

#### 12.8.1 OpenTelemetry：内置，无独立包

框架**自带 OTel 埋点**，不需要额外 instrumentation 包。每次 `agent.run()` 产生
`invoke_agent` / `chat` / `execute_tool` 三种 span，遵循 GenAI 语义约定。

两种开启方式：

- `configure_otel_providers(...)`（`agent_framework.observability`）—— 推荐，
  一行搞定 tracer/meter/logger provider 与 OTLP exporter，读标准 `OTEL_*` 环境变量。
- `enable_instrumentation(enable_sensitive_data=True)` —— 自己提供全局 tracer provider 时用。

```python
from agent_framework.observability import configure_otel_providers
configure_otel_providers(enable_sensitive_data=True)   # 必须在首次 agent 运行前
```

环境变量：`OTEL_SERVICE_NAME`、`OTEL_EXPORTER_OTLP_ENDPOINT`、
`OTEL_EXPORTER_OTLP_HEADERS`、`OTEL_EXPORTER_OTLP_PROTOCOL`、`ENABLE_SENSITIVE_DATA`。

**四个必须知道的坑**：

1. **协议默认 gRPC**。不设 `OTEL_EXPORTER_OTLP_PROTOCOL` 且没装 gRPC exporter，
   会抛 `ImportError`。我们打算用 OTLP/HTTP，所以**必须显式设置该变量**。
2. **provider 只在创建时读一次环境变量**。所以 `load_dotenv()` 必须**在**
   `configure_otel_providers()` **之前**调用，否则 span 会落到默认服务名上。
   这与蓝图提醒的"MAF 不会自动读 `.env`"是同一类问题，且更隐蔽。
3. **`enable_sensitive_data=True` 会把 prompt、system 指令、工具定义与参数写进 span。**
   → **与蓝图第 8 节"日志必须脱敏"直接冲突。** 生产环境默认必须关闭；
   开发环境可开，但不得指向会长期留存的外部后端。这一条要写进 `backend/AGENTS.md` 的禁止事项。
4. **token 会重复计数**：`invoke_agent` span 重复了子 `chat` span 的累计值。
   统计 token 与费用时**必须只在 `gen_ai.operation.name = 'chat'` 上求和**，
   否则我们的 `usage_logs` 会翻倍。这条直接影响成本控制的准确性。

另一个有用事实：失败的工具只把 `execute_tool` span 标为错误，agent 会自行恢复，
`invoke_agent` 仍是干净的；而**模型调用失败会向上传播**。

#### 12.8.2 YAML 声明式工作流：稳定，但有一个针对我们的严重问题

**好消息**：包 `agent-framework-declarative`（Python）已达 **1.0.0 稳定**。
声明式工作流**加载成与代码优先写法相同的 `Workflow` 类型** —— 运行、流式、检查点、
组合行为完全一致。这对 P5 的"导入导出"是重大利好：导出格式可以就用它，
不必自己设计一套。

```python
from agent_framework.declarative import WorkflowFactory
workflow = WorkflowFactory().create_workflow_from_yaml_path("support_router.yaml")
```

注意：**单 agent 的 `AgentFactory`（`create_agent_from_yaml`）仍是 experimental**，
只有工作流那部分是稳定的。

**三个坑**：

1. **表达式依赖 .NET 运行时**。`=` 前缀的表达式（Power Fx）由 C# 实现经 pythonnet 桥接。
   我们若用含表达式的 YAML，就**必须装 .NET 运行时** —— 对一个纯 Python 部署是意外负担。
   不用表达式可绕开，但那样只能做演示级流程。
2. **YAML 不跨语言可移植**（C# 用 `System.LastMessage` 而非 `Workflow.Inputs`），
   部分会话操作 action 是 C# 独有。我们只用 Python，影响有限，但导出文件不要声称通用。
3. **⚠️ 安全：YAML 里有副作用 action，且能绕过我们的权限模型。**

   动作目录里的 `HttpRequestAction`、`InvokeMcpTool`、`InvokeFunctionTool`、`GotoAction`
   **都有副作用**。这意味着：**任何能编辑配置区 YAML 的成员，都能让工作流发起 HTTP 请求
   或调用工具 —— 即使他的角色配置里没有这些工具。**

   这**直接违反**蓝图与 `design.md` 7.4 规则的核心："配置只决定'用什么、怎么分工'，
   **不授予额外权限**"。这是一个真实的越权路径，不是理论风险。

   **必须的缓解措施**（写进 P5 的发布前校验）：
   - YAML 导入与发布时做 **action 白名单校验**：`HttpRequestAction`、`InvokeMcpTool`、
     `InvokeFunctionTool`、`GotoAction` 一律**禁止出现在用户可编辑的配置里**，
     或至少强制要求它们引用的工具**必须同时存在于运行者的可用工具集**内；
   - 导入的 YAML 视为**代码**而非配置，走比配置更严的审查；
   - 参照社区做法：CI/发布校验器在"有副作用 action 却其前序分支上没有
     `Question` / `RequestExternalInput` 审批门"时**直接拒绝发布**。

   修正后的立场：**导出可以用 MAF 的 YAML 格式，导入必须过白名单校验后才能执行。**

#### 12.8.3 Skills：核心 API 已从实验性转为稳定（前提变化）

**MAF 的核心 Skills API 已正式转为稳定**（Python PR #6974 移除了全部 15 个
Skills API 上的 `@experimental` 装饰器并删除了 `ExperimentalFeature.SKILLS`；
.NET 侧 PR #6861 同步）。**仍然实验性的是 MCP-based skills**
（`MCPSkill` / `MCPSkillResource` / `MCPSkillsSource`，另一套 `MCP_SKILLS` 开关）。

**这改变了本项目的一个已定决策**（A-21 的理由"Skills 是预览功能"已不成立）。
详见第 14 节。

**机制**：一个 skill 是一个目录，主文件 `SKILL.md`：

- YAML front matter：必需 `name`（小写字母数字连字符，≤64 字符）与
  `description`（单行，≤1024 字符）；
- 之后的 Markdown 正文即被注入的指令；
- 每个 skill 在自己的子目录里（`greeting/SKILL.md`，不是根目录一个 `SKILL.md`）。

**渐进式加载**：agent 先只看到名称与简短描述；请求匹配时调 `load_skill` 取完整指令，
`read_skill_resource` 取参考资料，`run_skill_script` 执行附带脚本。

**关键发现 —— 默认要求人工审批**：`load_skill`、`read_skill_resource`、`run_skill_script`
**默认都需要人工批准**。可信 skill 可以关掉"加载与读取"的审批，但
**这不等于允许自动执行脚本**（脚本执行永远要批）。

→ 这与我们的审批模型天然契合，但也意味着**开箱即用体验会很啰嗦**
（每次加载技能都弹确认）。建议：把"加载与读取"对**管理员发布的官方技能**默认关闭审批，
对**成员自建技能**保留审批；脚本执行一律保留审批。

**三个可插拔抽象**：`SkillsProvider`、`SkillsSource`、`SkillScriptRunner`
（另有 `CachingSkillsSource`、`SkillsSourceContext`、`SkillFrontmatter`、`SkillResource`、`SkillScript`）。
三种编写方式：文件式、类式（可打包分发）、代码定义式。

→ **`SkillsSource` 是数据库化技能的正确挂载点**：实现一个 `DbSkillsSource`
就能让技能存数据库、可分享、可版本管理，而运行时仍用 MAF 稳定的 Skills API。
见第 14 节。

#### 12.8.4 自定义 base_url / 中转站：官方支持，已确认

**确认支持**，无需自己写 provider。`base_url` 参数是专门为"兼容 OpenAI 的第三方 API"
加的（PR #661，涉及 `OpenAIConfigMixin` 与 `OpenAIChatClient`），
也读 `OPENAI_BASE_URL` 环境变量。

**包 `agent-framework-openai` 提供三个客户端，都接受 `base_url` 与 `api_key`**：

| 客户端 | 端点 | 用于 |
|--------|------|------|
| `OpenAIChatCompletionClient` | `/chat/completions` | **中转站首选**，见下 |
| `OpenAIChatClient` | `/responses`（Responses API） | 官方新项目默认，但中转常不支持 |
| `OpenAIEmbeddingClient` | `/embeddings` | 嵌入 |

**⚠️ 对我们最关键的一条**：`OpenAIChatClient`（Responses API）是官方推荐的一般用途客户端，
但**大量中转站与自建网关只提供 Chat Completions、不提供 Responses**。
→ **我们的 `openai_compat` 适配器必须默认用 `OpenAIChatCompletionClient`**，
而不是官方推荐的 `OpenAIChatClient`。这一条直接决定中转站能不能用。

**其他必须注意的**：

- **`base_url` 必须以 `/v1` 结尾且不带尾部斜杠**（多个厂商文档都强调）。
- **Azure 与 OpenAI 环境变量同时存在时**，通用客户端**优先 OpenAI**（若设了 `OPENAI_API_KEY`）。
  要强制走 Azure，必须显式传 `azure_endpoint` 或 `credential`。
  → 我们多条目并存，**绝不能依赖环境变量推断，一切条目参数显式传入**。
- **不自动读 `.env`**，需自己 `load_dotenv()` 或显式传参（蓝图已提醒，此处再次确认）。
- 可传入自定义 `async_client`，便于做批量或代理注入。
- **Responses 专属的工具与厂商特性未必能映射到上游**。接新中转条目时，
  必须先验证**流式与工具调用**是否真的可用 —— 这正是 A-17（能力标记可手动覆盖）
  与"运行前校验"存在的原因。

---

## 14. 需要你重新确认的决策（因外部事实变化）

### 14.1 A-21 的前提不成立了：MAF Skills 已稳定

**你之前批准的 A-21 是"自研 `SkillLoader` 接口 + MAF Skills 作可选实现"，
理由写的是"MAF Skills 仍是预览功能"。这个理由现在被推翻了**
——核实发现核心 Skills API 已转为稳定（12.8.3），只有 MCP-based skills 仍是实验性。

所以在"自研"与"用 MAF"之间，前提已经变了，需要你重新拍板：

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **甲（原 A-21）** | 完全自研 `SkillLoader` / `SkillRegistry` | 完全自主，无框架依赖 | 重复实现 MAF 已稳定的东西；渐进式加载、资源读取、脚本执行都要自己写 |
| **乙（新建议）** | **运行时用 MAF 稳定的 Skills API，自研 `DbSkillsSource` 实现 `SkillsSource` 接口** | 技能存数据库、可分享、可版本管理（我们的需求）**由 `DbSkillsSource` 满足**；加载/资源/脚本机制直接复用，且自带默认人工审批 | 需要遵循 MAF 的 `SKILL.md` 目录约定与 frontmatter 结构 |
| 丙 | 甲 + 乙 都做，用配置切换 | 最灵活 | 两套都要维护，第一版明显过度设计 |

**我的建议：改为方案乙。** 你的三项要求（可配置、可分享、可版本管理）
本质是**存储与权限**问题，正好由 `DbSkillsSource` 这一个接口实现解决；
而**运行时行为**（渐进式加载、资源读取、脚本执行与审批）没必要自己重写。
这比原 A-21 工作量更小、行为更可靠。

**若采纳，需要配套调整**：
- `SKILL.md` 的 frontmatter 成为我们的技能格式（`name` ≤64、`description` ≤1024），
  不再自定义一套字段；
- 审批策略按来源分级：官方技能默认关闭"加载/读取"审批，成员自建技能保留；
  **脚本执行一律保留审批**；
- 数据库里存 `SKILL.md` 正文与资源，由 `DbSkillsSource` 装配成 MAF 需要的目录形态。

### 14.2 YAML 导入的越权风险需要你知晓

12.8.2 末发现：MAF 的 YAML 动作目录里 `HttpRequestAction`、`InvokeMcpTool`、
`InvokeFunctionTool`、`GotoAction` **都有副作用**。若 P5 允许成员编辑或导入 YAML，
他们将**绕过"配置不授予权限"这条规则**，让工作流调用其角色本无权使用的工具或发外部请求。

这是设计层面的真实越权路径。我在 `design.md` 12.8.2 已写明缓解措施
（导入走 action 白名单校验、YAML 视为代码而非配置、无审批门的有副作用 action 拒绝发布），
**不需要你现在决策，但你需要知道这条约束会限制 P5 的"导入"功能开放程度**。
