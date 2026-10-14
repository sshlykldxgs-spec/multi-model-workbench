# 代码沙箱

方案与理由见 [`docs/sandbox-image.md`](../docs/sandbox-image.md)。这里只放可执行的构件。

## 为什么沙箱必须预装依赖

蓝图第 9 节要求沙箱**默认不开放外网**。若不预置依赖，容器内连 `pip install`
与 `npm install` 都失败，代码任务只能跑纯标准库脚本 —— 这个功能等于白做。
所以依赖清单（`requirements-sandbox.txt`）与离线缓存是必需品，不是优化。

## P0 交付物

| 文件 | 作用 |
|------|------|
| `Dockerfile.base` | 基础层：系统工具 + **版本受控的 Git**（≥2.41，OpenCodeReview 的硬要求） |
| `Dockerfile.ocr` | P0 最小验证镜像：基础层 + Node 20 + 预装 `@alibaba-group/open-code-review` |
| `verify-ocr.sh` | 验证脚本：无外网、只读、受限资源下能否跑通 `ocr review --preview` |
| `requirements-sandbox.txt` | 沙箱内可用的 Python 包清单（离线 wheelhouse 的来源） |

## 构建与验证

```bash
cd sandbox && docker build -f Dockerfile.base -t workbench-sandbox-base:latest .
```

```bash
cd sandbox && docker build -f Dockerfile.ocr -t workbench-sandbox-ocr:latest .
```

```bash
./verify-ocr.sh
```

`verify-ocr.sh` 会依次验证四件事：Git 版本达标、**无外网**（这一步必须失败才算通过）、
`ocr review --preview` 能在受限容器里完成文件选择。

**为什么用 `--preview`**：它不调用模型，所以零成本、不需要密钥，
能把「能不能装、能不能跑」与「模型配置对不对」这两个问题解耦，先钉死前者。

## 为什么验证要提前到 P0

蓝图原计划 P4 才验证 OpenCodeReview（"P4 开始前要先做一次小验证"）。
核实后发现它提供 `--format json --audience agent`（机器可读）与 `--preview`（不调模型），
加上这个最小镜像，验证可以提前到 P0 —— P4 的风险因此显著下降。

## 后续（P4-A 起）

- 完整 `lang` 层（Python / Node / Java / Go / Rust）
- `deps` 层：离线 wheelhouse 与 npm cache
- 出口白名单代理（正向代理，非 Caddy）
- 镜像漏洞扫描与版本发布流程
