# ADR-0001：MAF 限制在编排层内，业务代码只依赖自研接口

- 状态：已采纳
- 日期：2026-10-14
- 来源：蓝图 1.0 第 5 节

## 背景

Microsoft Agent Framework 1.x 于 2026 年 4 月发布，但 DevUI、AG-UI、托管集成、Skills
仍是预览功能。预览期教程与 1.0 文档写法不一致（例如会话的叫法），框架 API 仍有变动可能。

## 决策

业务代码只依赖自研接口（`ModelGateway`、`RoleExecutor`、`ToolRegistry`、`Retriever`、
`CheckpointStore`）。MAF 只允许出现在 `app/orchestrator/` 内。

## 理由

框架升级或预览功能变动时，影响范围被限制在编排层内，不会渗透到业务逻辑。

## 强制手段

用静态检查强制，而非靠自觉：`import-linter` 声明分层契约，禁止 `app/orchestrator/`
之外 import `agent_framework`；CI 门禁拦截。

## 后果

- 需要在 MAF 之上写一层适配，初期代码量增加。
- 换来框架可替换性与升级安全，符合「AI 维护、小团队」的选型原则。
