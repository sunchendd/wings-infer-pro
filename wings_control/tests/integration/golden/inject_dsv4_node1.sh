#!/usr/bin/env bash
set -euo pipefail

_wings_log() {
    local level="$1"; shift
    local msg="$*"
    local ts
    ts=$(date "+%Y-%m-%d %H:%M:%S.%3N")
    echo "$ts [$level] WINGS-CONTROL [wings-launcher#start_command:0] $msg"
}

# ─── runtime commands (inline; source: <CONFIG>/engines/vllm-ascend/v0.18.0/ascend-a3/models/DeepSeek-V4-Pro/DeepSeek-V4-Pro.yaml @ scenarios.multi_node.strategies.multi_node.worker.system_setup) ───
nic_name=$(awk '$2=="00000000"{print $1;exit}' /proc/net/route 2>/dev/null || echo eth0)

export HCCL_OP_EXPANSION_MODE=AIV
export HCCL_IF_IP=10.0.0.2
export GLOO_SOCKET_IFNAME="$nic_name"
export TP_SOCKET_IFNAME="$nic_name"
export HCCL_SOCKET_IFNAME="$nic_name"
export HCCL_BUFFSIZE=2048
export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
export OMP_PROC_BIND=false
export OMP_NUM_THREADS=10
export TASK_QUEUE_ENABLE=1
export LD_PRELOAD="/usr/lib/aarch64-linux-gnu/libjemalloc.so.2${LD_PRELOAD:+:$LD_PRELOAD}"
export USE_MULTI_GROUPS_KV_CACHE=1
export USE_MULTI_BLOCK_POOL=1
export VLLM_ASCEND_ENABLE_FLASHCOMM1=1
export VLLM_ASCEND_ENABLE_FUSED_MC2=1

# ─── System Setup (source: <CONFIG>/engines/vllm-ascend/v0.18.0/ascend-a3/models/DeepSeek-V4-Pro/DeepSeek-V4-Pro.yaml @ scenarios.multi_node.strategies.multi_node.worker.system_setup) ───
# sysctls:
#   sysctl -w vm.swappiness=0
#   sysctl -w kernel.numa_balancing=0
#   sysctl -w kernel.sched_migration_cost_ns=50000
# sysfs_writes:
#   echo 'performance' > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

vllm serve /model/DeepSeek-V4-Pro --host 0.0.0.0 --port 8900 --safetensors-load-strategy prefetch --max-model-len 135000 --max-num-batched-tokens 4096 --served-model-name DeepSeek-V4-Pro --gpu-memory-utilization 0.9 --max-num-seqs 16 --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-start-rank 1 --data-parallel-address 10.0.0.1 --data-parallel-rpc-port 13399 --tensor-parallel-size 16 --enable-expert-parallel --quantization ascend --block-size 128 --async-scheduling --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}' --additional-config '{"enable_cpu_binding":"true","ascend_compilation_config":{"enable_npugraph_ex":true,"enable_static_kernel":false}}' &
ENGINE_PID=$!
_wings_log INFO "engine started, PID=$ENGINE_PID"
wait "$ENGINE_PID"
ENGINE_EXIT_CODE=$?
exit "$ENGINE_EXIT_CODE"
