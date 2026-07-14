#!/usr/bin/env bash
set -euo pipefail

# ─── runtime commands (inline; source: <CONFIG>/engines/vllm/gb200/models/MiMo-V2-Flash/MiMo-V2-Flash-fp8.yaml @ scenarios.multi_node.strategies.multi_node_tp.worker.system_setup) ───
IFACE_NAME=$(awk '$2=="00000000"{print $1;exit}' /proc/net/route 2>/dev/null || echo eth0)

export GLOO_SOCKET_IFNAME="$IFACE_NAME"
export NCCL_SOCKET_IFNAME="$IFACE_NAME"

exec vllm serve /model/MiMo-V2-Flash --host 0.0.0.0 --port 17000 --trust-remote-code --generation-config vllm --tensor-parallel-size 8 --nnodes 2 --node-rank 1 --master-addr 10.0.0.1 --headless --served-model-name MiMo-V2-Flash
