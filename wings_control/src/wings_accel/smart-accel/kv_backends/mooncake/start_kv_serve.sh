#!/usr/bin/env bash
# mooncake master daemon(仅 master 节点起;framework 自动 bash <path> &,不监听端口)。
cd /vllm-workspace/Mooncake
mooncake_master --port 50088 \
    --eviction_high_watermark_ratio 0.9 \
    --eviction_ratio 0.1 \
    --default_kv_lease_ttl 11000
