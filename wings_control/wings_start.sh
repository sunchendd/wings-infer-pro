#!/usr/bin/env bash
# wings-control 启动入口(MaaS 调用 / 本地测试用)。
#
# 等价于:python -m wings_ctl <args>;把参数原样透传给 CLI。
# MaaS 生产路径形如 /opt/wings-control/wings_start.sh;本仓库放在仓库根,语义一致。
#
# 行为(已与团队确认):**只生成三件产物**(start_command.sh / repro.sh / audit.json
# [+ wings_start.log]),**不 exec 拉起 engine**(新框架旁路,只生成不接管拉起)。
# 真正拉起由调用方执行生成的 start_command.sh(multi_node 占位脚本含 exit 3,勿直接跑)。
#
# 用法:
#   bash wings_start.sh --engine vllm-ascend --model-name DeepSeek-V4-Flash \
#       --hardware-info /path/hw.json --port 18000 --output-dir /path/out ...
#   - 配方标识 = --model-name(模型名称,做 name_pattern 查找 + served_model_name);
#     缺省可由 --model-path basename 推导。
#   - --hardware-info 可由 WINGS_HARDWARE_FILE env 提供;--engine 可由 ENGINE env 提供;
#     multi_node 运行时上下文走 RANK_IP/NODE_IPS/MASTER_IP env。

set -uo pipefail

# 仓库根 = 本脚本所在目录(无论从哪里调用)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Python:优先仓库内 venv,否则系统 python3
if [ -x "$HERE/.venv/bin/python" ]; then
  PY="$HERE/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi
if [ -z "${PY:-}" ]; then
  echo "ERROR: 未找到 python(.venv/bin/python 或 python3)" >&2
  exit 1
fi

# 拷贝 log_analyzer 模块到共享卷
# log_analyzer 在构建时被单独拷贝到 /opt/log_analyzer(避免 pyc 编译),
# 运行时再拷贝到 /shared-volume/log_analyzer,供 start_command.sh 中的后台进程使用。
if [ -d "${DEFAULT_LOG_ANALYZER:-/opt/log_analyzer}" ]; then
  echo "Copying ${DEFAULT_LOG_ANALYZER:-/opt/log_analyzer} module to /shared-volume..."
  cp -r "${DEFAULT_LOG_ANALYZER:-/opt/log_analyzer}" "${SHARED_VOLUME_PATH:-/shared-volume}/"
  echo "${DEFAULT_LOG_ANALYZER:-/opt/log_analyzer} copied successfully !"
fi

# 让 wings_ctl 可被导入(源码在 src/)
export PYTHONPATH="$HERE/src${PYTHONPATH:+:$PYTHONPATH}"

exec "$PY" -m wings_ctl "$@"
