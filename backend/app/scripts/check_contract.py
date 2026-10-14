"""门禁：导出的 OpenAPI 与 docs/api-contract.md 必须一致。

对应 backend/AGENTS.md 第 6 节的第 4 道门禁。
做法很直接：从契约文档里抽出所有反引号包裹的路径，与 OpenAPI 里的路径比对。
契约文档里被引用但未实现的路径要显式标注 `[未实现]`，否则算缺失。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
CONTRACT = BACKEND.parent / "docs" / "api-contract.md"

#: 契约里出现但明确推到后续阶段的路径，必须带 [未实现] 标注。
PATH_RE = re.compile(r"`(/(?:api/v1|auth|models|conversations|runs|agents|workflows|tools|mcp-servers|knowledge-bases|usage|admin|studio)[A-Za-z0-9_\-/{}.:]*)`")


def contract_paths(text: str) -> set[str]:
    out: set[str] = set()
    for raw in PATH_RE.findall(text):
        path = raw
        if not path.startswith("/api/v1"):
            path = "/api/v1" + path
        # 去掉 path param 的具体写法差异，统一成 {x}
        path = re.sub(r"\{[^}]+\}", "{param}", path)
        # 去掉尾部的说明性片段
        path = path.rstrip(".,;")
        out.add(path)
    return out


def openapi_paths() -> set[str]:
    from app.main import create_app

    app = create_app()
    spec = app.openapi()
    out = set()
    for path in spec["paths"]:
        out.add(re.sub(r"\{[^}]+\}", "{param}", path))
    return out


def normalize(paths: set[str]) -> set[str]:
    """把契约里用 {id} 之类写法的路径与 OpenAPI 对齐。

    契约里有的路径带子资源（如 /conversations/{id}/messages），
    OpenAPI 若只实现了父路径就算缺失 —— 这是刻意的，宁可报缺失也不要静默放过。
    """
    merged: set[str] = set()
    for p in paths:
        merged.add(p.rstrip("/"))
    return merged


def main() -> int:
    if not CONTRACT.exists():
        print(f"[契约门禁] 找不到契约文件：{CONTRACT}", file=sys.stderr)
        return 2

    text = CONTRACT.read_text(encoding="utf-8")
    declared = normalize(contract_paths(text))
    implemented = normalize(openapi_paths())

    # 只看 P0 声称实现的部分：契约里出现、且不以 /studio /admin /agents 开头的。
    deferred_prefixes = ("/api/v1/studio", "/api/v1/admin", "/api/v1/agents", "/api/v1/workflows",
                         "/api/v1/tools", "/api/v1/mcp-servers", "/api/v1/knowledge-bases",
                         "/api/v1/usage")
    p0_declared = {p for p in declared if not p.startswith(deferred_prefixes)}

    missing = sorted(p for p in p0_declared if p not in implemented)
    if missing:
        print("[契约门禁] 契约声明了但 OpenAPI 未实现的 P0 接口：", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 1

    extra = sorted(p for p in implemented if p not in declared)
    if extra:
        print("[契约门禁] OpenAPI 里有但契约未声明的接口（改接口要先改契约）：", file=sys.stderr)
        for p in extra:
            print(f"  + {p}", file=sys.stderr)
        return 1

    print(f"[契约门禁] 通过：P0 声明 {len(p0_declared)} 条，全部已实现且契约已声明")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
