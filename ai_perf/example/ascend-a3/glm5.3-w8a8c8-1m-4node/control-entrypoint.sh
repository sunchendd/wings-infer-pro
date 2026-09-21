#!/bin/bash
set -Eeuo pipefail

rm -f /shared-volume/start_command.sh /shared-volume/repro.sh /shared-volume/audit.json

/opt/wings-control/wings_start.sh \
  --engine vllm_ascend \
  --distributed \
  --model-name GLM-5.3-w8a8c8-1m-4node \
  --served-model-name GLM-5.3-w8a8c8 \
  --model-path "$MODEL_PATH" \
  --port 18000 \
  --device-count "$DEVICE_COUNT" \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --enable-auto-think-choice \
  --hardware-info /wings-deploy/config/hardware_info.json \
  --output-dir /shared-volume

echo "[control] Configuration artifacts are ready; keeping the control container running."
exec tail -f /dev/null
