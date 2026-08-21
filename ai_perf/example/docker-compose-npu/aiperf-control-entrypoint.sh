#!/bin/bash
# AI Perf control 入口 — 适配 wings-infer-pro (Wings Control 重构版)
#
# 相对旧版 AI Perf 仓库的适配点:
# 1. 新版 wings_ctl CLI 已移除 --enable-speculative-decode 等 flag,
#    投机解码/稀疏加速改由环境变量 ENABLE_SPECULATIVE_DECODE / ENABLE_SPARSE
#    交给 SmartAccel 子系统消费(docker-compose 已下发)。
# 2. 新框架按 hardware_family 定位配置目录, 需要提供 hardware_info.json;
#    本入口根据 HARDWARE_FAMILY env 自动写入 /shared-volume/hardware_info.json。
# 3. 新版 wings_start.sh 只生成 start_command.sh / repro.sh / audit.json,
#    不拉起引擎; 引擎容器自行等待并执行 start_command.sh(见 aiperf-engine-entrypoint.sh)。
set -e

SHARED_VOLUME_PATH=/shared-volume

echo "[aiperf-control] Generating hardware_info.json (hardware_family=${HARDWARE_FAMILY:-<unset>}) ..."
cat > "${SHARED_VOLUME_PATH}/hardware_info.json" <<EOF
{
  "hardware_family": "${HARDWARE_FAMILY:-}",
  "device": "ascend",
  "count": ${DEVICE_COUNT:-1},
  "gpu": null,
  "cann_version": null
}
EOF
cat "${SHARED_VOLUME_PATH}/hardware_info.json"

echo "[aiperf-control] Running wings_start.sh..."
[ -n "${ENGINE:-}" ] && ENGINE="${ENGINE//-/_}"

# use array to build command/base command
CMD=(
    "/opt/wings-control/wings_start.sh"
    "--engine" "${ENGINE}"
    "--model-name" "${MODEL_NAME}"
    "--model-path" "${MODEL_PATH}"
    "--input-length" "${INPUT_LENGTH:-10000}"
    "--output-length" "${OUTPUT_LENGTH:-10000}"
    "--max-num-seqs" "${MAX_NUM_SEQS:-64}"
    "--gpu-memory-utilization" "${GPU_MEMORY_UTILIZATION:-0.9}"
    "--device-count" "${DEVICE_COUNT:-1}"
)

# other params
[ -n "${QUANTIZATION:-}" ] && CMD+=("--quantization" "${QUANTIZATION}")
[ "${TRUST_REMOTE_CODE:-false}" = "true" ] && CMD+=("--trust-remote-code")
[ -n "${DTYPE:-}" ] && CMD+=("--dtype" "${DTYPE}")
[ -n "${MAX_NUM_BATCHED_TOKENS:-}" ] && CMD+=("--max-num-batched-tokens" "${MAX_NUM_BATCHED_TOKENS}")
[ -n "${KV_CACHE_DTYPE:-}" ] && CMD+=("--kv-cache-dtype" "${KV_CACHE_DTYPE}")
[ -n "${BLOCK_SIZE:-}" ] && CMD+=("--block-size" "${BLOCK_SIZE}")


echo "[aiperf-control] Command: ${CMD[*]}"
# exec command
"${CMD[@]}" || true

echo "[aiperf-control] start_command.sh content:"
echo "----------------------------------------"
cat ${SHARED_VOLUME_PATH}/start_command.sh
echo "----------------------------------------"

echo "[aiperf-control] Blocking..."
exec tail -f /dev/null
