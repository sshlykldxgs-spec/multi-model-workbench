# 技能与插件候选清单（**尚未安装**）

> 对应你的要求：先调研、列清单、标明来源与版本，**征得你同意后再装**。
> 覆盖你要的五类：代码审查、测试与验证、框架设计、TDD、子智能体协作。
>
> **调研日期：2026-10-14。** 软件生态变化快，装之前应再核一次版本。
> **优先级规则**：官方（Anthropic 维护）> 官方市场收录 > 知名社区项目。

---

## 一、先弄清两套东西（否则容易装错）

| 名称 | 是什么 | 关系 |
|------|--------|------|
| **Skill（技能）** | 一个目录 + `SKILL.md`（YAML frontmatter + Markdown）。模型根据 `description` **自行判断**是否加载 | 隐式触发，不占常驻上下文（只扫描 name 与 description） |
| **Plugin（插件）** | 打包：命令 + 子智能体 + 技能 + hooks + MCP 服务器 | 一个 plugin 可以内含多个 skill |
| **Marketplace（市场）** | 一个 Git 仓库，含 `.claude-plugin/marketplace.json` | 插件从市场装 |

**三个官方市场**（装之前要分清，很容易加错）：

| 市场 | 仓库 | `@` 后写的名字 |
|------|------|--------------|
| 官方 | `anthropics/claude-plugins-official` | `claude-plugins-official` |
| 社区 | `anthropics/claude-plugins-community` | `claude-community` |
| 示例 | `anthropics/claude-code` | `claude-code-plugins` |

⚠️ **常见错误**：`/plugin marketplace add anthropics/claude-code` 加的是**示例**市场，不是官方市场。
`code-review`、`feature-dev`、`commit-commands` 等在两处同名，会重复。
**一律从 `claude-plugins-official` 装。**

---

## 二、按你点名的五类，逐项给候选

### 1. 代码审查

| 候选 | 来源 | 说明 | 建议 |
|------|------|------|------|
| **内置 `/code-review`** | Claude Code 自带 | 直接审当前 diff / PR / 分支 / 路径，支持 `low\|medium\|high\|xhigh\|max` 分档、`--fix` 应用修复、`--comment` 发到 GitHub/GitLab | **已可用，无需安装** |
| `code-review` 插件 | `anthropics/claude-code`（官方示例） | 并行起 5 个 Sonnet 子智能体，各持不同视角（CLAUDE.md 规范、bug、git 历史、PR 历史、代码注释），再按置信度过滤假阳性 | 与你现有内置命令**功能重叠**，非必要 |
| `/security-review` | 内置 | 安全审查 | **已可用**，本项目提示词注入风险高，建议常用 |
| **OpenCodeReview** | 阿里 `alibaba/open-code-review`，Apache-2.0 | 命令行 AI 代码审查。`ocr review --format json --audience agent` 有机器可读输出。**你的产品 P4 本来就要接它** | **开发期就该先用一遍**，等于提前替 P4 验证。见下方第三节 |

### 2. 测试与验证

| 候选 | 来源 | 说明 | 建议 |
|------|------|------|------|
| `webapp-testing` | **官方** `anthropics/skills` | 基于 Playwright 的 UI 测试与调试 | **推荐**。你的前端需要它 |
| `playwright`（官方 OpenAI skills 也有同名） | 官方 | 浏览器自动化 | 与上面重叠，二选一 |
| 内置 Browser 工具 | 本环境已有 | 起 dev server、看页面、读控制台 | **已可用，优先用** |
| `e2e/` 自建 | 本项目 | 已写 `frontend/e2e/smoke.spec.ts` | 你的门禁已含烟雾测试 |

### 3. 框架设计

| 候选 | 来源 | 说明 | 建议 |
|------|------|------|------|
| `feature-dev` | 官方市场 `claude-plugins-official` | 7 阶段结构化开发流程（spec → plan → implement → test），带三个子智能体：`code-explorer`、`code-architect`、`code-reviewer` | **推荐**。`code-architect` 正对"框架设计" |
| `mcp-builder` | 官方 `anthropics/skills` | 构建 MCP 服务器（Python/FastMCP 或 Node/TS SDK） | **P2 要用**，你的产品要接 MCP。可提前装 |
| `skill-creator` | 官方 `anthropics/skills` | 写/改/评测技能 | 你要做产品内置技能系统（`DbSkillsSource`），值得参考其结构 |
| `frontend-design` | 官方 `anthropics/skills` | 避免模板化 UI | **已在本会话可用** |

### 4. TDD

| 候选 | 来源 | 说明 | 建议 |
|------|------|------|------|
| **Superpowers**（obra/superpowers） | 社区，MIT，已收录进官方市场 | 一整套方法论：头脑风暴 → worktree → 写计划 → **子智能体执行** → **严格 RED-GREEN-REFACTOR** → 任务间代码审查 → 收尾。作者称可自主工作数小时 | **与你需求最贴的一个**，见下方风险 |
| `tdd` | 社区 `glebis/claude-skills` | 单点 TDD 技能 | 功能被 Superpowers 覆盖 |
| 本项目自建 | — | `backend/tests/`、`frontend/e2e/` 已建，门禁已含 pytest | 已有基础 |

### 5. 子智能体协作

| 候选 | 来源 | 说明 | 建议 |
|------|------|------|------|
| **内置子智能体机制** | Claude Code 自带 | Agent 工具、`/batch`（拆成 5–30 个 worktree 隔离的子智能体）、worktree、跨会话消息、agent teams | **已可用** |
| Superpowers 的 `subagent-driven-development` | 社区 | 每个任务派**全新子智能体**保持上下文干净，两阶段审查（先规格符合、再代码质量） | 与上面同源 |
| `agents-swarm-orchestration` 一类 | 社区 | 主从契约、文件所有权、接口冻结 | 原则可借鉴，不必装 |

---

## 三、我的推荐（分三档）

### 第一档 · 强烈建议（成本低、直接对应你的需求）

| 项 | 类型 | 理由 |
|----|------|------|
| 内置 `/code-review`、`/security-review`、`/simplify` | 内置 | **零安装成本**，本会话已可用 |
| `/plugin marketplace add anthropics/skills` → `webapp-testing` | 官方 skill | 前端验证的唯一可靠手段 |
| `feature-dev` @ `claude-plugins-official` | 官方插件 | 含 `code-architect` 子智能体，对"框架设计" |
| OpenCodeReview（`ocr`） | 阿里开源 | 开发期用它 = 提前替 P4 做验证 |
| `mcp-builder` @ `anthropics/skills` | 官方 skill | P2 直接要用 |

### 第二档 · 建议装，但要你知情

| 项 | 类型 | 风险 |
|----|------|------|
| **Superpowers** | 社区（已收录官方市场） | 它**强推自己的方法论**（强制 TDD、强制 worktree、计划文档放 `docs/superpowers/specs/`），会与你已定的流程（蓝图第 10 节 + `AGENTS.md`）**部分冲突**。它的技能会覆盖默认行为，但**你的 `AGENTS.md` 优先级更高**。建议：先只装它，**不要**同时装其它同类方法论 |

### 第三档 · 暂不建议

| 项 | 理由 |
|----|------|
| 各类"必装清单"聚合包 | 多为内容营销，来源与版本不可核，且会引入大量用不上的技能 |
| 同类重复的 TDD / orchestration 技能 | 互相冲突，模型选择困难 |
| Codex 侧的 Skill 包 | 你问的是两侧，但 Codex 的 skill 与 Claude 的 skill **格式与加载机制不同**，不能混用（见第四节） |

---

## 四、关于 Codex 侧（你单独问的部分）

**关键结论：Claude 的 skill 与 Codex 的 skill 不能互换。**

| | Claude Code | OpenAI Codex |
|---|---|---|
| 格式 | `SKILL.md`（YAML frontmatter + Markdown） | 同为 `SKILL.md` 约定，但**加载与发现机制不同** |
| 官方仓库 | `anthropics/skills` | `openai/skills` —— **已标记弃用**，转向 Plugins 仓库 |
| 组织方式 | 市场 `.claude-plugin/marketplace.json` | `.system` / `.curated` / `.experimental` 三档 |
| 安装 | `/plugin install <名>@<市场>` | `$skill-installer <名>`，装完需**重启** Codex |
| 许可 | 多数 Apache-2.0；文档类技能是 source-available | **逐技能**看各自目录内 `LICENSE.txt`，仓库整体无统一许可 |

**给你的建议**：Codex 侧**不要照搬**这份清单。
Codex 那个会话真正需要的是**本项目自己的规范文件**（`AGENTS.md`、`docs/tasks/*.md`），
而不是通用方法论技能 —— 我们的流程已经定死在文件里了。

---

## 五、安装与回滚方式（等你确认后再执行）

**Claude 侧**：

```
/plugin marketplace add anthropics/skills
```

```
/plugin install webapp-testing@anthropic-agent-skills
```

```
/plugin install feature-dev@claude-plugins-official
```

```
/plugin install superpowers@claude-plugins-official
```

**OpenCodeReview（走 npm，不是插件）**：

```bash
npm install -g @alibaba-group/open-code-review
```

**回滚**：插件可在会话里禁用而不改项目配置；`/plugin` 面板可卸载。
`ocr` 走 `npm uninstall -g`。

---

## 六、安装前必须向你确认的三点

1. **Superpowers 装不装？** 它功能最强，但会强推自己的方法论，
   与你已定的流程（蓝图第 10 节 + `AGENTS.md` + 我们的任务卡制度）有重叠与冲突。
2. **哪些装到项目级、哪些只装到本机？**
   项目级（`.claude/`）会随仓库分发，团队成员都会受影响；
   本机级只影响你这台机器。
3. **Codex 侧要不要也配？** 我的建议是**不配通用技能**，
   只给它项目自己的规范文件（见第四节）。
