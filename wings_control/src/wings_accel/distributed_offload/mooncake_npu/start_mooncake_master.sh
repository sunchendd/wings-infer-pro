#!/bin/bash
set -o errexit
set -o xtrace

# 日志  对应  /var/log/fusiononecenter/aispace/serving-pod/${POD_NAME}
LOG_PATH=/var/log/wings
enable_offload=false

CUR_PATH=$(cd "$(dirname "$0")" || exit; pwd)

if [ ! -f "${CUR_PATH}/master.env" ]; then
  echo "Mooncake master environment is missing: ${CUR_PATH}/master.env" >&2
  exit 1
fi
source "${CUR_PATH}/master.env"

function log() {
  exec_hostname=$(cat /etc/hostname)
  # 获取毫秒级时间戳
  timestamp=$(date +"%Y-%m-%d:%H:%M:%S.%3N")
  echo $timestamp [$1] [$exec_hostname] [$2]
  echo $timestamp [$1] [$exec_hostname] [$2] >>$LOG_PATH/mooncake_master_setup.log
}

function set_env() {
  export MOONCAKE_MASTER_EVICTION_HIGH_WATERMARK_RATIO="${MOONCAKE_MASTER_EVICTION_HIGH_WATERMARK_RATIO:-0.9}"
  export MOONCAKE_MASTER_EVICTION_RATIO="${MOONCAKE_MASTER_EVICTION_RATIO:-0.05}"

  # 磁盘卸载开关由 master.env 的 ENABLE_KV_DISK_OFFLOAD 决定(env.yaml 默认 false,MaaS 覆盖)
  case "${ENABLE_KV_DISK_OFFLOAD:-false}" in
    true|TRUE|True|1) enable_offload=true ;;
    false|FALSE|False|0|"") enable_offload=false ;;
    *)
      log error "master.env非法值: ENABLE_KV_DISK_OFFLOAD=${ENABLE_KV_DISK_OFFLOAD} (期望 true/false)"
      exit 1
      ;;
  esac
  log info "mooncake_master enable-offload=${enable_offload} (ENABLE_KV_DISK_OFFLOAD=${ENABLE_KV_DISK_OFFLOAD:-})"
  log info "MOONCAKE_MASTER_EVICTION_HIGH_WATERMARK_RATIO=$MOONCAKE_MASTER_EVICTION_HIGH_WATERMARK_RATIO"
  log info "MOONCAKE_MASTER_EVICTION_RATIO=$MOONCAKE_MASTER_EVICTION_RATIO"

}

function pre_handler() {
  # 启动master的适配
  cp $(pip3 show fusionone_xcache_npu | grep "Location: " | awk -F " " '{print $2}')/mooncake/ascend_transport.so /usr/local/bin/
  cp /usr/local/Ascend/cann/$(uname -m)-linux/lib64/device/lib64/libascend_hal.so /usr/local/bin/
  export LD_LIBRARY_PATH=/usr/local/bin:$LD_LIBRARY_PATH
}

# 这个是个阻塞性的进程
function start_server() {
  mooncake_master \
    --enable_http_metadata_server=true \
    --http_metadata_server_host=0.0.0.0 \
    --http_metadata_server_port=10080 \
    --rpc_thread_num=64 \
    --metrics_port=9003 \
    --enable_metric_reporting=true \
    --enable-offload=${enable_offload} \
    --log_dir=${LOG_PATH} \
    --logtostderr=false \
    --eviction_high_watermark_ratio="$MOONCAKE_MASTER_EVICTION_HIGH_WATERMARK_RATIO" \
    --eviction_ratio="$MOONCAKE_MASTER_EVICTION_RATIO" \
    --promotion_on_hit=true \
    >>${LOG_PATH}/mooncake_master_setup.log 2>&1
}

# 进程退出后的重启间隔(秒), 可通过环境变量 RESTART_INTERVAL 覆盖
RESTART_INTERVAL="${RESTART_INTERVAL:-5}"

# 进程守护: 监听 start_server, 退出后自动重启
function monitor_server() {
  local restart_count=0
  while true; do
    # start_server 退出(无论正常/异常)都重启; 用 || true 屏蔽 errexit, 避免脚本随进程一起退出
    start_server || true
    restart_count=$((restart_count + 1))
    log warn "mooncake_master process exited, restarting (count=${restart_count}) in ${RESTART_INTERVAL}s"
    sleep "${RESTART_INTERVAL}"
  done
}

function main() {
  log info "================ Starting mooncake_master ================"
  set_env
  pre_handler
  monitor_server
}

main
