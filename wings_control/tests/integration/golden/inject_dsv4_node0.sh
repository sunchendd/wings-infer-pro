#!/usr/bin/env bash
set -euo pipefail

_wings_log() {
    local level="$1"; shift
    local msg="$*"
    local ts
    ts=$(date "+%Y-%m-%d %H:%M:%S.%3N")
    echo "$ts [$level] WINGS-CONTROL [wings-launcher#start_command:0] $msg"
}

# ─── runtime commands (inline; source: <CONFIG>/engines/vllm-ascend/v0.18.0/ascend-a3/models/DeepSeek-V4-Pro/DeepSeek-V4-Pro.yaml @ scenarios.multi_node.strategies.multi_node.head.system_setup) ───
nic_name=$(awk '$2=="00000000"{print $1;exit}' /proc/net/route 2>/dev/null || echo eth0)

# --- log_analyzer: 启动部署进度监控 ---
# 清空旧日志,确保 log_analyzer 只分析新日志(避免残留触发误判)
rm -f /var/log/wings/engine.log
rm -f /var/log/wings/engine-full.log
rm -f /shared-volume/progress.jsonl

# 记录脚本开始时间(用于计算耗时)
SCRIPT_START_EPOCH=$(date +%s)

# _wings_log() 已在 start_command.sh 头部无条件定义(所有脚本通用)。
# 此处直接使用,无需重复定义。

ANALYZER_CONFIG='{"engine": "vllm-ascend", "deployment_mode": "distributed", "hardware": "ascend", "backend_port": 8900}'
_wings_log INFO "log_analyzer config: $ANALYZER_CONFIG"

# 启动日志分析器(后台)
cd /shared-volume && python3 -B -m log_analyzer.log_analyzer \
    --config "$ANALYZER_CONFIG" \
    --log-file /var/log/wings/engine.log \
    --progress-file /shared-volume/progress.jsonl &
LOG_ANALYZER_PID=$!
_wings_log INFO "log_analyzer PID: $LOG_ANALYZER_PID"

# 注册清理函数(等待分析器完全退出)
# 引擎以后台进程运行(非 exec 替换),shell 保持存活,
# trap 在引擎退出后正常触发,确保 log_analyzer 被正确清理。
cleanup_analyzer() {
    local exit_code=$?
    _wings_log INFO "stopping log_analyzer (cleanup triggered)"
    if [ -n "$LOG_ANALYZER_PID" ]; then
        kill $LOG_ANALYZER_PID 2>/dev/null || true
        wait $LOG_ANALYZER_PID 2>/dev/null || true
    fi

    if [ -n "${ENGINE_PID:-}" ]; then
        _wings_log INFO "sending SIGTERM to engine process (PID=$ENGINE_PID)"
        kill -TERM "$ENGINE_PID" 2>/dev/null || true
    else
        # ENGINE_PID 未设置说明引擎启动前脚本就失败了
        if [ "$exit_code" -ne 0 ]; then
            _wings_log ERROR "script exited before engine start, exit_code=$exit_code"
            local curr_time
            curr_time=$(date -Iseconds)
            local start_time
            start_time=$(date -Iseconds -d "@${SCRIPT_START_EPOCH}")
            local elapsed
            elapsed=$(( $(date +%s) - SCRIPT_START_EPOCH ))
            cat >> "/shared-volume/progress.jsonl" <<EARLY_FAIL_EOF
{"progress": 0, "phase_code": "script_error", "phase_name": "启动脚本执行失败", "status": "failed", "key_log": "引擎启动前脚本异常退出，退出码: $exit_code", "curr_time": "$curr_time", "start_time": "$start_time", "elapsed_time_s": $elapsed}
EARLY_FAIL_EOF
        fi
    fi
}
trap cleanup_analyzer EXIT SIGTERM SIGINT
# --- end log_analyzer ---


mkdir -p /var/log/wings
export PYTHONUNBUFFERED=1
exec > >(tee -a /var/log/wings/engine-full.log | grep --line-buffered -vE '"GET\s+/(health|metrics)\s|\b(Prefill|Decode) batch\b' | tee -a /var/log/wings/engine.log) 2>&1

export HCCL_OP_EXPANSION_MODE=AIV
export HCCL_IF_IP=10.0.0.1
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

# ─── System Setup (source: <CONFIG>/engines/vllm-ascend/v0.18.0/ascend-a3/models/DeepSeek-V4-Pro/DeepSeek-V4-Pro.yaml @ scenarios.multi_node.strategies.multi_node.head.system_setup) ───
# sysctls:
#   sysctl -w vm.swappiness=0
#   sysctl -w kernel.numa_balancing=0
#   sysctl -w kernel.sched_migration_cost_ns=50000
# sysfs_writes:
#   echo 'performance' > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

vllm serve /model/DeepSeek-V4-Pro --host 0.0.0.0 --port 8900 --safetensors-load-strategy prefetch --max-model-len 135000 --max-num-batched-tokens 4096 --served-model-name DeepSeek-V4-Pro --gpu-memory-utilization 0.9 --max-num-seqs 16 --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-start-rank 0 --data-parallel-address 10.0.0.1 --data-parallel-rpc-port 13399 --tensor-parallel-size 16 --enable-expert-parallel --quantization ascend --block-size 128 --async-scheduling --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}' --additional-config '{"enable_cpu_binding":"true","ascend_compilation_config":{"enable_npugraph_ex":true,"enable_static_kernel":false}}' &
ENGINE_PID=$!
_wings_log INFO "engine started, PID=$ENGINE_PID"
wait "$ENGINE_PID"
ENGINE_EXIT_CODE=$?
exit "$ENGINE_EXIT_CODE"
