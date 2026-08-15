#!/usr/bin/env bash
set -euo pipefail

_wings_log() {
    local level="$1"; shift
    local msg="$*"
    local ts
    ts=$(date "+%Y-%m-%d %H:%M:%S.%3N")
    echo "$ts [$level] WINGS-CONTROL [wings-launcher#start_command:0] $msg"
}

# --- log_analyzer: 启动部署进度监控 ---
# 清空旧日志,确保 log_analyzer 只分析新日志(避免残留触发误判)
rm -f /var/log/wings/engine.log
rm -f /var/log/wings/engine-full.log
rm -f /shared-volume/progress.jsonl

# 记录脚本开始时间(用于计算耗时)
SCRIPT_START_EPOCH=$(date +%s)

# _wings_log() 已在 start_command.sh 头部无条件定义(所有脚本通用)。
# 此处直接使用,无需重复定义。

ANALYZER_CONFIG='{"engine": "vllm", "deployment_mode": "distributed", "hardware": "nvidia", "backend_port": 17000}'
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

export GLOO_SOCKET_IFNAME=eth0
export NCCL_SOCKET_IFNAME=eth0

vllm serve /model/MiMo-V2-Flash --host 0.0.0.0 --port 17000 --trust-remote-code --generation-config vllm --tensor-parallel-size 8 --nnodes 2 --node-rank 0 --master-addr 10.0.0.1 --served-model-name MiMo-V2-Flash &
ENGINE_PID=$!
_wings_log INFO "engine started, PID=$ENGINE_PID"
wait "$ENGINE_PID"
ENGINE_EXIT_CODE=$?
exit "$ENGINE_EXIT_CODE"
