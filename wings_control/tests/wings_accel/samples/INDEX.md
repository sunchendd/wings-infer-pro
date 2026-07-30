# 路径覆盖样本索引

> 生成自 `smart_accel_io.py --save-samples`

> 目录: vllm, vllm-ascend   模型 YAML: 919


## 投机 decoding(12 变体)

- [mtp](./decoding.md#mtp) — 466 路径,代表 `vllm/v0.22.0/rtx_pro_5000_48G/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-fp8.yaml`
- [draft_model](./decoding.md#draft-model) — 179 路径,代表 `vllm/v0.23.0/b200/models/gemma-4-12B-it/gemma-4-12B-it-bf16.yaml`
- [eagle3](./decoding.md#eagle3) — 106 路径,代表 `vllm/v0.23.0/b200/models/Kimi-K2.5/Kimi-K2.5-int4.yaml`
- [step3p5_mtp](./decoding.md#step3p5-mtp) — 36 路径,代表 `vllm/v0.23.0/b200/models/Step-3.5-Flash/Step-3.5-Flash-bf16.yaml`
- [eagle](./decoding.md#eagle) — 22 路径,代表 `vllm/v0.23.0/b200/models/Mistral-Medium-3.5-128B/Mistral-Medium-3.5-128B-fp8.yaml`
- [qwen3_next_mtp](./decoding.md#qwen3-next-mtp) — 22 路径,代表 `vllm/v0.23.0/b200/models/Qwen3-Next-80B-A3B-Instruct/Qwen3-Next-80B-A3B-Instruct-bf16.yaml`
- [dflash](./decoding.md#dflash) — 19 路径,代表 `vllm/v0.23.0/b200/models/Laguna-XS-2.1/Laguna-XS-2.1-bf16.yaml`
- [ernie_mtp](./decoding.md#ernie-mtp) — 18 路径,代表 `vllm/v0.23.0/b200/models/ERNIE-4.5-21B-A3B-PT/ERNIE-4.5-21B-A3B-PT-300b.yaml`
- [qwen3_5_mtp](./decoding.md#qwen3-5-mtp) — 18 路径,代表 `vllm/v0.23.0/rtx_pro_5000_48G/models/Qwen3.5-122B-A10B/Qwen3.5-122B-A10B-bf16.yaml`
- [deepseek_mtp](./decoding.md#deepseek-mtp) — 14 路径,代表 `vllm-ascend/v0.21.0rc/ascend-a2/models/DeepSeek-V3.2/DeepSeek-V3.2.yaml`
- [suffix](./decoding.md#suffix) — 8 路径,代表 `vllm/v0.23.0/rtx_pro_5000_48G/models/MiniMax-M2.5/MiniMax-M2.5-nvfp4.yaml`
- [dspark](./decoding.md#dspark) — 7 路径,代表 `vllm/v0.23.0/b200/models/DeepSeek-V4-Pro/DeepSeek-V4-Pro-dspark.yaml`

## 稀疏 sparse(2 变体)

- [accuracy_first](./sparse.md#accuracy-first) — 14 路径,代表 `vllm/v0.22.0/rtx_pro_5000_48G/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-fp8.yaml`
- [performance_first](./sparse.md#performance-first) — 14 路径,代表 `vllm/v0.22.0/rtx_pro_5000_48G/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-fp8.yaml`

## 卸载 offload(5 变体)

- [native](./offload.md#native) — 25 路径,代表 `vllm/v0.23.0/h20_141G/models/DeepSeek-V3.2/DeepSeek-V3.2.yaml`
- [backend:memcache](./offload.md#backend-memcache) — 5 路径,代表 `vllm-ascend/v0.21.0rc/ascend-a3/models/GLM-5.2/GLM-5.2-w4a8.yaml`
- [lmcache:cpu_disk](./offload.md#lmcache-cpu-disk) — 4 路径,代表 `vllm/v0.23.0/rtx_pro_5000_48G/models/MiniMax-M2.7/MiniMax-M2.7-nvfp4.yaml`
- [backend:mooncake](./offload.md#backend-mooncake) — 3 路径,代表 `vllm-ascend/v0.21.0rc/ascend-a2/models/MiniMax-M2.7/MiniMax-M2.7-w8a8.yaml`
- [lmcache-ascend](./offload.md#lmcache-ascend) — 2 路径,代表 `vllm-ascend/v0.21.0rc/ascend-a2/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash.yaml`