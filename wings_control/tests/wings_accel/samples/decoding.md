# 投机 decoding — 变体输出样本

> 由 `smart_accel_io.py --save-samples` 生成。每个变体取一条**代表性模型路径**,隔离测试(仅开该特性 + 该变体)后 `func_smart_accel` 的完整输出。
> 测试用占位输入:草稿路径=`/dummy/draft-model`、内存卸载容量=128 GB、磁盘=512 GB @ `/var/cache/lmcache`。
> offload 的 `files:` 配置文件写入临时目录(此处仅展示生成的 pre_serve 命令与 env/cli)。


## `mtp`  (466 路径)

- **代表路径:** `vllm/v0.22.0/rtx_pro_5000_48G/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-fp8.yaml`
- **选中 scheme:** `mtp` (预期 `mtp`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "mtp",
    "num_speculative_tokens": 2
  }
}
```

---

## `draft_model`  (179 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/gemma-4-12B-it/gemma-4-12B-it-bf16.yaml`
- **选中 scheme:** `draft_model` (预期 `draft_model`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "model": "/dummy/draft-model",
    "num_speculative_tokens": 4
  }
}
```

---

## `eagle3`  (106 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/Kimi-K2.5/Kimi-K2.5-int4.yaml`
- **选中 scheme:** `eagle3` (预期 `eagle3`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "eagle3",
    "model": "/dummy/draft-model",
    "num_speculative_tokens": 3
  }
}
```

---

## `step3p5_mtp`  (36 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/Step-3.5-Flash/Step-3.5-Flash-bf16.yaml`
- **选中 scheme:** `step3p5_mtp` (预期 `step3p5_mtp`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "step3p5_mtp",
    "num_speculative_tokens": 1
  },
  "hf_overrides": {
    "num_nextn_predict_layers": 1
  }
}
```

---

## `eagle`  (22 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/Mistral-Medium-3.5-128B/Mistral-Medium-3.5-128B-fp8.yaml`
- **选中 scheme:** `eagle` (预期 `eagle`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "eagle",
    "model": "/dummy/draft-model",
    "num_speculative_tokens": 3,
    "max_model_len": 65536
  }
}
```

---

## `qwen3_next_mtp`  (22 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/Qwen3-Next-80B-A3B-Instruct/Qwen3-Next-80B-A3B-Instruct-bf16.yaml`
- **选中 scheme:** `qwen3_next_mtp` (预期 `qwen3_next_mtp`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "qwen3_next_mtp",
    "num_speculative_tokens": 2
  }
}
```

---

## `dflash`  (19 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/Laguna-XS-2.1/Laguna-XS-2.1-bf16.yaml`
- **选中 scheme:** `dflash` (预期 `dflash`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "dflash",
    "model": "/dummy/draft-model",
    "num_speculative_tokens": 15
  }
}
```

---

## `ernie_mtp`  (18 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/ERNIE-4.5-21B-A3B-PT/ERNIE-4.5-21B-A3B-PT-300b.yaml`
- **选中 scheme:** `ernie_mtp` (预期 `ernie_mtp`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "ernie_mtp",
    "model": "/dummy/draft-model",
    "num_speculative_tokens": 1
  }
}
```

---

## `qwen3_5_mtp`  (18 路径)

- **代表路径:** `vllm/v0.23.0/rtx_pro_5000_48G/models/Qwen3.5-122B-A10B/Qwen3.5-122B-A10B-bf16.yaml`
- **选中 scheme:** `qwen3_5_mtp` (预期 `qwen3_5_mtp`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "qwen3_5_mtp",
    "num_speculative_tokens": 1
  }
}
```

---

## `deepseek_mtp`  (14 路径)

- **代表路径:** `vllm-ascend/v0.21.0rc/ascend-a2/models/DeepSeek-V3.2/DeepSeek-V3.2.yaml`
- **选中 scheme:** `deepseek_mtp` (预期 `deepseek_mtp`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "deepseek_mtp",
    "num_speculative_tokens": 3
  }
}
```

---

## `suffix`  (8 路径)

- **代表路径:** `vllm/v0.23.0/rtx_pro_5000_48G/models/MiniMax-M2.5/MiniMax-M2.5-nvfp4.yaml`
- **选中 scheme:** `suffix` (预期 `suffix`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "suffix",
    "num_speculative_tokens": 10
  }
}
```

---

## `dspark`  (7 路径)

- **代表路径:** `vllm/v0.23.0/b200/models/DeepSeek-V4-Pro/DeepSeek-V4-Pro-dspark.yaml`
- **选中 scheme:** `dspark` (预期 `dspark`) ✓
- **降级:** 无

**engine_config:**
```json
{
  "speculative_config": {
    "method": "dspark",
    "model": "/dummy/draft-model",
    "num_speculative_tokens": 7,
    "draft_sample_method": "greedy"
  }
}
```

---
