#!/usr/bin/env bash
# P0 验证脚本：在无外网沙箱里验证 OpenCodeReview 能跑。
#
# 要点：用 `ocr review --preview`，它**不调用模型**，所以
#   1) 不需要 API 密钥，不需要联网；
#   2) 零成本。
# 它只回答"文件选择与 Git 依赖是否工作"，把这个问题与"模型配置"解耦。
# 见 docs/sandbox-image.md 第 7 节。

set -euo pipefail

IMAGE="${IMAGE:-workbench-sandbox-ocr:latest}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "==> 1. 准备一个带提交的小仓库"
mkdir -p "$WORKDIR/repo"
cd "$WORKDIR/repo"
git init -q
git config user.email "sandbox@local"
git config user.name "sandbox"
cat > demo.py <<'PY'
def divide(a, b):
    return a / b
PY
git add -A
git commit -q -m "init"

# 制造一处改动，供 ocr 审查
cat > demo.py <<'PY'
def divide(a, b):
    return a / b


def unsafe(x):
    eval(x)
PY

cd "$WORKDIR"

echo "==> 2. 验证镜像里的 Git 版本满足 >= 2.41"
docker run --rm --network none "$IMAGE" git --version | tee /tmp/git-version.txt
GIT_VER="$(awk '{print $3}' /tmp/git-version.txt)"
if [ "$(printf '%s\n2.41\n' "$GIT_VER" | sort -V | head -1)" != "2.41" ]; then
  echo "Git 版本 $GIT_VER 低于要求的 2.41" >&2
  exit 1
fi

echo "==> 3. 验证无外网（这一步必须失败才算通过）"
if docker run --rm --network none "$IMAGE" curl -sS --max-time 5 https://example.com >/dev/null 2>&1; then
  echo "沙箱竟然能访问外网 —— 网络策略没生效" >&2
  exit 1
fi
echo "    无外网：符合预期"

echo "==> 4. 在沙箱里跑 ocr review --preview（不调模型，零成本）"
# 两个必需的环境变量（缺陷 22，实测发现）：
#   safe.directory —— 挂载进来的仓库属主是宿主 uid（容器里看到是 0），而沙箱以
#                     uid 10001 运行，Git >= 2.35.2 会判 "dubious ownership" 直接拒绝，
#                     ocr 随之报 "/work is not a git repository"。
#   HOME=/tmp      —— 根文件系统只读，ocr/git 若往 $HOME 写配置或缓存会失败。
# 这两条是沙箱运行代码任务的固定前提，P4 的执行器必须同样传入（见 docs/sandbox-image.md 第 7 节）。
docker run --rm \
  --network none \
  --cpus 2 --memory 2g \
  --read-only --tmpfs /tmp \
  -e HOME=/tmp \
  -e GIT_CONFIG_COUNT=1 \
  -e GIT_CONFIG_KEY_0=safe.directory \
  -e GIT_CONFIG_VALUE_0=/work \
  -v "$WORKDIR/repo:/work:ro" \
  -w /work \
  "$IMAGE" \
  ocr review --preview

echo
echo "通过：OpenCodeReview 能在无外网、只读、受限资源的沙箱里完成文件选择。"
echo "下一步（P4-A 前）：验证 --format json --audience agent 的输出能稳定解析。"
