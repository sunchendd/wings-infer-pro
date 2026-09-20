#!/bin/bash
set -e
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
export TORCH_DEVICE_BACKEND_AUTOLOAD=0
export VLLM_PLUGINS=""
mkdir -p /var/log/wings

PROXY_PORT=${PROXY_PORT:-8000}
# ENGINE_PORT 是 engine backend 端口基座：prefill 直用基座，decode 实际端口 = 基座 + local_rank。
ENGINE_PORT=${ENGINE_PORT:-17000}
DECODE_LOCAL_DP=${DECODE_LOCAL_DP:-2}
: "${PREFILL_HOSTS:?PREFILL_HOSTS is required}"
: "${DECODE_HOSTS:?DECODE_HOSTS is required}"
IFS=',' read -r -a prefiller_hosts <<< "$PREFILL_HOSTS"
IFS=',' read -r -a decoder_hosts <<< "$DECODE_HOSTS"
prefiller_ports=()
for _ in "${prefiller_hosts[@]}"; do
  prefiller_ports+=("$ENGINE_PORT")
done
decoder_ports=()
i=0
for _ in "${decoder_hosts[@]}"; do
  decoder_ports+=("$((ENGINE_PORT + i % DECODE_LOCAL_DP))")
  i=$((i + 1))
done

exec python3 /vllm-workspace/vllm-ascend/examples/disaggregated_prefill_v1/load_balance_proxy_server_example.py \
  --port "$PROXY_PORT" \
  --host 0.0.0.0 \
  --prefiller-hosts "${prefiller_hosts[@]}" \
  --prefiller-ports "${prefiller_ports[@]}" \
  --decoder-hosts "${decoder_hosts[@]}" \
  --decoder-ports "${decoder_ports[@]}"
