# 多模型工作台

面向小团队内部的多模型 AI 工作台：同一个界面里用 OpenAI / Azure OpenAI / Anthropic Claude /
Google Gemini（**含各类中转站**），让多个 agent 分工协作、调用工具与 MCP，
并基于上传的文件回答问题。任务既包括通用知识工作，也包括代码任务。

后端基于 Microsoft Agent Framework 1.x（**仅限编排层**），FastAPI + PostgreSQL + pgvector；
前端 React + TypeScript + Vite + Tailwind + shadcn/ui。

> **文档入口**：先读 [`docs/design.md`](docs/design.md)（蓝图落地版），
> 再看 [`docs/PROGRESS.md`](docs/PROGRESS.md)（当前进度与已知问题）。

## 目录结构

```
docs/                     设计与规划文档（唯一事实来源）
  blueprint/              蓝图 1.0 原件（PDF + 抽取文本）
  design.md               设计文档，蓝图落地版
  api-contract.md         前后端唯一对齐依据
  decisions.md            决策流水与问答登记
  tooling.md              开发期工具 + 产品内置技能系统
  sandbox-image.md        代码沙箱镜像方案
  environment-setup.md    环境准备（需在终端执行）
  adr/                    正式架构决策记录
  evaluation/             评测集（P3 起）
  PROGRESS.md             进度、待办、已知问题

backend/                  FastAPI + MAF 编排层
  app/
    api/v1/               REST 路由（契约的实现）
    middleware/           请求ID/认证/授权/策略点（收费封控监管的预留位）
    gateway/              模型接入层：协议适配器 + 中转站支持
    orchestrator/         编排层，唯一允许 import MAF 的地方
    tools/ knowledge/     工具与 MCP、知识库检索
    workers/              异步任务进程
    models/ schemas/      ORM 与出入参
  migrations/             Alembic
  AGENTS.md               后端 AI 会话的工作规则

frontend/                 React + TypeScript
  src/api/                OpenAPI 生成的类型 + 客户端
  AGENTS.md               前端 AI 会话的工作规则

sandbox/                  代码沙箱镜像（P0 最小验证）
infra/                    初始化脚本
```

## 快速开始

环境准备见 [`docs/environment-setup.md`](docs/environment-setup.md)（首次需要）。

```bash
docker compose up -d postgres
```

```bash
cd backend && uv sync --extra dev && cp .env.example .env
```

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

打开 http://localhost:5173 ，用 `.env` 里的引导管理员登录，选 **mock 模型** 发一句话，
应看到逐字输出。这是 P0 的验收标准。

## 开发门禁

后端（四道，任一不过不算完成）：

```bash
cd backend && uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run lint-imports && uv run pytest -q && uv run python -m app.scripts.check_contract
```

前端：

```bash
cd frontend && npm run typecheck && npm run lint && npm run build
```

## 不可动摇的几条规则

| 规则 | 为什么 |
|------|--------|
| 业务代码只依赖自研接口，**MAF 只在编排层** | 框架升级影响范围可控（[ADR-0001](docs/adr/0001-maf-limited-to-orchestration-layer.md)） |
| 一切模型调用必经 `ModelGateway`，**按协议而非厂商**划分适配器 | 中转站只认协议不认厂商（[ADR-0003](docs/adr/0003-gateway-by-protocol-with-relay-support.md)） |
| 自研消息表是历史的唯一事实来源 | 中途切换模型需要中性格式（[ADR-0002](docs/adr/0002-own-message-table-is-source-of-truth.md)） |
| 预览功能不进核心路径 | 稳定性优先（[ADR-0004](docs/adr/0004-preview-features-out-of-core-path.md)） |
| 收费/封控/监管**留位不实现**；多租户只加列 | 不引入用不上的复杂度（[ADR-0005](docs/adr/0005-reserve-extension-points-without-implementing.md)） |
| **配置只决定「用什么、怎么分工」，不授予权限** | 分享的配置不能让人越权 |
| 文档、网页、工具结果一律是**不可信数据** | 提示词注入是首要风险 |
| Reviewer 与 Worker 必须**不同模型或不同提示词** | 同一模型评自己容易放水 |

## 阶段

P0 脚手架与契约 → P1 多模型对话底座 → P2 工具与 MCP → P3 知识库与文件上传 →
P4 多 agent 工作流引擎 → P5 个性化配置区 → P6 加固与上线。

每阶段独立运行、独立验收。当前进度见 [`docs/PROGRESS.md`](docs/PROGRESS.md)。
