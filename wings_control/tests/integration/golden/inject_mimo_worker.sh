#!/usr/bin/env bash
set -euo pipefail

_wings_log() {
    local level="$1"; shift
    local msg="$*"
    local ts
    ts=$(date "+%Y-%m-%d %H:%M:%S.%3N")
    echo "$ts [$level] WINGS-CONTROL [wings-launcher#start_command:0] $msg"
}

export GLOO_SOCKET_IFNAME=eth0
export NCCL_SOCKET_IFNAME=eth0
export RAG_ACC_ENABLED=false

vllm serve /model/MiMo-V2-Flash --host 0.0.0.0 --port 17000 --trust-remote-code --generation-config vllm -cc.pass_config.fuse_allreduce_rms=False --tensor-parallel-size 8 --nnodes 2 --node-rank 1 --master-addr 10.0.0.1 --headless --served-model-name MiMo-V2-Flash &
ENGINE_PID=$!
_wings_log INFO "engine started, PID=$ENGINE_PID"
wait "$ENGINE_PID"
ENGINE_EXIT_CODE=$?
exit "$ENGINE_EXIT_CODE"
