---
name: smart-yaml
description: Use when creating, editing, or validating a `wings_control` smart-accel YAML, including decoding, KV offload, sparse, or any `smart_accel:` block under `src/wings_accel/smart-accel/`.
---

# smart-accel YAML

为 `wings_control` 编写或校验 `smart-accel` 加速资产。它只定义
`decoding`、`kv_offload`、`sparse`；引擎基础配置和 `features` 由
`engine-yaml-from-command` 负责。

## 决策与验证顺序

1. 对每一份 engine YAML 单独确认运行时 `ENGINE_VERSION`、精确
   `model.variant_name`、硬件目录和 `features`；不要把同一模型目录中的多个
   engine YAML 合并为一个 smart 资产。
2. 以开源 recipe 为基线；仅将已有 0day 实测结果作为补充或覆盖依据。没有
    recipe 或实测依据时，不臆造特性、参数、包版本或后端。
3. 新资产写入
    `wings_control/src/wings_accel/smart-accel/<engine>/v<version>/<hardware>/models/<model>/<variant>.yaml`。
   `vllm` 的 engine 配置目录没有版本层，不能据此推断 smart-accel 路径；路径只由
   实际运行时 `ENGINE_VERSION` 决定，**不是** `min_engine_version`。loader 按
   “原始版本目录→归一化版本目录”查找。例如同一 engine 目录中的
   `DeepSeek-V4-Flash-fp8`（`ENGINE_VERSION=v0.22.0`）和
   `DeepSeek-V4-Flash-0731`（`ENGINE_VERSION=v0.26.0`）必须分别落在
   `smart-accel/vllm/v0.22.0/...` 和 `smart-accel/vllm/v0.26.0/...`，不能
   互相代替或强行归入 `v0.23.0`。
4. 先用同类资产起稿，再按本文件检查。无受支持 feature 时保留
    `smart_accel: {}`。
5. 完成后运行：
    `cd wings_control && python3 tests/wings_accel/smart_accel_io.py <yaml路径> --matrix`
    它验证 loader、选择、渲染和 `files` 的 JSON/YAML/bash 语法；**不是** 0day。
    只有实际部署的功能/性能结果才能作为 0day 证据，且要记录其相对 recipe 的增删。

## YAML 骨架

`variant_name` 必须是精确 `--model-name`，`name_pattern` 只做家族兜底。场景块
用 `source_ref`、`match`、`strategies`；其中 `match` 是作者自检，loader 不读取。

```yaml
model:
   name: <family>
   variant_name: <exact-model-name>
   match: [{name_pattern: <family-regex>}]
smart_accel:
   standalone:
      source_ref: <recipe-or-test>#single_node
      match: {distributed: false, pd_role: null}
      strategies: {single_node: {default_strategy: true}}
   multi_node:
      source_ref: <recipe-or-test>#multi_node
      match: {distributed: true, pd_role: null}
      strategies: {multi_node_dp: {default_strategy: true}}
   pd_disaggregation:
      source_ref: <recipe-or-test>#pd_cluster
      match: {distributed: true, pd_role: null}
      strategies:
         pd_cluster:
            default_strategy: true
            nodes:
               - {role: prefill, index: 0}
               - {role: decode, index: 0}
```

删除不支持的空特性键，而不是保留空列表。禁止旧字段 `deploy_modes`。
PD prefill 只能有 `sparse`；PD decode 只能有 `decoding`、`sparse`；PD 两端均不能有
`kv_offload`。

## 方案字段与 decoding

每个方案使用 `name`、`cli_params`、`envs`，可选 `packages`（新资产必须是
`{package: version}` 字典，不是列表）；KV 方案可额外有 `files`。

- `cli_params` 是原样传入引擎的结构化配置；投机参数放在
   `speculative_config` 内。`num_speculative_tokens_per_batch_size` 也必须放在
   此处，并保留 `num_speculative_tokens` 作为兜底。
- `requires_model_path: true` 的草稿方案在 `speculative_config.model` 使用
   `$path`。多个 `draft_arch` 必须互斥；可有一个未声明 `draft_arch` 的通用草稿兜底。
- `requires_model_path` 缺省/false 的 no-model 方案（MTP、suffix 等）至多一个。
- 若任一对应 engine scenario 的 `async_scheduling: true`，所有 smart YAML
   scenario 都不能声明 `suffix`。
- 仅当 `decoding`、`kv_offload`、`sparse` 至少一个实际产出时，才会合入
   `custom_features`。它是可选的 always-on 方案列表，用于与三类特性正交的
   引擎参数；其 `cli_params` 深合并、`envs` 后者覆盖，不能单独作为启用特性。

## KV 卸载与 files

YAML 不写 `ENABLE_*` 开关。`cpu`、`disk`、`cpu_disk` 分别由内存/磁盘开关选中；
`cpu_disk` 缺失才会退化为 `disk` 或 `cpu`。只声明 recipe 或 0day 已确认的方案：

| 形态 | 写法要点 |
| --- | --- |
| vLLM 原生 CPU | `name: cpu`，`kv_offloading_backend: native`，容量用 `{memory_capacity_gb}`。 |
| LMCache disk/cpu_disk | `LMCacheConnectorV1`；按基线保留所需 `envs`、包和配置文件。若使用 `files` 写 LMCache 配置，`envs` 的 `LMCACHE_CONFIG_FILE` 必须指向它。 |
| Ascend LMCache | `name: cpu`，`LMCacheAscendConnectorV1Dynamic`；按已验证资产声明包和 LMCache 环境变量。 |
| mooncake/memcache | `name: cpu`，`AscendStoreConnector` 和 `backend`；使用 `files` 写配置及 `start_kv_serve.sh`。mooncake 才加 `LD_LIBRARY_PATH`。 |
| LMCache MP | `name: cpu`，`LMCacheMPConnector`；connector 参数在 `kv_transfer_config`，server 参数在 `start_kv_serve.sh`。 |

`start_kv_serve.sh` 表示独立 daemon，框架只在 master 执行它；不要手写
`pre_serve`，除非已有特殊流程无法用 `files` 表达。`files` 条目使用 `path`、
`content` 或 `src`（二选一），可选 `scope: all|master|client` 和 `mode: "0755"`。
memcache `world_size`、端口、协议均为手写字面量，拓扑变更时必须复核。
`LMCACHE_QAT_ENABLED` 由代码注入，绝不能写入 `envs`。

## sparse 与占位符

`sparse.name` 必须是 `performance_first` 或 `accuracy_first`。`index_topk_freq`
越大表示越少重算、速度越高、精度越低，因此使用 performance `8`、accuracy `4`。
`kv_cache_dtype` 规则（单向，只约束 engine→smart）：开源 recipe（engine YAML）
声明了 `kv_cache_dtype: fp8`/`fp8_e4m3` 时，sparse 两个方案的 `cli_params` 都
必须写 `kv_cache_dtype: fp8`（与 engine 基线对齐）。recipe 未设置时 smart 侧
也**允许额外声明**——smart 可以比 recipe 多（如 fp8 checkpoint / 0day 验证），
符合预期不算违规，不要回删。

命名占位符在 `cli_params`/`envs` 中必须占满整个字符串，在 `files.content` 中才可嵌入。
未知或条件未满足的 token 会原样保留。

| token | 用途 |
| --- | --- |
| `{memory_capacity_gb}`、`{disk_capacity_gb}`、`{disk_path}` | 已启用的内存/磁盘卸载容量与路径。 |
| `{mem_gb_to_bytes}`、`{mem_gb_to_blocks}`、`{cpu_swap_space_gb}` | 原生卸载的换算/策略值。 |
| `{qat_enabled}`、`{qat_device_count}`、`{qat_compression_level}` | LMCache 配置文件 QAT 值。 |
| `$path` / `$draft_model_path` | 草稿模型路径。 |
| `{rank_ip}` / `{master_ip}` | daemon 文件中的节点 IP，运行时展开。 |
| `{lookup_server_worker_ids}` | 由 TP 推导的 LMCache worker 列表。 |
| `{= expr}` | 数值表达式；变量限容量、QAT、`gpu_count`、`tp_size`、`dp_size`，运算限 `+ - * / // % ** ()`。 |

## 交付

汇报资产路径、各 scenario 特性、recipe 基线、0day 覆盖项（或无）、矩阵结果。
字段不确定时以 `wings_control/src/wings_accel/docs/smart-yaml.md`、代码和相近已验证
资产为准，不猜测。