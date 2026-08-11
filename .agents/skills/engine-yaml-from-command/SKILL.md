---
name: engine-yaml-from-command
description: 当用户给出 vLLM、vLLM-Ascend 或 SGLang 启动命令，要求生成 Wings Control 或兼容 schema 的模型 YAML 时使用。支持单节点、多节点和 Prefill/Decode 分离；包含可移植的真实 YAML 参考、输入规范化和结构校验。Use when converting vLLM, vLLM-Ascend, or SGLang launch commands into Wings Control-compatible YAML for standalone, multi-node, or prefill/decode disaggregation deployments.
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
- `--flag-name value` 写成 `flag_name: value`；裸 flag 写 `true`。
- `export KEY=value` 写入对应策略或节点的 `env`，保持顺序。
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

### 引擎差异

- vLLM 手工配置默认把本地模型路径替换成已确认的 HF/ModelScope ID，并默认丢弃 `served_model_name`。
- vLLM-Ascend 保留命令中的 `served_model_name`。官方 `/weights/...`、`$MODEL_PATH` 可部署占位路径可以保留；用户机器私有路径应替换为已确认的模型 ID 或可部署占位路径。
- SGLang 保留真实参数名，例如 `model_path`、`tp`/`tp_size`、`dp`、`ep`、`mem_fraction_static`、`disaggregation_mode`，不得改写为 vLLM 参数名。

### 可选功能

工具调用、reasoning、spec decoding、KV offloading、Mooncake/MemCache/LMCache 和 sparse index 等可独立开关功能放在 `features`，不重复留在 `engine_config`。`features.*.args` 保留原始 CLI flag，JSON 使用双引号字符串并转义内部双引号。

如果目标 schema 不支持 `features`，先扩展 schema/验证器；否则功能参数留在 `engine_config`，不能静默丢弃。

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


验证必须覆盖：

1. YAML 可解析，顶层顺序和字段类型正确；`system_setup.commands` 必须是同一行的 flow-style 字符串列表。
2. 场景结构与 reference 一致，且恰有一个 `default_strategy: true`。
3. multi-node 节点结构完整；PD 同时存在 prefill/decode。
4. `engine_config` 可按原顺序重建命令，features 参数可合并回原始命令。
5. 除明确的路径归一化、feature 拆分和参数名映射外，不允许核心参数缺失或值变化。
6. 若存在 `features.reasoning`，核对 `model.variant_name` 在 `wings_control/docs/features/reasoning_parser/reason_parser.yaml` 的 `ReasoningParserModels.models` 中已唯一登记，且 `vllm` 与 `vllm_ascend` 的 parser 配置相同；若是新登记项，确认公共表同步已包含在同一变更中。

除 `system_setup.commands` 的 canonical flow-style 约束外，YAML 的引号、其它 flow/block list、`0.90`/`0.9` 属于序列化差异，应比较解析后的结构。若用户要求其余内容逐字一致，必须使用用户指定模板或确定性 renderer，不能依赖自由生成。

## default_model.yaml

`default_model.yaml` 不是普通模型配置。它只包含 `hardware`、`engine`、`scenarios`，并且三个场景都必须存在；不要套用本 skill 的普通模型 YAML reference。目标仓库存在 default 文件时以其为模板。

## 禁止事项

- 不编造模型元数据、版本、硬件规格或节点角色。
- 不从错误拼写推断另一个版本。
- 不把本地私有路径写入可分发 YAML。
- 不把 vLLM、vLLM-Ascend、SGLang 的参数名和 strategy 命名混用。
- 不因 YAML 能解析就声称命令已验证；必须说明是否执行了参数支持检查。
