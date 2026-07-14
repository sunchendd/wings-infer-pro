#!/usr/bin/env bash
# check.sh — 单一"绿"定义:ruff lint + 红线守卫(rg engine==) + pytest。
# 人 / CI / pre-commit 都跑这一条命令,口径一致,不漂移。
# 用法:bash scripts/check.sh   (在 wings_control 下,或任意目录均可——脚本自定位)
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # wings_control 根
cd "$HERE"

# ── 解释器:优先带依赖的 venv(本仓 .venv → 上层 .venv → 系统 python3)──
PY=""
for c in "$HERE/.venv/bin/python" "$HERE/../.venv/bin/python" "$(command -v python3 || true)"; do
  [ -n "$c" ] && [ -x "$c" ] && { PY="$c"; break; }
done
[ -z "$PY" ] && { echo "ERROR: 未找到 python"; exit 2; }
RUFF="$(dirname "$PY")/ruff"; [ -x "$RUFF" ] || RUFF="$(command -v ruff || true)"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

FAIL=0
hr(){ echo; echo "───── $* ─────"; }

# 1) ruff lint(硬;配置见 pyproject [tool.ruff],已排除移植 proxy 子系统)
hr "ruff lint (E9/F/W)"
if [ -n "$RUFF" ]; then
  "$RUFF" check . && echo "  ✓ lint 通过" || { echo "  ❌ lint 不通过(可 'ruff check --fix' 自动修部分)"; FAIL=1; }
else
  echo "  ❌ ruff 未安装:pip install ruff(或 pip install -e '.[dev]')"; FAIL=1
fi

# 2) 红线守卫(硬):主流水线 engine== 必须 0;移植进来的 proxy 子系统豁免。
#    用 grep 以免依赖 rg(CI 更稳)。
hr "red-line: 主流水线 'engine ==' = 0"
HITS="$(grep -rEn "engine[[:space:]]*==" src/wings_ctl --include='*.py' \
          --exclude-dir=rag_acc --exclude-dir=common --exclude-dir=proxy \
          --exclude=wings_control.py || true)"
if [ -n "$HITS" ]; then
  echo "$HITS"; echo "  ❌ 主流水线出现 engine==(配置解析主流水线不得按引擎分支)"; FAIL=1
else
  echo "  ✓ 0 命中(proxy 子系统已豁免)"
fi

# 3) pytest 核心套件(硬)。排除 test_wings_start_sh:它子进程跑 wings_start.sh、
#    依赖 shell 选到的 python 是否装了 proxy 依赖(pydantic 等),属环境相关问题,单列为软步。
hr "pytest (核心套件)"
"$PY" -m pytest -q --ignore=tests/integration/test_wings_start_sh.py \
  && echo "  ✓ 核心套件全绿" || { echo "  ❌ 核心套件有失败"; FAIL=1; }

# 4) 子进程集成(软:报告不阻断)——子进程 python 依赖环境,不纳入硬 gate
hr "pytest test_wings_start_sh (软;子进程依赖)"
"$PY" -m pytest -q tests/integration/test_wings_start_sh.py >/dev/null 2>&1 \
  && echo "  ✓ 通过" \
  || echo "  ⚠️ 未通过(子进程 python 是否装 proxy 依赖;不阻断本 gate)"

# 5) ruff format(软:仅提示)——全量整形留作一次性提交后再纳入硬关
hr "ruff format --check (软提示)"
if [ -n "$RUFF" ] && "$RUFF" format --check . >/dev/null 2>&1; then
  echo "  ✓ 已符合 ruff format"
else
  echo "  ⚠️ 有文件未按 ruff format 整形(建议单独跑一次 '$RUFF format .' 作一次性提交;暂不阻断)"
fi

echo
[ "$FAIL" -eq 0 ] && echo "================  check OK  ================" || echo "================  check FAILED  ================"
exit "$FAIL"
