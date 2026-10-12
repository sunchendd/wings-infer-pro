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
    export MOONCAKE_OFFLOAD_BUCKET_MAX_TOTAL_SIZE=$((KV_DISK_OFFLOAD_SIZE * 1024 * 1024 * 1024))
    export MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES=$((12 * 1024 * 1024 * 1024))
    # 配置buffer_size 和心跳间隔
    export MOONCAKE_OFFLOAD_HEARTBEAT_INTERVAL_SECONDS=3
    # kv最小切片大小
    export MOONCAKE_OFFLOAD_SLICE_MIN_THRESHOLD=$((100 * 1024 * 1024))
  fi


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

# Ascend/HCCL 通信与运行时环境变量
function set_ascend_env() {
  # ============================================================================
  # 派生变量：local_ip（Pod IP）、nic_name（通信网卡）、可见NPU。
  # 均在容器内部探测，不依赖外部传入。
  # ============================================================================

  # 通信 IP：从 hostname -i 取第一个非 127.0.0.1 的地址
  local_ip=$(hostname -i | awk '{for(i=1;i<=NF;i++) if($i!="127.0.0.1") print $i; exit}')
  export HCCL_IF_IP="$local_ip"

  # 通信网卡：用 ifconfig 按本地 IP 反查接口名，兜底 eth0
  nic_name=$(ifconfig 2>/dev/null | grep -B1 "$local_ip" | grep -o "^[a-zA-Z0-9]*" | head -n1)
  nic_name="${nic_name:-eth0}"
  export GLOO_SOCKET_IFNAME="$nic_name"
  export TP_SOCKET_IFNAME="$nic_name"
  export HCCL_SOCKET_IFNAME="$nic_name"

  # 可见 NPU：优先外部指定的 ASCEND_RT_VISIBLE_DEVICES；
  # 否则用 npu-smi info -l 的 Total Count 生成 0,1,...,N-1；命令不可用时兜底单卡 "0"
  if [ -z "${ASCEND_RT_VISIBLE_DEVICES:-}" ]; then
    local total_count
    total_count=$(npu-smi info -l 2>/dev/null | awk '/Total Count/{getline; gsub(/[^0-9]/,"",$0); print $0; exit}')
    if [ -n "$total_count" ] && [ "$total_count" -ge 1 ]; then
      local devices="" i
      for ((i=0; i<total_count; i++)); do
        if [ -n "$devices" ]; then devices="$devices,"; fi
        devices="${devices}${i}"
      done
      export ASCEND_RT_VISIBLE_DEVICES="$devices"
    else
      export ASCEND_RT_VISIBLE_DEVICES="0"
    fi
  fi

  export HCCL_INTRA_ROCE_ENABLE=1
  export HCCL_RDMA_TIMEOUT=17
  export HCCL_CONNECT_TIMEOUT=1800
  export HCCL_OP_EXPANSION_MODE="AIV"
  export HCCL_BUFFSIZE="${HCCL_BUFFSIZE:-400}"
  export HCCL_NPU_SOCKET_PORT_RANGE="${HCCL_NPU_SOCKET_PORT_RANGE:-20000-21000}"

  export ASCEND_CONNECT_TIMEOUT=60000
  export ASCEND_TRANSFER_TIMEOUT=60000
  export ASCEND_AUTO_CONNECT=1
  export ASCEND_AGGREGATE_ENABLE=1
  export ASCEND_TRANSPORT_PRINT=1
  export ASCEND_A3_ENABLE=1
  if [ -z "${ASCEND_GLOBAL_RESOURCE_CONFIG:-}" ]; then
    export ASCEND_GLOBAL_RESOURCE_CONFIG='{"comm_resource_config.listen_port":26667, "comm_resource_config.protocol_desc": ["roce:device"]}'
  fi

  export ACL_OP_INIT_MODE=1
  export OMP_PROC_BIND=false
  export OMP_NUM_THREADS=1
  export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
  export PYTHONHASHSEED=0
  export VLLM_MOONCAKE_ABORT_REQUEST_TIMEOUT=120
  export VLLM_ASCEND_ENABLE_FUSED_MC2=1
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

# 等待 mooncake master 就绪:store 依赖 master 的 RPC/metadata 服务,未就绪时启动会失败。
# 探测 HTTP metadata 端口(任意 HTTP 响应即就绪;无 curl 时退化为 /dev/tcp 连通探测),
# 超时(MOONCAKE_MASTER_WAIT_TIMEOUT,默认 300s)后退出。
function wait_for_master() {
  local port="${MOONCAKE_MASTER_HTTP_PORT:-10080}"
  local timeout_s="${MOONCAKE_MASTER_WAIT_TIMEOUT:-300}"
  local start_ts=$(date +%s)
  log info "Waiting for mooncake master at http://${SERVICE_NAME}:${port}/ (timeout=${timeout_s}s)"
  while true; do
    if curl -s -o /dev/null --max-time 3 "http://${SERVICE_NAME}:${port}/" 2>/dev/null ||
      timeout 3 bash -c 'exec 3<>/dev/tcp/$1/$2' _ "$SERVICE_NAME" "$port" 2>/dev/null; then
      log info "Mooncake master is ready (elapsed $(($(date +%s) - start_ts))s)"
      return 0
    fi
    if [ $(($(date +%s) - start_ts)) -ge "$timeout_s" ]; then
      log error "Mooncake master not ready after ${timeout_s}s; aborting mooncake store startup"
      exit 1
    fi
    sleep 5
  done
}

function start_server() {
  # 服务启动：仅当传了 KV_DISK_OFFLOAD_SIZE 才带 --offload-dir，否则不启用卸载存储
  if [ -n "$KV_DISK_OFFLOAD_SIZE" ]; then
    python3 ${STORE_PY_FILE} \
      --local-host "$RANK_IP" \
      --protocol "$KV_PROTOCOL" \
      --metadata-server "P2PHANDSHAKE" \
      --master-server "${SERVICE_NAME}:50051" \
      --global-segment-size "$GLOBAL_SEGMENT_SIZE_MB" \
      --device-name "" \
      --offload-dir "$MOONCAKE_OFFLOAD_FILE_STORAGE_PATH" \
      >>${LOG_PATH}/mooncake_store_setup.log 2>&1 &
  else
    python3 ${STORE_PY_FILE} \
      --local-host "$RANK_IP" \
      --protocol "$KV_PROTOCOL" \
      --metadata-server "P2PHANDSHAKE" \
      --master-server "${SERVICE_NAME}:50051" \
      --global-segment-size "$GLOBAL_SEGMENT_SIZE_MB" \
      --device-name "" \
      >>${LOG_PATH}/mooncake_store_setup.log 2>&1 &
  fi
}

function main() {
  log info "================ Starting mooncake_store_ascend ================"
  check_param
  set_env
  set_ascend_env
  log_param
  wait_for_master
  start_server
  log info "================ Finish mooncake_store_ascend ================"
}


main
