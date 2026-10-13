#!/bin/bash
set -o errexit
set -o xtrace

# 日志  对应  /var/log/fusiononecenter/aispace/serving-pod/${POD_NAME}
LOG_PATH=/var/log/wings

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

# 这个是个阻塞性的进程
function start_server() {
  # 磁盘卸载开关由 master.env 的 ENABLE_KV_DISK_OFFLOAD 决定(env.yaml 默认 false,MaaS 覆盖)
  local enable_offload=false
  case "${ENABLE_KV_DISK_OFFLOAD:-false}" in
    true|TRUE|True|1) enable_offload=true ;;
    false|FALSE|False|0|"") enable_offload=false ;;
    *)
      log error "master.env非法值: ENABLE_KV_DISK_OFFLOAD=${ENABLE_KV_DISK_OFFLOAD} (期望 true/false)"
      exit 1
      ;;
  esac
  log info "mooncake_master enable-offload=${enable_offload} (ENABLE_KV_DISK_OFFLOAD=${ENABLE_KV_DISK_OFFLOAD:-})"
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
    --eviction_high_watermark_ratio=0.7 \
    --eviction_ratio=0.2 \
    --promotion_on_hit=true \
    >>${LOG_PATH}/mooncake_master_setup.log 2>&1
}

function main() {
  log info "================ Starting mooncake_master ================"
  start_server
  log info "================ Finish mooncake_master ================"
}

main
