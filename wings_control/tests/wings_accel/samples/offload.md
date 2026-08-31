# 卸载 offload — 变体输出样本

> 由 `smart_accel_io.py --save-samples` 生成。每个变体取一条**代表性模型路径**,隔离测试(仅开该特性 + 该变体)后 `func_smart_accel` 的完整输出。
> 测试用占位输入:草稿路径=临时 stub 目录(本地目录契约,样本中统一展示为`/dummy/draft-model`)、内存卸载容量=128 GB、磁盘=512 GB @ `/var/cache/lmcache`。
> offload 的 `files:` 仅生成并校验文件计划；此处展示生成的 pre_serve 命令与 env/cli。


## `other:?`  (27 路径)

- **代表路径:** `vllm/v0.23.0/h20_141G/models/DeepSeek-V3.2/DeepSeek-V3.2-Exp.yaml`
- **选中 scheme:** `cpu` (预期 `cpu`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "kv_offloading_backend": "native",
  "kv_offloading_size": "128"
}
```

---

## `backend:memcache`  (2 路径)

- **代表路径:** `vllm-ascend/v0.21.0rc/ascend-a3/models/GLM-5.2/GLM-5.2-w4a8.yaml`
- **选中 scheme:** `cpu` (预期 `cpu`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "kv_transfer_config": {
    "kv_connector": "AscendStoreConnector",
    "kv_role": "kv_both",
    "kv_load_failure_policy": "recompute",
    "kv_connector_extra_config": {
      "lookup_rpc_port": "0",
      "backend": "memcache"
    }
  }
}
```

**envs:**
```
MMC_META_CONFIG_PATH=/shared-volume/mmc_meta.conf
MMC_LOCAL_CONFIG_PATH=/shared-volume/mmc_local.conf
```

**pre_serve(所有节点):**
```sh
mkdir -p /shared-volume
export MASTER_IP="${MASTER_IP:-127.0.0.1}" RANK_IP="${RANK_IP:-127.0.0.1}"
if command -v envsubst >/dev/null 2>&1 && envsubst '${MASTER_IP} ${RANK_IP}' < /shared-volume/mmc_local.conf > /shared-volume/mmc_local.conf.tmp 2>/dev/null; then :; else sed "s|\${MASTER_IP}|$MASTER_IP|g;s|\${RANK_IP}|$RANK_IP|g" /shared-volume/mmc_local.conf > /shared-volume/mmc_local.conf.tmp; fi
mv /shared-volume/mmc_local.conf.tmp /shared-volume/mmc_local.conf
```

**pre_serve_master(仅 master):**
```sh
export MASTER_IP="${MASTER_IP:-127.0.0.1}" RANK_IP="${RANK_IP:-127.0.0.1}"
if command -v envsubst >/dev/null 2>&1 && envsubst '${MASTER_IP} ${RANK_IP}' < /shared-volume/mmc_meta.conf > /shared-volume/mmc_meta.conf.tmp 2>/dev/null; then :; else sed "s|\${MASTER_IP}|$MASTER_IP|g;s|\${RANK_IP}|$RANK_IP|g" /shared-volume/mmc_meta.conf > /shared-volume/mmc_meta.conf.tmp; fi
mv /shared-volume/mmc_meta.conf.tmp /shared-volume/mmc_meta.conf
bash /shared-volume/start_kv_serve.sh &
```

---

## `backend:mooncake`  (2 路径)

- **代表路径:** `vllm-ascend/v0.21.0rc/ascend-a2/models/MiniMax-M2.7/MiniMax-M2.7-w8a8.yaml`
- **选中 scheme:** `cpu` (预期 `cpu`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "kv_transfer_config": {
    "kv_connector": "AscendStoreConnector",
    "kv_role": "kv_both",
    "kv_load_failure_policy": "recompute",
    "kv_connector_extra_config": {
      "lookup_rpc_port": "1",
      "backend": "mooncake"
    }
  }
}
```

**envs:**
```
MOONCAKE_CONFIG_PATH=/shared-volume/mooncake.json
LD_LIBRARY_PATH=/usr/local/lib:${LD_LIBRARY_PATH:-}
```

**pre_serve(所有节点):**
```sh
mkdir -p /shared-volume
export MASTER_IP="${MASTER_IP:-127.0.0.1}" RANK_IP="${RANK_IP:-127.0.0.1}"
if command -v envsubst >/dev/null 2>&1 && envsubst '${MASTER_IP} ${RANK_IP}' < /shared-volume/mooncake.json > /shared-volume/mooncake.json.tmp 2>/dev/null; then :; else sed "s|\${MASTER_IP}|$MASTER_IP|g;s|\${RANK_IP}|$RANK_IP|g" /shared-volume/mooncake.json > /shared-volume/mooncake.json.tmp; fi
mv /shared-volume/mooncake.json.tmp /shared-volume/mooncake.json
```

**pre_serve_master(仅 master):**
```sh
bash /shared-volume/start_kv_serve.sh &
```

---

## `lmcache-ascend`  (2 路径)

- **代表路径:** `vllm-ascend/v0.21.0rc/ascend-a2/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash.yaml`
- **选中 scheme:** `cpu` (预期 `cpu`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "kv_transfer_config": {
    "kv_connector": "LMCacheAscendConnectorV1Dynamic",
    "kv_role": "kv_both",
    "kv_connector_module_path": "lmcache_ascend.integration.vllm.lmcache_ascend_connector_v1"
  }
}
```

**envs:**
```
LMCACHE_TRACK_USAGE=false
LMCACHE_LOCAL_CPU=True
LMCACHE_MAX_LOCAL_CPU_SIZE=128
LMCACHE_LOG_LEVEL=INFO
LMCACHE_USE_LAYERWISE=False
LMCACHE_NUMA_MODE=auto
LMCACHE_CHUNK_SIZE=1024
LMCACHE_EXTRA_CONFIG={"save_only_first_rank": false}
LMCACHE_LOOKUP_SERVER_WORKER_IDS=0
```

**packages:** lmcache-ascend:v0.4.5

---

## `lmcache:cpu`  (2 路径)

- **代表路径:** `vllm/v0.23.0/rtx_pro_5000_48G/models/MiniMax-M2.7/MiniMax-M2.7-nvfp4.yaml`
- **选中 scheme:** `cpu` (预期 `cpu`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "kv_transfer_config": {
    "kv_connector": "LMCacheConnectorV1",
    "kv_role": "kv_both",
    "kv_load_failure_policy": "recompute"
  }
}
```

**envs:**
```
LMCACHE_LOCAL_CPU=True
LMCACHE_MAX_LOCAL_CPU_SIZE=128
LMCACHE_CHUNK_SIZE=256
LMCACHE_EXTRA_CONFIG={"use_odirect": true}
LMCACHE_PRE_CACHING_HASH_ALGORITHM=sha256_cbor_64bit
```

---

## `lmcache:cpu_disk`  (2 路径)

- **代表路径:** `vllm/v0.23.0/rtx_pro_5000_48G/models/MiniMax-M2.7/MiniMax-M2.7-nvfp4.yaml`
- **选中 scheme:** `cpu_disk` (预期 `cpu_disk`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "kv_transfer_config": {
    "kv_connector": "LMCacheConnectorV1",
    "kv_role": "kv_both",
    "kv_load_failure_policy": "recompute"
  }
}
```

**envs:**
```
LMCACHE_LOCAL_CPU=True
LMCACHE_MAX_LOCAL_CPU_SIZE=128
LMCACHE_CHUNK_SIZE=256
LMCACHE_EXTRA_CONFIG={"use_odirect": true}
LMCACHE_PRE_CACHING_HASH_ALGORITHM=sha256_cbor_64bit
LMCACHE_LOCAL_DISK=/var/cache/lmcache
LMCACHE_MAX_LOCAL_DISK_SIZE=512
```

---
