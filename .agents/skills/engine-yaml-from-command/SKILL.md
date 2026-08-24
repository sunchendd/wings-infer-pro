---
name: engine-yaml-from-command
description: 当用户要求根据 vLLM、vLLM-Ascend 或 SGLang 的引擎版本、硬件规格、卡数/显存生成或更新 Wings Control/兼容 schema 的模型 YAML 时使用，包括 default_model.yaml；也用于将启动命令转换为模型 YAML。支持单节点、多节点和 Prefill/Decode 分离，并包含输入规范化、canonical reference 和结构校验。Use when generating or updating Wings Control-compatible model YAML or default_model.yaml from vLLM, vLLM-Ascend, or SGLang engine version and hardware specifications, GPU count/memory, or launch commands, including standalone, multi-node, and prefill/decode deployments.
---

# 从启动命令生成引擎 YAML

## 目标

把用户实测的启动脚本转换为可追溯、可重建命令的模型 YAML。输出必须同时满足：

1. `engine_config` 保留原始命令参数顺序，模型位置参数固定第一位。
2. 顶层结构、场景结构、命名和字段风格匹配本 skill 携带的 canonical reference。
3. 不猜测版本、硬件规格、模型 ID、节点角色或损坏的 Shell 表达式。
4. 生成后执行 YAML 结构校验；在 Wings Control 仓库内继续执行项目验证器。

## 可移植边界

本 skill 自带 Wings Control 手工 YAML 的最小 contract 和真实场景参考，因此在空项目中也能稳定选择格式。目标项目若定义了不同 schema，必须以目标项目 schema 为准，不能把 Wings Control 字段强行写入。

优先级固定为：

1. 用户明确指定的目标 YAML 或模板。
2. 目标仓库同引擎、同版本、同硬件、同场景的现有 YAML。
3. 本 skill 中对应引擎和场景的 canonical reference。
4. `references/schema-contract.md` 的通用规则。

低优先级规则不得覆盖高优先级示例的字段集合、字段顺序或命名。

## 第一步：检查输入

必须确认以下输入：

- 引擎：只接受 `vllm`、`vllm-ascend`、`sglang`。
- 引擎版本：使用用户确认的完整版本，例如 `v0.21.0rc`；不要把 `0.21.rc1` 自动改成另一个版本。
- 完整启动命令：多节点必须分别提供 head/worker；PD 必须至少提供 prefill/decode。
- 硬件：profile id、单节点卡数、单节点总显存；已知 profile 可从 `references/hardware-profiles.json` 读取。`hardware_profile.multi_node` 根据用户提供的命令和场景自动判断：standalone 为 `false`，multi_node/PD（存在对应节点角色或分布式参数）为 `true`。
- 场景：`standalone`、`multi_node`、`pd_disaggregation`。
- 模型：模型名、可确认的 HuggingFace/ModelScope ID、variant。

先运行输入规范化器：

```bash
python3 <skill-dir>/scripts/normalize_input.py \
  --engine vllm-ascend \
  --engine-version v0.21.0rc \
  --hardware-profile ascend-a3 \
  --scenario standalone \
  --model-name Qwen3.6-35B-A3B \
  --model-id Qwen/Qwen3.6-35B-A3B \
  --variant bf16 \
  --command-file /path/to/start.sh
```

规范化器报错时停止生成。以下情况必须让用户确认，不能静默修复：

- 引擎拼写错误或版本不满足完整格式。
- Shell 语法错误，或出现 `\(`、`\)` 这类疑似转义损坏。
- multi-node 缺 head/worker 命令。
- PD 缺 prefill/decode 命令或节点角色不明确。
- 未知硬件 profile 且没有显式卡数和总显存。
- 本地模型路径无法映射到可靠的 `model_id`。

## 第二步：加载 reference

生成前必须读取 `references/schema-contract.md`，然后只读取对应引擎和场景的一个 YAML：

| 引擎 | standalone | multi_node | pd_disaggregation |
|---|---|---|---|
| vLLM | `references/vllm-standalone.yaml` | `references/vllm-multi-node.yaml` | `references/vllm-pd-disaggregation.yaml` |
| vLLM-Ascend | `references/vllm-ascend-standalone.yaml` | `references/vllm-ascend-multi-node.yaml` | `references/vllm-ascend-pd-disaggregation.yaml` |
| SGLang | `references/sglang-standalone.yaml` | `references/sglang-multi-node.yaml` | `references/sglang-pd-disaggregation.yaml` |

这些文件从 Wings Control 已检入的真实 YAML 中提取，非目标场景已删除。它们定义结构和风格，不定义新模型的具体参数值。禁止复制示例中的模型名、端口、并行度、环境变量或节点数量，除非用户命令确实提供了相同值。

## 第三步：生成 YAML

### 输出路径

- vLLM：`wings_control/config/engines/vllm/{profile}/models/{Model}/{Model}-{variant}.yaml`
- vLLM-Ascend：`config/engines/vllm-ascend/{version}/{profile}/models/{Model}/{Model}-{variant}.yaml`
- SGLang：`config/engines/sglang/{version}/{profile}/models/{Model}/{Model}-{variant}.yaml`

bf16/b16 全精度权重的文件名统一使用 `-bf16.yaml`。`variant_name` 是否带 bf16 后缀必须服从目标仓库同目录风格；没有目标仓库时按对应 canonical reference 的引擎风格。

### 顶层与字段顺序

普通模型 YAML 的顶层顺序固定为：

```text
upstream_sources -> model -> hardware_profile -> features(可选) -> scenarios
```

`engine_config` 与 `env` 的键顺序必须等于各自命令和 export 的出现顺序。只允许模型位置参数固定在 `engine_config` 第一位。不要按字母排序。

### Shell 拆分

- `vllm serve <model>` 的位置参数写成 `engine_config.model`。
- 普通顶层 `--flag-name value` 写成 `flag_name: value`；裸 flag 写 `true`。
- `export KEY=value` 写入对应策略或节点的 `env`，保持顺序。
- 对硬件 profile `rtx_pro_5000`（包括任意显存后缀，如 `rtx_pro_5000_48G`、`rtx_pro_5000_72G`）生成 YAML 时，必须在每个部署策略/节点的 `env` 中加入以下性能环境变量；不区分显存规格，也不要求用户在启动命令中重复提供：
  ```yaml
  NCCL_P2P_LEVEL: SYS
  NCCL_SHM_DISABLE: 1
  ```
  如果对应 `env` 已有其它变量，追加到现有键之后；如果是空环境，改为上述映射。该规则适用于 standalone、multi-node 和 PD 的所有策略/节点，包括 `default_model.yaml`。
- `source`、`unset` 和普通准备命令写入 `system_setup.commands`。`commands` 必须是字符串列表，并统一使用 canonical flow-style；禁止省略列表符号或改成裸缩进文本：

```yaml
system_setup:
  commands: [source /usr/local/Ascend/ascend-toolkit/set_env.sh, source /usr/local/Ascend/nnal/atb/set_env.sh]
```

- `sysctl` 写入 `system_setup.sysctls`，sysfs 写入写入 `system_setup.sysfs_writes`。
- 不输出 `ASCEND_RT_VISIBLE_DEVICES`。
- jemalloc 统一为 `/usr/lib/aarch64-linux-gnu/libjemalloc.so.2${LD_PRELOAD:+:$LD_PRELOAD}`。
- `MOONCAKE_CONFIG_PATH` 统一为 `/shared-volume/mooncake.json`。
- MemCache 配置路径统一为 `/shared-volume/mmc_local.conf`。
- 对于 `multi_node` 和 `pd_disaggregation`：若原始命令包含
  `--data-parallel-rpc-port`（或等价的下划线拼写），但值不是可确认的十进制端口号
  （例如 `$6`、`${DP_RPC_PORT}`），必须将 YAML 的对应
  `data_parallel_rpc_port` 写为 YAML 整数，并按场景设置回退值：
  - `multi_node` 的 head、worker 和同一组中的所有节点均填写 `12321`。
  - `pd_disaggregation` 中，同一组的所有 prefill（`p`）节点填写 `12321`，所有
    decode（`d`）节点填写 `12322`。
  生成结果必须明确提示用户这些值是待确认的默认端口，要求其确认实际端口；在确认前不得
  声称端口已按原始命令验证。若原始命令给出明确数字端口，必须保留原值，不得按上述回退
  规则改写。
  对生成后的 YAML，`validate_yaml.py` 必须校验 multi-node 和 PD 节点中已出现的
  `data_parallel_rpc_port` 为 YAML 整数；`$6`、`${DP_RPC_PORT}` 和带引号的
  `"12321"` 均视为无效并报错。
- `engine_config.kv_transfer_config` 中的 `engine_id` 和 `kv_port` 必须是 YAML
  整数。脚本占位符（如 `$1`）、带引号的字符串（如 `"0"`、`"30000"`）或任何非
  整数值均视为无效，`validate_yaml.py` 必须报错。生成时应从原始命令提取明确数字，
  不得保留 shell 变量或引号。

### 参数名映射与嵌套原生配置

Wings Control 的 `engine_config` 参数名映射以**第一个点号**为边界；不得把完整 CLI 名称机械地把 `-` 和 `.` 全部替换成 `_`。该规则适用于 vLLM、vLLM-Ascend、SGLang 的 `engine_config` 渲染，优先级高于“普通顶层参数”的简写规则。

1. **无点号的顶层参数**：CLI 去掉 `--` 后将连字符转换为下划线。例如 `--max-model-len 2048` 写成 `max_model_len: 2048`，渲染回 `--max-model-len 2048`。
2. **带点号的原生嵌套参数**：只转换点号**前**的顶层段；点号及其后的原生路径必须逐字符保留（包括下划线、额外点号和大小写）。例如：
   ```yaml
   # --cc.pass_config.fuse_allreduce_rms=False
   cc.pass_config.fuse_allreduce_rms: false

   # --speculative-config.num_speculative_tokens 3
   speculative_config.num_speculative_tokens: 3
   ```
   上述键分别渲染为 `--cc.pass_config.fuse_allreduce_rms=False` 与 `--speculative-config.num_speculative_tokens=3`。
3. **禁止扁平化嵌套路径**：不得把 `--cc.pass_config.fuse_allreduce_rms=False` 写成 `cc_pass_config_fuse_allreduce_rms: false`。这会错误渲染为 `--cc-pass-config-fuse-allreduce-rms`，且当前顶层布尔 `false` 会被当作关闭的裸开关而省略，造成参数丢失。
4. **布尔值语义**：顶层 `true` 是裸 flag；顶层 `false` 不输出。带点号的嵌套参数始终使用 `--flag=value`，所以 `true` 和 `false` 都必须显式保留为 YAML 布尔值，不能因为值为 `false` 而删除。若原始命令含有“顶层参数显式传 Boolean 值”但它不是嵌套路径，先核对项目渲染器是否支持；不支持时必须扩展渲染/契约，不能静默写成顶层 `false`。
5. `features.*.args` 是原始 CLI token 列表，保持原 flag 拼写，不套用 `engine_config` 的 key 转换规则。

所有长参数必须使用 `--` 前缀；`-cc.pass_config...` 不是本项目输出的长参数形式。

### 引擎差异

- vLLM 手工配置默认把本地模型路径替换成已确认的 HF/ModelScope ID，并默认丢弃 `served_model_name`。
- vLLM-Ascend 保留命令中的 `served_model_name`。官方 `/weights/...`、`$MODEL_PATH` 可部署占位路径可以保留；用户机器私有路径应替换为已确认的模型 ID 或可部署占位路径。
- SGLang 保留真实参数名，例如 `model_path`、`tp`/`tp_size`、`dp`、`ep`、`mem_fraction_static`、`disaggregation_mode`，不得改写为 vLLM 参数名。

### 单机监听地址

所有 `standalone` 场景的 `engine_config` 必须写入 `host: "0.0.0.0"`。无论原始启动命令是否提供 `--host`，也无论其值为何，均不得省略该字段或沿用原始值。该规范化仅适用于 standalone；multi-node 和 PD 仍按原始命令及对应 reference 保留节点地址。

### 可选功能

工具调用、reasoning、spec decoding、KV offloading、Mooncake/MemCache/LMCache 和 sparse index 等可独立开关功能放在 `features`，不重复留在 `engine_config`。`features.*.args` 保留原始 CLI flag，JSON 使用双引号字符串并转义内部双引号。

如果目标 schema 不支持 `features`，先扩展 schema/验证器；否则功能参数留在 `engine_config`，不能静默丢弃。

#### PD 功能参数保留规则

对于 `pd_disaggregation`，以下功能参数**不得**从各 prefill/decode 节点的
`engine_config` 抽取到顶层 `features`。必须保留在每个节点中，并按该节点的原始
启动命令分别配置；不得为了复用而删除节点中的参数：

| 功能 | 参数 |
|---|---|
| `spec_decoding` | `--speculative-config` 或 SGLang speculative 参数组 |
| `kv_offloading` | `--kv-offloading-*` |
| `mooncake_offloading` | Mooncake `--kv-transfer-config` |
| `memcache_offloading` | MemCache `--kv-transfer-config` |
| `lmcache` | LMCache server 与 connector 参数 |
| `sparse_index` | 配置 sparse index 的 `--hf-overrides` |

这项限制仅针对 PD 节点配置。standalone 或 multi-node 场景仍可按目标 schema 将这些
可选功能抽取到 `features`；但同一 YAML 具有 PD 场景时，不能让顶层 feature 覆盖或替代
PD 节点的显式参数。

#### reasoning parser 公共表同步

每次**新增或更新**模型 YAML，都必须在写入文件前检查是否包含 `features.reasoning`：

1. 若不包含 `features.reasoning`，不修改公共 reasoning parser 表。
2. 若包含 `features.reasoning`，读取目标仓库的 `wings_control/docs/features/reasoning_parser/reason_parser.yaml`，在 `name: ReasoningParserModels` 条目的 `models` 下按 `model.variant_name` 做**大小写不敏感的完整匹配**。不得只按模型目录、`model.name`、`model_id` 或子串判断。
3. 若已存在，核对其 `vllm` 和 `vllm_ascend` 配置与 YAML 中的 reasoning parser；发现不一致、`null` 或只配置一个引擎时，停止并报告差异，不能静默覆盖。
4. 若不存在，必须在 `ReasoningParserModels.models` 下新增一项，并从 `features.reasoning.args` 中读取已确认的 `--reasoning-parser` 值：

   ```yaml
   - name: ReasoningParserModels
     config: {}
     models:
       <variant_name>: {vllm: <parser>, vllm_ascend: <parser>}
   ```

   `vllm` 和 `vllm_ascend` 必须使用完全相同的 parser 配置。若 args 中没有明确的 parser 名称，或 parser 名称无法从用户命令/可靠资料确认，必须先让用户确认，不能猜测或使用默认值。
5. 同一变体已有公共表条目时，不要重复添加；更新模型 YAML 和公共表必须作为同一变更一起验证。

这项检查适用于 standalone、multi-node 和 PD 的每个模型 YAML；PD 的多个节点只登记一次同一个 `variant_name`。生成结果必须说明公共表是“未涉及”“已命中并核对”还是“已新增并同步”，以及两个引擎使用的 parser 值。

### 场景

- standalone：`match.distributed: false`，策略内直接放 `engine_config`、`env`、`system_setup`。
- multi-node：`match.distributed: true`，普通双节点使用 `head`/`worker`；多个 worker 或多类节点可使用 `nodes`。
- PD：场景 key 固定为 `pd_disaggregation`，策略优先为 `pd_cluster`，`nodes` 至少包含一个 `prefill` 和一个 `decode`。
- `hardware_profile.multi_node` 根据用户提供的命令判断当前部署是否为多节点：standalone 命令（无 head/worker、prefill/decode 角色及分布式节点参数）填写 `false`；multi_node 或 PD 命令（包含 head/worker、prefill/decode 角色，或明确的多节点分布式参数）填写 `true`。不要仅依据硬件型号或硬件表静态决定该字段。若命令无法判断，必须要求用户补充节点角色或节点数量。

## 第四步：验证

先运行 skill 自带结构校验：

```bash
python3 <skill-dir>/scripts/validate_yaml.py \
  --engine vllm-ascend \
  --scenario standalone \
  --reasoning-registry wings_control/docs/features/reasoning_parser/reason_parser.yaml \
  /path/to/generated.yaml
```

结构校验通过后，**必须执行 dry-run 参数一致性校验**。该校验从 YAML 的
`engine_config` 和 `features.*.args` 重建引擎命令，并与生成 YAML 所依据的每个原始
启动命令比较。

用户可能直接在消息中粘贴多行命令，而不是提供脚本文件。此时必须先将命令原样写入
临时 command file（保留续行、引号和 JSON 参数），再执行 dry-run；“没有现成的脚本
文件”不能作为跳过校验的理由。只有用户确实没有提供完整原始命令时，才能报告 dry-run
未完成，且不能声称参数已验证：

```bash
python3 <skill-dir>/scripts/check_dry_run.py \
  --engine vllm-ascend \
  --scenario standalone \
  --command-file /path/to/materialized-start.sh \
  /path/to/generated.yaml
```

multi-node/PD 对每个节点重复 `--command-file`，顺序必须与 YAML 中的节点顺序一致。
inline 命令物化后，必须检查 command file 内容与用户消息逐项一致，再运行校验。
校验失败（缺失参数、额外参数、参数值不一致或节点数量不一致）时停止并修正 YAML。standalone 的 `--host` 是唯一例外：YAML 固定为 `0.0.0.0`，dry-run 不将原始命令中缺失或不同的 `--host` 视为不一致。
对于 multi-node/PD 的 `data_parallel_rpc_port` 回退值：在用户确认真实端口前，不得将含
`$6` 等非数字端口的原始命令直接与 YAML 宣称为 dry-run 匹配；应报告端口待确认。用户确认
回退端口后，才可将临时命令中的该参数解析为对应值并完成 dry-run：multi-node 的所有节点为
`12321`；PD 的 prefill（`p`）节点为 `12321`，decode（`d`）节点为 `12322`。
脚本会打印每个节点的 YAML 重建命令、原始启动命令和逐项比较结果：`OK` 表示匹配，
`缺失`、`多余`、`不一致` 会分别列出参数及 YAML/command 的值；异常报告输出到 stderr，
并以退出码 1 结束。成功报告输出到 stdout 并以退出码 0 结束，便于日志和 CI 查看。
尤其必须确认 `features.tool_calling` 和 `features.reasoning` 中的参数分别出现在
最终 dry-run 命令中；不能只验证 YAML 能解析。

验证必须覆盖：

1. YAML 可解析，顶层顺序和字段类型正确；`system_setup.commands` 必须是同一行的 flow-style 字符串列表。
2. 场景结构与 reference 一致，且恰有一个 `default_strategy: true`。
3. multi-node 节点结构完整；PD 同时存在 prefill/decode。
4. `engine_config` 可按原顺序重建命令，features 参数可合并回原始命令；若存在带点号的 key，必须逐项确认输出为 `--顶层-flag.原生路径=value`，并覆盖值为 `false` 的情形。
5. 除明确的路径归一化、feature 拆分、参数名映射和 standalone `host: "0.0.0.0"` 规范化外，不允许核心参数缺失或值变化。
6. 若存在 `features.reasoning`，核对 `model.variant_name` 在 `wings_control/docs/features/reasoning_parser/reason_parser.yaml` 的 `ReasoningParserModels.models` 中已唯一登记，且 `vllm` 与 `vllm_ascend` 的 parser 配置相同；若是新登记项，确认公共表同步已包含在同一变更中。

除 `system_setup.commands` 的 canonical flow-style 约束外，YAML 的引号、其它 flow/block list、`0.90`/`0.9` 属于序列化差异，应比较解析后的结构。若用户要求其余内容逐字一致，必须使用用户指定模板或确定性 renderer，不能依赖自由生成。

## default_model.yaml

用户只提供引擎版本、硬件 profile、卡数和单卡显存，并要求生成 `default_model.yaml` 时，也必须触发本 skill；这类请求不需要模型名、variant 或启动命令。应先查找目标路径 `{engine}/{version}/{hardware_profile}/models/default_model.yaml`：

1. 文件已存在时，只提示已存在及其路径，禁止自动覆盖；用户明确要求更新时再单独确认覆盖范围。
2. 文件不存在时，提示目标目录缺少默认文件，并根据同引擎/版本的相邻 hardware profile 模板自动创建。总显存按 `gpu_count * vram_per_gpu_gb` 计算，所有默认 TP、PD 的 `tp_size` 等与模板保持一致，仅替换硬件相关值。
3. 创建后必须执行 default 专用 dry-run；不能使用要求启动命令的普通模型 dry-run。

```bash
python3 <skill-dir>/scripts/check_dry_run.py \
  --default-model --engine vllm-ascend --engine-version v0.23.0 \
  --hardware-profile ascend910b-x86_64 --gpu-count 16 \
  --vram-per-gpu-gb 64 \
  wings_control/config/engines/vllm-ascend/v0.23.0/ascend910b-x86_64/models/default_model.yaml
```

若目标仓库没有模板，读取 `references/default-model-contract.md`（如存在），不得套用普通模型 YAML reference。`default_model.yaml` 只包含 `hardware`、`engine`、`scenarios`，并且三个场景都必须存在。default dry-run 必须检查 YAML 可解析、顶层结构、版本、硬件卡数/总显存、三个场景、唯一默认策略以及 standalone/multi-node/PD 的节点结构；失败时停止并修正，不能声称创建成功。

## 禁止事项

- 不编造模型元数据、版本、硬件规格或节点角色。
- 不从错误拼写推断另一个版本。
- 不把本地私有路径写入可分发 YAML。
- 不把 vLLM、vLLM-Ascend、SGLang 的参数名和 strategy 命名混用。
- 不因 YAML 能解析就声称命令已验证；必须说明是否执行了参数支持检查。
