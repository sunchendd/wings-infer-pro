#!/usr/bin/env bash
# Generate the vLLM Mooncake connector configuration from script fallback assets.
# The master is managed by Kubernetes; this script only writes this engine
# node's client-side configuration into the shared volume.
#
# Environment: sourced client.env (platform variables, verbatim names):
#   ENABLE_KV_OFFLOAD / ENABLE_DISTRIBUTED_KV_OFFLOAD / ENABLE_KV_DISK_OFFLOAD /
#   ENABLE_KV_MEM_OFFLOAD / KV_DISK_OFFLOAD_PATH / KV_DISK_OFFLOAD_SIZE /
#   KV_MEM_OFFLOAD_SIZE / KV_PROTOCOL / SERVING_CONFIG_ID
set -euo pipefail

CUR_PATH=$(cd "$(dirname "$0")" && pwd)
if [ ! -f "${CUR_PATH}/client.env" ]; then
    echo "Mooncake client environment is missing: ${CUR_PATH}/client.env" >&2
    exit 1
fi
source "${CUR_PATH}/client.env"

: "${SERVING_CONFIG_ID:?SERVING_CONFIG_ID is required for Mooncake script fallback}"
: "${KV_PROTOCOL:?KV_PROTOCOL is required for Mooncake script fallback}"
: "${KV_MEM_OFFLOAD_SIZE:?KV_MEM_OFFLOAD_SIZE is required for Mooncake script fallback}"
: "${ENABLE_KV_MEM_OFFLOAD:?ENABLE_KV_MEM_OFFLOAD is required for Mooncake script fallback}"

case "$SERVING_CONFIG_ID" in
    *[!a-z0-9-]* | -* | *- | '')
        echo "Mooncake JSON generation failed: invalid serving config id" >&2
        exit 2
        ;;
esac
case "$KV_PROTOCOL" in
    *[!a-z0-9_-]* | '')
        echo "Mooncake JSON generation failed: invalid protocol" >&2
        exit 2
        ;;
esac

output_dir="$SHARED_VOLUME_PATH/distributed_offload/mooncake_npu"
output_path="$output_dir/mooncake.json"
mkdir -p "$output_dir"
tmp_path="$(mktemp "$output_dir/.mooncake.json.XXXXXX")"
cleanup() {
    rm -f "$tmp_path"
}
trap cleanup EXIT

printf '%s\n' \
    '{' \
    '  "mode": "standalone-store",' \
    "  \"metadata_server\": \"P2PHANDSHAKE\"," \
    "  \"master_server_address\": \"mooncake-service-${SERVING_CONFIG_ID}:50051\"," \
    '  "global_segment_size": 0,' \
    "  \"protocol\": \"${KV_PROTOCOL}\"," \
    '  "device_name": "",' \
    '  "preferred_segment": false,' \
    '  "prefer_alloc_in_same_node": true,' \
    '  "enable_ssd_offload": false' \
    '}' > "$tmp_path"

mv -f "$tmp_path" "$output_path"
trap - EXIT
echo "Mooncake script fallback wrote configuration: $output_path"
