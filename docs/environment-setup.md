# 环境准备（需要你在终端执行）

> 我的会话沙箱拦截出网，`pip install`、`brew install` 会被拒，所以安装必须由你执行。
> 下面按顺序做，每步都可单独验证。**做完一步就可以告诉我，不必等全部做完。**

最后更新：2026-10-14

## 本机现状（已实测）

| 工具 | 现状 | 是否需要动 |
|------|------|-----------|
| Python | 3.12.8 | 满足（要求 3.11+） |
| Node / npm | 24.21.0 / 11.19.0 | 满足 |
| Homebrew | 7.0.8 | 已有 |
| gh | 2.102.0，**未登录** | 需登录 |
| **git** | **2.39.5** | **需升级到 ≥ 2.41** |
| uv、ruff、pyright | 未安装 | 需安装（ruff/pyright 随 uv 走） |
| docker、psql、caddy | 未安装 | 需安装 |

**Git 那条最关键**：OpenCodeReview 要求 Git ≥ 2.41，本机 2.39.5 不满足。
P4 之前必须解决，早做早省事。

---

## 第一步：uv（Python 工具链）

```bash
brew install uv
```

验证：

```bash
uv --version
```

`ruff` 与 `pyright` **不需要单独装** —— 它们在后端的 dev 依赖里，`uv sync` 会一起装好。

## 第二步：升级 Git 到 ≥ 2.41

```bash
brew install git
```

验证：

```bash
git --version
```

若显示的仍是 2.39.5（macOS 自带的那份优先），把 Homebrew 的放到 PATH 前面：

```bash
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zprofile
```

然后重开终端再验证一次。

## 第三步：Docker Desktop

```bash
brew install --cask docker
```

装完**需要手动打开一次 Docker Desktop**，否则 `docker` 命令无法连接守护进程。
沙箱与本地 Postgres 都靠它。

验证：

```bash
docker --version
```

## 第四步：PostgreSQL 客户端（psql）

```bash
brew install libpq
```

```bash
brew link --force libpq
```

验证：

```bash
psql --version
```

数据库本身用 Docker 起即可，不需要 brew 装服务端（见下方 docker-compose）。

## 第五步：登录 GitHub

```bash
gh auth login
```

按提示选 GitHub.com → HTTPS → 用浏览器登录。
P0 的 CI 与后续的 PR 流程都需要它。

---

## 装完之后：启动后端

在项目根目录：

```bash
cd /Users/pengxuezhi/项目蓝图2.0/multi-model-workbench/backend
```

```bash
uv sync --extra dev
```

```bash
cp .env.example .env
```

（`.env` 已经在 `.gitignore` 里，不会被提交。）

先跑门禁，确认环境是干净的：

```bash
uv run ruff check . && uv run pyright && uv run pytest -q
```

再起服务：

```bash
uv run uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000/docs 应该能看到接口文档 —— 这就是蓝图 P0 验收里
「打开接口文档页，能看到全部接口」那一条。

## 启动前端

另开一个终端：

```bash
cd /Users/pengxuezhi/项目蓝图2.0/multi-model-workbench/frontend
```

```bash
npm install
```

```bash
npm run dev
```

打开 http://localhost:5173 ，用 `.env` 里的引导管理员账号登录
（默认 `admin@example.com` / `admin12345`，**上线前必须改**）。
选 mock 模型发一句话，应看到**逐字**输出 —— 这是 P0 验收的核心那一条。

前端类型来自后端 OpenAPI，后端起来后执行一次：

```bash
npm run gen:api
```

这会覆盖 `src/api/schema.d.ts`（目前是占位文件）。

---

## 遇到问题时

- **`uv sync` 报网络错误**：本地网络问题，与沙箱无关（你在自己终端跑）。
- **`uv sync` 报找不到 `agent-framework`**：先跑 `uv pip index versions agent-framework`
  确认真实版本。已核实的事实是各索引源对最新版说法不一，
  `pyproject.toml` 里目前写的是 `>=1.0.1`（2026-04-10 发布），按实测结果调整。
- **`pyright` 报 `agent_framework` 找不到**：正常，P0 骨架里编排层只放了接口，
  没有真正 import MAF。等 P4 实化时再处理。
- **端口占用**：改 `--port` 与 `vite.config.ts` 里的 `proxy.target`，两处要一致。
