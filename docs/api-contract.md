# 接口契约 · api-contract.md

> **前后端唯一对齐依据。** 后端改，前端只读。
> 本文件与 `backend` 导出的 OpenAPI 必须一致，由门禁脚本强制校验。
> 本文件目前是**草案**，P0 阶段由后端会话细化并补齐 schema。

最后更新：2026-10-14

## 1. 通用约定

| 项 | 约定 |
|----|------|
| 路径前缀 | 全部以 `/api/v1` 开头 |
| 字段命名 | `snake_case` |
| 时间 | UTC，ISO 8601（例：`2026-10-14T03:00:00Z`） |
| ID | UUID |
| 列表 | 游标分页，`?cursor=&limit=`，返回 `{items, next_cursor}` |
| 认证 | 服务端会话 Cookie（HttpOnly、SameSite） |
| 内容类型 | 除上传外均 `application/json`；事件流 `text/event-stream` |
| 幂等 | `POST /runs` 需带 `Idempotency-Key` 头，防止重复扣费 |

## 2. 错误格式

统一为：

```json
{ "error": { "code": "budget_exceeded", "message": "本月预算已用完", "request_id": "uuid" } }
```

错误码是**封闭集合**，前端必须为每个码准备人话提示：

| code | HTTP | 含义 |
|------|------|------|
| `unauthorized` | 401 | 未登录或会话过期 |
| `forbidden` | 403 | 已登录但无权访问该对象 |
| `not_found` | 404 | 对象不存在（含无权查看时的伪装） |
| `validation_failed` | 422 | 参数校验失败 |
| `model_unavailable` | 502 | 模型或中转站不可用（含鉴权失败） |
| `rate_limited` | 429 | 限流 |
| `budget_exceeded` | 402 | 超出预算或配额 |
| `run_conflict` | 409 | 同一运行状态冲突（如对已完成运行发取消） |
| `tool_denied` | 403 | 工具调用被拒绝或不在白名单 |
| `internal_error` | 500 | 未预期错误 |

## 2A. 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 存活探针，无需登录。返回 `{"status": "ok"}` |

## 3. 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/login` | 登录，设置会话 Cookie |
| POST | `/auth/logout` | 退出 |
| GET | `/auth/me` | 当前用户与角色 |

角色只有两个：`admin`、`member`。管理员邀请制，无公开注册。

## 4. 模型

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/models` | 可用模型及能力标记（流式、工具调用、图片、上下文长度、单价） |
| POST | `/admin/models` | 管理员新增/修改模型条目，**含 base_url 与协议类型** |
| POST | `/admin/models/{id}/test` | 连通性测试（中转站尤其需要） |

**能力标记必须由管理员可覆盖**：中转站实际支持的能力常少于官方，不能只靠自动探测。

## 5. 会话与消息

| 方法 | 路径 | 说明 |
|------|------|------|
| GET / POST | `/conversations` | 列表 / 新建 |
| GET / PATCH / DELETE | `/conversations/{id}` | 详情 / 改名 / 删除 |
| GET | `/conversations/{id}/messages` | 历史消息（游标分页） |

会话默认**私有**（仅创建者可见）；管理员可查看全部。

## 6. 运行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/conversations/{id}/runs` | 启动一次运行，以 SSE 返回事件 |
| GET | `/runs/{id}` | 运行详情（状态、起止、已用预算） |
| GET | `/runs/{id}/events?after=序号` | 断线后续传事件 |
| POST | `/runs/{id}/cancel` | 取消运行 |
| POST | `/runs/{id}/approvals/{request_id}` | 对工具调用或计划做「同意 / 拒绝」 |

运行状态：`queued`、`running`、`waiting_approval`、`succeeded`、`failed`、`cancelled`。

## 7. Agent 与编排

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/agents` | agent 管理 |
| CRUD | `/workflows` | 编排配置 |

## 8. 工具与 MCP

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tools` | 工具列表（含风险级别） |
| CRUD | `/mcp-servers` | MCP 配置（地址、加密凭据、工具白名单） |
| POST | `/mcp-servers/{id}/test` | 连通性测试 |

风险级别：`read_only`、`write`、`destructive`。`write` 与 `destructive` 默认需人工确认。

## 9. 知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/knowledge-bases` | 知识库（可设团队共享） |
| POST | `/knowledge-bases/{id}/documents` | 上传（multipart） |
| GET / DELETE | `/knowledge-bases/{id}/documents/{doc_id}` | 文件状态 / 删除 |

文件状态：`queued`、`processing`、`ready`、`failed`。
检索按**运行者**权限过滤，分享的配置不能越权。

## 10. 用量与管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/usage` | 按时间、用户、模型查询用量与费用 |
| GET / POST | `/admin/users` | 邀请、禁用成员 |

> 预留（第一版不实现，接口位置先占）：`/admin/policies`、`/admin/billing`、`/admin/audit`。

## 11. 配置区（/studio/*）

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/studio/roles` | 角色库 |
| CRUD | `/studio/workflows` | 分工草稿 |
| POST | `/studio/workflows/{id}/publish` | 发布新版本 |
| GET | `/studio/workflows/{id}/versions` | 版本列表 |
| POST | `/studio/workflows/{id}/rollback` | 回滚 |
| POST | `/studio/workflows/{id}/test-runs` | 试运行，以 SSE 返回事件（`is_test` 标记） |
| GET | `/studio/workflows/{id}/export` | 导出 |
| POST | `/studio/import` | 导入 |
| GET / POST | `/studio/workflows/{id}/shares` | 分享（默认只读） |

发布前校验：孤立节点、循环是否设最大轮数、引用的模型/工具/知识库是否可用、是否设预算上限。

## 12. SSE 事件

每个事件带**递增序号**，前端据此断线重连；统一信封：

```
event: message.delta
id: 42
data: {"run_id":"...","message_id":"...","seq":42,"ts":"2026-10-14T03:00:00Z","payload":{...}}
```

| 事件 | 含义 | 主要字段 |
|------|------|---------|
| `run.started` | 运行开始 | `run_id`、编排模板 |
| `plan.created` | Planner 产出计划 | 步骤列表、验收标准 |
| `step.started` / `step.completed` | 某一步开始或结束 | `step_id`、角色、执行器 |
| `message.delta` | 文本片段 | `message_id`、`text` |
| `message.completed` | 一条消息结束 | `message_id` |
| `tool.call.started` / `tool.call.completed` | 工具调用 | 工具名、参数摘要、结果摘要 |
| `approval.requested` | 需要人工确认 | `request_id`、工具、参数、风险级别 |
| `review.result` | Reviewer 评审结论 | 结论、问题清单（严重程度、位置、说明、建议） |
| `citations` | 引用来源 | 文件、位置、片段 |
| `usage` | 用量 | token、费用 |
| `run.failed` / `run.completed` | 结束 | 状态、错误码 |

## 13. 契约变更流程

1. 后端改本文件 → 2. 后端起实现并导出 OpenAPI → 3. 门禁比对两者一致 →
4. 前端重新生成类型 → 5. 前端改实现。**任一步不合规，视为任务未完成。**
