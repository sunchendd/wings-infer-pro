# 稀疏 sparse — 变体输出样本

> 由 `smart_accel_io.py --save-samples` 生成。每个变体取一条**代表性模型路径**,隔离测试(仅开该特性 + 该变体)后 `func_smart_accel` 的完整输出。
> 测试用占位输入:草稿路径=`/dummy/draft-model`、内存卸载容量=128 GB、磁盘=512 GB @ `/var/cache/lmcache`。
> offload 的 `files:` 配置文件写入临时目录(此处仅展示生成的 pre_serve 命令与 env/cli)。


## `accuracy_first`  (14 路径)

- **代表路径:** `vllm/v0.22.0/rtx_pro_5000_48G/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-fp8.yaml`
- **选中 scheme:** `accuracy_first` (预期 `accuracy_first`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "hf_overrides": {
    "use_index_cache": true,
    "index_topk_freq": 4
  }
}
```

---

## `performance_first`  (14 路径)

- **代表路径:** `vllm/v0.22.0/rtx_pro_5000_48G/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-fp8.yaml`
- **选中 scheme:** `performance_first` (预期 `performance_first`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "hf_overrides": {
    "use_index_cache": true,
    "index_topk_freq": 8
  }
}
```

---
