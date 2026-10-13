#!/bin/bash
set -o errexit
set -o xtrace

# 日志  对应  /var/log/fusiononecenter/aispace/serving-pod/${POD_NAME}
LOG_PATH=/var/log/wings

CUR_PATH=$(cd "$(dirname "$0")" || exit; pwd)

function log() {
  exec_hostname=$(cat /etc/hostname)
  # 获取毫秒级时间戳
  timestamp=$(date +"%Y-%m-%d:%H:%M:%S.%3N")
  echo $timestamp [$1] [$exec_hostname] [$2]
  echo $timestamp [$1] [$exec_hostname] [$2] >>$LOG_PATH/mooncake_store_setup.log
}

# 校验 client.env 是否存在，未找到则记录日志并退出
if [ ! -f "${CUR_PATH}/client.env" ]; then
  log error "client.env not found, please provide it before starting."
  exit 1
fi

source ${CUR_PATH}/client.env

# 从环境变量读取
# 协议
KV_PROTOCOL="${KV_PROTOCOL}"
# 实例ID 用于拼接ServiceName
SERVING_CONFIG_ID="${SERVING_CONFIG_ID}"
# 内存单位GB
KV_MEM_OFFLOAD_SIZE="${KV_MEM_OFFLOAD_SIZE}"
# 磁盘大小GB
KV_DISK_OFFLOAD_SIZE="${KV_DISK_OFFLOAD_SIZE}"
# 磁盘卸载开关:由 ENABLE_KV_DISK_OFFLOAD 决定,不再以 KV_DISK_OFFLOAD_SIZE 非空判断
# (env.yaml 容量默认 0,size 非空/非 0 不能代表用户开启了磁盘卸载)
DISK_OFFLOAD_ENABLED=false
case "${ENABLE_KV_DISK_OFFLOAD:-}" in
  true|TRUE|True|1) DISK_OFFLOAD_ENABLED=true ;;
  false|FALSE|False|0|"") DISK_OFFLOAD_ENABLED=false ;;
  *)
    log error "client.env非法值: ENABLE_KV_DISK_OFFLOAD=${ENABLE_KV_DISK_OFFLOAD} (期望 true/false)"
    exit 1
    ;;
esac

# 其他参数
OFFLOAD_CLEANUP_DIR="/tmp/kvcacheoffload"
STORE_PY_FILE=${CUR_PATH}/mooncake_store.py

# 参数效验
function check_param() {
  # 从 client.env 获取的参数不能为空
  if [ -z "$KV_PROTOCOL" ]; then
    log error "client.env未设置: KV_PROTOCOL"
    exit 1
  fi

  if [ -z "$SERVING_CONFIG_ID" ]; then
    log error "client.env未设置: SERVING_CONFIG_ID"
    exit 1
  fi

  if [ -z "$KV_MEM_OFFLOAD_SIZE" ]; then
    log error "client.env未设置: KV_MEM_OFFLOAD_SIZE"
    exit 1
  fi

  if [[ "$KV_PROTOCOL" != "rdma" && "$KV_PROTOCOL" != "tcp" && "$KV_PROTOCOL" != "ascend" ]]; then
    log error "Error: KV_PROTOCOL must be either rdma, tcp or ascend."
    exit 1
  fi

  if ! [[ "$KV_MEM_OFFLOAD_SIZE" =~ ^[0-9]+$ ]] || [ "$KV_MEM_OFFLOAD_SIZE" -le 0 ]; then
    echo "Error: KV_MEM_OFFLOAD_SIZE must be a positive integer."
    exit 1
  fi

  # 磁盘卸载开启时容量必填且必须为正整数(GB);关闭时不校验容量
  if [ "$DISK_OFFLOAD_ENABLED" = "true" ]; then
    if [ -z "$KV_DISK_OFFLOAD_SIZE" ]; then
      log error "client.env未设置: KV_DISK_OFFLOAD_SIZE (ENABLE_KV_DISK_OFFLOAD=true 时必填)"
      exit 1
    fi
    if ! [[ "$KV_DISK_OFFLOAD_SIZE" =~ ^[0-9]+$ ]] || [ "$KV_DISK_OFFLOAD_SIZE" -le 0 ]; then
      log error "Error: KV_DISK_OFFLOAD_SIZE must be a positive integer when ENABLE_KV_DISK_OFFLOAD=true."
      exit 1
    fi
  fi
}

# 设置环境变量
function set_env() {
  export MOONCAKE_OFFLOAD_SLICE_ENABLE=true
  export MOONCAKE_OFFLOAD_OFFSET_ALLOCATOR_EVICTION_POLICY=fifo
  export MOONCAKE_OFFLOAD_STORAGE_BACKEND_DESCRIPTOR="bucket_storage_backend"
  export MOONCAKE_OFFLOAD_FILE_STORAGE_PATH="${OFFLOAD_CLEANUP_DIR}"

  # 配置存储:offload 专属环境变量仅在 ENABLE_KV_DISK_OFFLOAD=true 时导出
  if [ "$DISK_OFFLOAD_ENABLED" = "true" ]; then
    export MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES=$((KV_DISK_OFFLOAD_SIZE * 1024 * 1024 * 1024))
    export MOONCAKE_OFFLOAD_BUCKET_MAX_TOTAL_SIZE=$((KV_DISK_OFFLOAD_SIZE * 1024 * 1024 * 1024))
    export MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES=$((12 * 1024 * 1024 * 1024))
    # 配置buffer_size 和心跳间隔
    export MOONCAKE_OFFLOAD_HEARTBEAT_INTERVAL_SECONDS=3
    # kv最小切片大小
    export MOONCAKE_OFFLOAD_SLICE_MIN_THRESHOLD=$((100 * 1024 * 1024))
  fi

  # 启动存储服务前,先取本机对外地址
  export RANK_IP=$(hostname -i | awk '{for(i=1;i<=NF;i++) if($i!="127.0.0.1") print $i; exit}')
  # 卸载目录与存储端口固定,无需拼接
  export MC_STORE_HTTP_PORT=9300
  # 将内存容量换算为兆字节单位
  export GLOBAL_SEGMENT_SIZE_MB=$((KV_MEM_OFFLOAD_SIZE * 1024))
  # 设置服务名称
  export SERVICE_NAME="mooncake-service-${SERVING_CONFIG_ID}"
}

function log_param() {
  # 启动服务前参数打印
  log info "RANK_IP=$RANK_IP"
  log info "MC_STORE_HTTP_PORT=$MC_STORE_HTTP_PORT"
  log info "KV_PROTOCOL=$KV_PROTOCOL"
  log info "SERVICE_NAME=$SERVICE_NAME"
  log info "KV_MEM_OFFLOAD_SIZE=$KV_MEM_OFFLOAD_SIZE (${GLOBAL_SEGMENT_SIZE_MB}MB)"
  log info "ENABLE_KV_DISK_OFFLOAD=${ENABLE_KV_DISK_OFFLOAD:-} (disk offload ${DISK_OFFLOAD_ENABLED})"
  if [ "$DISK_OFFLOAD_ENABLED" = "true" ]; then
    log info "MOONCAKE_OFFLOAD_FILE_STORAGE_PATH=$MOONCAKE_OFFLOAD_FILE_STORAGE_PATH"
    log info "KV_DISK_OFFLOAD_SIZE=$KV_DISK_OFFLOAD_SIZE (${MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES} Bytes)"
    log info "MOONCAKE_OFFLOAD_SLICE_ENABLE=$MOONCAKE_OFFLOAD_SLICE_ENABLE"
    log info "MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES=$MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES"
  fi
}

# 这个是个阻塞的进程
function start_server() {
  # 服务启动：仅当 ENABLE_KV_DISK_OFFLOAD=true 才带 --offload-dir，否则不启用卸载存储
  if [ "$DISK_OFFLOAD_ENABLED" = "true" ]; then
    python3 ${STORE_PY_FILE} \
      --local-host "$RANK_IP" \
      --protocol "$KV_PROTOCOL" \
      --metadata-server "http://${SERVICE_NAME}:10080/metadata" \
      --master-server "${SERVICE_NAME}:50051" \
      --global-segment-size "$GLOBAL_SEGMENT_SIZE_MB" \
      --device-name "" \
      --offload-dir "$MOONCAKE_OFFLOAD_FILE_STORAGE_PATH" \
      >>${LOG_PATH}/mooncake_store_setup.log 2>&1
  else
    python3 ${STORE_PY_FILE} \
      --local-host "$RANK_IP" \
      --protocol "$KV_PROTOCOL" \
      --metadata-server "http://${SERVICE_NAME}:10080/metadata" \
      --master-server "${SERVICE_NAME}:50051" \
      --global-segment-size "$GLOBAL_SEGMENT_SIZE_MB" \
      --device-name "" \
      >>${LOG_PATH}/mooncake_store_setup.log 2>&1
  fi
}

function main() {
  log info "================ Starting mooncake_store ================"
  check_param
  set_env
  log_param
  start_server
  log info "================ Finish mooncake_store ================"
}

main
