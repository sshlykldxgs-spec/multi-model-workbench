"""门禁：分层与外部 SDK 位置（R-1、R-3）。

为什么不用 import-linter 的 forbidden 契约做这件事：
  开启 include_external_packages 后，lint-imports 会**追踪整条传递链**。
  app.core.deps 只是 import 了 app.gateway.registry，而 registry 内部
  import 了 openai，于是 app.core 被判定为「import 了 openai」。
  实测结果：app.api 与 app.core 全部误报。

  但 R-3 的真实规则是「**直接** import 厂商 SDK 只允许出现在协议适配器内」，
  传递性依赖是正常的分层结果，不是违规。
  import-linter 表达不了「仅直接」，所以这里用 AST 自己查。

三层规则：
  A. agent_framework* 只允许出现在 app/orchestrator/ 下（R-1）
  B. openai / anthropic / google 只允许出现在 app/gateway/protocols/ 下（R-3）
  C. 底层不得反向依赖上层：orchestrator / gateway / tools / knowledge / models /
     schemas / core 不得 import app.api 或 app.middleware
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]

#: 规则 A：模块名前缀 → 只允许出现的目录
SDK_RULES: tuple[tuple[str, str, str], ...] = (
    ("agent_framework", "app/orchestrator", "R-1：MAF 只允许出现在编排层"),
    ("openai", "app/gateway/protocols", "R-3：厂商 SDK 只允许在协议适配器内"),
    ("anthropic", "app/gateway/protocols", "R-3：厂商 SDK 只允许在协议适配器内"),
    ("google", "app/gateway/protocols", "R-3：厂商 SDK 只允许在协议适配器内"),
)

#: 规则 C：这些包不得依赖 api / middleware
LOWER_LAYERS = (
    "app/orchestrator",
    "app/gateway",
    "app/tools",
    "app/knowledge",
    "app/models",
    "app/schemas",
    "app/core",
)
UPPER_LAYERS = ("app.api", "app.middleware")


def direct_imports(path: Path) -> list[tuple[str, int]]:
    """取出**直接** import 的顶层模块名与其行号。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((a.name.split(".")[0], node.lineno) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            # 相对导入（level > 0）不是外部包
            if node.level == 0 and node.module:
                out.append((node.module.split(".")[0], node.lineno))
    return out


def main() -> int:
    problems: list[str] = []

    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP.parent).as_posix()

        for name, lineno in direct_imports(path):
            for prefix, allowed_dir, rule in SDK_RULES:
                if name == prefix or name.startswith(prefix):
                    if not rel.startswith(allowed_dir + "/"):
                        problems.append(
                            f"{rel}:{lineno} 直接 import 了 {name}，"
                            f"但只允许出现在 {allowed_dir}/（{rule}）"
                        )
        # 规则 C 需要完整模块名，单独再扫一遍
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            mod: str | None = None
            lineno = getattr(node, "lineno", 0)
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mod = node.module
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith(UPPER_LAYERS):
                        mod = a.name
            if mod and mod.startswith(UPPER_LAYERS) and rel.startswith(LOWER_LAYERS):
                problems.append(f"{rel}:{lineno} 下层模块 import 了上层 {mod}（依赖只能单向向下）")

    if problems:
        print("[分层门禁] 发现违规：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("[分层门禁] 通过：厂商 SDK 位置、MAF 位置、依赖方向 均符合 R-1 / R-3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
