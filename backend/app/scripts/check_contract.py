"""门禁：导出的 OpenAPI 与 docs/api-contract.md 必须一致。

对应 backend/AGENTS.md 第 6 节的第 4 道门禁。做法：
  1. 从契约文档抽出所有反引号包裹的路径，归一化。
  2. 从应用导出 OpenAPI，取其路径，归一化。
  3. 双向比对：
     - 契约声明且属 P0 范围、但 OpenAPI 没有 → 失败（没做完）
     - OpenAPI 有但契约没声明 → 失败（改接口要先改契约）

P0 范围由 P0_DEFERRED_PREFIXES 的补集定义：凡以这些前缀开头的路径，
视为后续阶段，允许"契约已声明但尚未实现"。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
CONTRACT = BACKEND.parent / "docs" / "api-contract.md"

#: 只匹配契约里的路径。遇到 `?` 立即截断，因为契约里会写
#: `GET /runs/{id}/events?after=序号` 这种带查询串的说明。
PATH_RE = re.compile(
    r"`(?:GET|POST|PATCH|PUT|DELETE|CRUD|GET/POST|GET/PATCH/DELETE|GET/DELETE)?\s*"
    r"(/(?:health|auth|models|conversations|runs|agents|workflows|tools|"
    r"mcp-servers|knowledge-bases|usage|admin|studio)(?:/[A-Za-z0-9_\-{}.:]+)*)"
)

#: 契约正文里出现、但并不是接口的裸路径。
#: `/api/v1` 是"所有路径以此开头"的说明；`/runs` 单独出现是讲幂等键的叙述。
NOT_ENDPOINTS: frozenset[str] = frozenset({"/api/v1", "/api/v1/runs"})

#: 这些前缀的接口推到 P1 之后，契约里已声明但允许暂未实现。
#: 每进入一个阶段就把对应前缀删掉，门禁随之变严。
P0_DEFERRED_PREFIXES: tuple[str, ...] = (
    "/api/v1/admin",
    "/api/v1/agents",
    "/api/v1/workflows",
    "/api/v1/tools",
    "/api/v1/mcp-servers",
    "/api/v1/knowledge-bases",
    "/api/v1/usage",
    "/api/v1/studio",
    # 会话的子资源与单会话操作在 P1-D 落地；P0 只有列表与新建
    "/api/v1/conversations/{param}/messages",
)


def normalize(path: str) -> str:
    path = path.split("?", 1)[0]
    if not path.startswith("/api/v1"):
        path = "/api/v1" + path
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    return path.rstrip(".,;").rstrip("/") or "/api/v1"


def contract_paths(text: str) -> set[str]:
    return {normalize(raw) for raw in PATH_RE.findall(text)} - NOT_ENDPOINTS


def openapi_paths() -> set[str]:
    from app.main import create_app

    spec = create_app().openapi()
    return {normalize(p) for p in spec["paths"]}


def is_deferred(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in P0_DEFERRED_PREFIXES)


def main() -> int:
    if not CONTRACT.exists():
        print(f"[契约门禁] 找不到契约文件：{CONTRACT}", file=sys.stderr)
        return 2

    declared = contract_paths(CONTRACT.read_text(encoding="utf-8"))
    implemented = openapi_paths()

    # 契约里的 `/conversations/{id}` 单会话操作（GET/PATCH/DELETE）也在 P1-D。
    # 这里按"实现了列表就算 P0 完成"处理，单会话操作归入 deferred。
    single_convo = "/api/v1/conversations/{param}"
    p0_declared = {p for p in declared if not is_deferred(p) and p != single_convo}

    missing = sorted(p for p in p0_declared if p not in implemented)
    extra = sorted(p for p in implemented if p not in declared)

    ok = True
    if missing:
        ok = False
        print("[契约门禁] 契约声明了但 OpenAPI 未实现的 P0 接口：", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
    if extra:
        ok = False
        print("[契约门禁] OpenAPI 里有但契约未声明的接口（改接口要先改契约）：", file=sys.stderr)
        for p in extra:
            print(f"  + {p}", file=sys.stderr)
    if not ok:
        return 1

    deferred = sorted(p for p in declared if is_deferred(p) and p not in implemented)
    print(f"[契约门禁] 通过：P0 声明 {len(p0_declared)} 条全部已实现，无未声明接口")
    print(f"[契约门禁] 另有 {len(deferred)} 条契约已声明、推至后续阶段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
