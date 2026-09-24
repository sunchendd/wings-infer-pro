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

  # KV_DISK_OFFLOAD_SIZE 为可选参数：未传时不启用 offload，跳过校验
  if [ -n "$KV_DISK_OFFLOAD_SIZE" ]; then
    if ! [[ "$KV_DISK_OFFLOAD_SIZE" =~ ^[0-9]+$ ]] || [ "$KV_DISK_OFFLOAD_SIZE" -le 0 ]; then
      echo "Error: KV_DISK_OFFLOAD_SIZE must be a positive integer."
      exit 1
    fi
  fi
}

# 设置环境变量
function set_env() {
  # 配置存储
  export MOONCAKE_OFFLOAD_SLICE_ENABLE=true
  export MOONCAKE_OFFLOAD_OFFSET_ALLOCATOR_EVICTION_POLICY=fifo
  export MOONCAKE_OFFLOAD_STORAGE_BACKEND_DESCRIPTOR="bucket_storage_backend"
  # 传了 KV_DISK_OFFLOAD_SIZE 才启用 offload 相关容量配置，否则不配置
  if [ -n "$KV_DISK_OFFLOAD_SIZE" ]; then
    export MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES=$((KV_DISK_OFFLOAD_SIZE * 1024 * 1024 * 1024))
    export MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES=$((12 * 1024 * 1024 * 1024))
    # 配置buffer_size 和心跳间隔
    export MOONCAKE_OFFLOAD_HEARTBEAT_INTERVAL_SECONDS=3
    # kv最小切片大小
    export MOONCAKE_OFFLOAD_SLICE_MIN_THRESHOLD=$((100 * 1024 * 1024))
  fi

  # ssd数据持久化配置（可选）
  #export MOONCAKE_OFFLOAD_METADATA_PERSISTENCE=1
  # 元数据空间大小，单位MB，默认10G
  #export MOONCAKE_OFFLOAD_META_REGION_SIZE_MB=1000
  # KV数据空间大小。 单位MB，默认MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES - MOONCAKE_OFFLOAD_META_REGION_SIZE_MB
  #export MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES=1153433600000
  # 可选。 日志文件最多保存多少条日志，就要压缩成快照文件，默认 10万
  #export MOONCAKE_OFFLOAD_DATA_REGION_SIZE_MB=1000000

  # 启动mooncake_store
  export RANK_IP=$(hostname -i | awk '{for(i=1;i<=NF;i++) if($i!="127.0.0.1") print $i; exit}')

  # offload路径固定为 /tmp/kvcacheoffload，无需拼接路径
  export MC_STORE_HTTP_PORT=9300
  export MOONCAKE_OFFLOAD_FILE_STORAGE_PATH="${OFFLOAD_CLEANUP_DIR}"

  # global-segment-size 单位转换为 MB (mooncake_store.py 期望单位为 MB，如 25GB -> 25600MB)
  export GLOBAL_SEGMENT_SIZE_MB=$((KV_MEM_OFFLOAD_SIZE * 1024))
  # 设置服务名称
  export SERVICE_NAME="mooncake-service-${SERVING_CONFIG_ID}"
}

function log_param() {
  # 启动服务前参数打印
  log info "RANK_IP=$RANK_IP"
  log info "MC_STORE_HTTP_PORT=$MC_STORE_HTTP_PORT"
  log info "MOONCAKE_OFFLOAD_FILE_STORAGE_PATH=$MOONCAKE_OFFLOAD_FILE_STORAGE_PATH"
  log info "KV_PROTOCOL=$KV_PROTOCOL"
  log info "SERVICE_NAME=$SERVICE_NAME"
  log info "KV_MEM_OFFLOAD_SIZE=$KV_MEM_OFFLOAD_SIZE (${GLOBAL_SEGMENT_SIZE_MB}MB)"
  log info "KV_DISK_OFFLOAD_SIZE=$KV_DISK_OFFLOAD_SIZE (${MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES} Bytes)"
  log info "MOONCAKE_OFFLOAD_SLICE_ENABLE=$MOONCAKE_OFFLOAD_SLICE_ENABLE"
  log info "MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES=$MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES"
}

# 这个是个阻塞的进程
function start_server() {
  # 服务启动：仅当传了 KV_DISK_OFFLOAD_SIZE 才带 --offload-dir，否则不启用卸载存储
  if [ -n "$KV_DISK_OFFLOAD_SIZE" ]; then
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
