# Wings Control 手工模型 YAML Contract

## 目录

1. Reference 使用方式
2. 输入契约
3. 顶层结构
4. 场景结构
5. 命令映射
6. Feature 规则
7. 序列化规则
8. 验证清单

## Reference 使用方式

场景 YAML 是从 Wings Control 已检入配置中提取的结构参考。生成新配置时：

- 复制字段集合、层级、字段顺序、strategy key 和 display name 风格。
- 用用户命令替换模型、端口、并行度、环境变量、节点和功能参数。
- 不复制 reference 中未出现在用户输入里的调优参数。
- 用户指定目标 YAML 时，以目标 YAML 为最高优先级。
- 同目录样例和本 contract 冲突时，以同目录样例为准，并在结果说明差异。

## 输入契约

普通模型 YAML 生成前必须得到以下确定信息：

| 输入 | 要求 |
|---|---|
| engine | `vllm`、`vllm-ascend`、`sglang` 之一 |
| engine_version | 完整版本，格式 `v?MAJOR.MINOR.PATCH`，可带 `rc` 或 `rcN` |
| hardware_profile | 已知 profile id，或显式 `gpu_count` + 单节点 `vram_gb` |
| scenario | `standalone`、`multi_node`、`pd_disaggregation` |
| model_name | YAML 和输出目录使用的稳定名称 |
| model_id | 可确认的 HF/ModelScope ID；无法确认时明确为 null |
| variant | bf16、w8a8、w4a8、fp8 等；无法判断时询问 |
| commands | 每种节点角色的完整命令和前置 Shell 设置 |

`default_model.yaml` 是例外：它只需要 `engine`、`engine_version`、`hardware_profile`（包括卡数和单卡显存），不需要 `model_name`、`model_id`、`variant` 或 `commands`。生成路径必须是 `{engine}/{version}/{hardware_profile}/models/default_model.yaml`。写入前先检查目标文件：已存在时不得覆盖；不存在时才能从同引擎/版本的相邻硬件模板创建。总显存为 `gpu_count * vram_per_gpu_gb`。创建后必须执行 `check_dry_run.py --default-model`，检查顶层结构、版本、硬件规格、三个场景和默认策略。

版本字符串只做可选前导 `v` 的格式检查，不做猜测性别名转换。`0.21.rc1` 缺 patch 段，应报错而不是转换成 `v0.21.0rc`。

Shell 中出现 `\(`、`\)`、未闭合引号或未展开的错误变量表达式时，必须先确认原命令。

## 顶层结构

普通模型 YAML 顶层键顺序：

1. `upstream_sources`
2. `model`
3. `hardware_profile`
4. `features`，仅在存在可选功能时输出
5. `scenarios`

### upstream_sources

手工命令使用：

```yaml
upstream_sources:
  - id: <engine>_<model-slug>_<variant>_manual
    kind: manual
    repo: null
    file: null
    url: <confirmed-model-url-or-null>
    note: 用户提供启动命令，手工录入。
```

不要默认加入动态日期。目标目录已经统一使用 `date_updated` 时才添加。

### model 字段风格

- vLLM 默认采用完整模型字段；只填写能从用户输入或可靠来源确认的值。
- vLLM-Ascend 和 SGLang 默认采用精简字段：`name`、`provider`、`model_id`、`min_engine_version`、`match`、`variant_name`。
- 不确定字段不编造。目标 schema 允许时写 `null # 待补充`；精简风格下直接省略。
- `min_engine_version` 保持用户确认的完整版本，不做近似转换。
- `match.name_pattern` 必须转义正则特殊字符；模型名中的 `-`/`.` 可使用 `[-.]?` 兼容。

### hardware_profile

```yaml
hardware_profile:
  gpu_count: <单节点卡数>
  vram_gb: <单节点总显存 GB>
  multi_node: <根据用户命令判断的当前部署是否为多节点>
```

`multi_node` 根据用户提供的命令和部署场景确定，而不是硬件型号的静态能力字段：standalone 命令填写 `false`；multi_node 或 PD 命令填写 `true`。命令中若有 head/worker、prefill/decode 角色，或明确的多节点分布式参数，应判定为 `true`；仅有单节点启动命令且无上述信息时判定为 `false`。无法判断时必须要求用户补充节点角色或节点数量。未知硬件 profile 仍必须让用户提供 `gpu_count` 和 `vram_gb`。

## 场景结构

### standalone

- 场景 key：`standalone`
- `match.distributed: false`
- `match.pd_role: null`
- strategy 直接包含 `engine_config`、可选 `env` 和 `system_setup`
- vLLM strategy 按并行方式使用 `single_node_tp`、`single_node_tep`、`single_node_dep`
- vLLM-Ascend 默认使用 `single_node` 和 `display_name: Standalone`
- SGLang 优先匹配 reference 或目标同目录的 strategy key

### multi_node

- 场景 key：`multi_node`
- `match.distributed: true`
- `match.pd_role: null`
- 普通双节点使用 `head`/`worker`
- 每个节点独立包含完整 `engine_config` 和 `env`
- worker 特有参数不得复制到 head，反之亦然
- 超过两类节点或多个非同构 worker 时使用 `nodes`

### pd_disaggregation

- 场景 key：`pd_disaggregation`
- strategy key：`pd_cluster`，除非目标目录已有更具体命名
- `display_name: Prefill/Decode Disaggregation`
- `nodes` 至少包含一个 `role: prefill` 和一个 `role: decode`
- 每个 role 内 `index` 从 0 或用户命令给出的编号开始，同一 role 下不能重复
- vLLM/vLLM-Ascend 的 producer/consumer 角色必须与 prefill/decode 对应
- SGLang 的 `disaggregation_mode` 必须与节点 role 对应

每个场景必须恰好有一个 `default_strategy: true`。只有一条策略时必须标记为默认。

## 命令映射

| 输入 | YAML |
|---|---|
| `vllm serve <model>` | `model: <model>`，固定第一位 |
| `--tensor-parallel-size 8` | `tensor_parallel_size: 8` |
| `--data-parallel-size 2` | `data_parallel_size: 2` |
| `--enable-expert-parallel` | `enable_expert_parallel: true` |
| SGLang `--model-path` | `model_path`，必要时按同目录风格同时写 `model` |
| SGLang `--tp/--dp/--ep` | `tp`/`dp`/`ep`，不得改成 vLLM 名称 |
| `export KEY=value` | 对应策略或节点的 `env.KEY` |
| `source`/`unset` | `system_setup.commands`，字符串列表，使用同一行 flow-style |
| `sysctl -w a=b` | `system_setup.sysctls.a: b` |
| 写入 `/sys/...` | `system_setup.sysfs_writes` |

未知 flag 使用通则：去掉 `--`，连字符转下划线；带值保留原始类型，裸 flag 为 `true`。dotted flag 默认保留点号，除非目标项目验证器定义了其它映射。

JSON/dict 参数优先转为 YAML mapping。进入 `features.*.args` 时保留为转义后的 JSON 字符串，以便重建原始 CLI。

## Feature 规则

以下独立开关从主 `engine_config` 抽到 `features`：

| feature | 常见参数 |
|---|---|
| `tool_calling` | `--enable-auto-tool-choice`、`--tool-call-parser`、配套 `--chat-template`/`--tokenizer-mode` |
| `reasoning` | `--reasoning-parser` |
| `spec_decoding` | `--speculative-config` 或 SGLang speculative 参数组 |
| `kv_offloading` | `--kv-offloading-*` |
| `mooncake_offloading` | Mooncake `--kv-transfer-config` |
| `memcache_offloading` | MemCache `--kv-transfer-config` |
| `lmcache` | LMCache server 与 connector 参数 |
| `sparse_index` | 配置 sparse index 的 `--hf-overrides` |

核心 PD 数据通道配置仍放在对应 node 的 `engine_config`。只有能从主命令独立开关的加速功能才抽到 `features`。

### reasoning parser 公共表同步

新增或更新 YAML 时，只要顶层存在 `features.reasoning`，就必须读取 `wings_control/docs/features/reasoning_parser/reason_parser.yaml`，并将 `model.variant_name` 与 `ReasoningParserModels.models` 做大小写不敏感的完整匹配。没有 `features.reasoning` 时不得因为模型名称相似而登记。

- 已有完整匹配：核对其 `vllm`、`vllm_ascend` 与 YAML `features.reasoning.args` 中的 `--reasoning-parser` 值；差异、`null` 或缺少引擎配置必须报告并停止，不能静默改写。
- 没有匹配：在 `ReasoningParserModels.models` 下新增唯一键，并让两个引擎使用同一个已确认 parser：

  ```yaml
  - name: ReasoningParserModels
    config: {}
    models:
      <variant_name>: {vllm: <parser>, vllm_ascend: <parser>}
  ```

- parser 名称必须来自用户命令或可靠资料；`features.reasoning.args` 未明确给出时不能猜测。multi-node/PD 的多个节点对相同变体只登记一次。
- 生成结果必须说明公共表同步状态（未涉及、已命中并核对、已新增并同步）及 `vllm`/`vllm_ascend` parser 值。

## 序列化规则

- `engine_config`、`env` 保持原命令顺序。
- 模型参数固定第一位。
- host 字符串使用引号，例如 `"0.0.0.0"`。
- JSON feature 参数使用双引号字符串并转义内部双引号。
- `system_setup.commands` 必须写成同一行的 flow-style 字符串列表，例如 `commands: [source /path/a.sh, source /path/b.sh]`。禁止写成 `commands:` 后跟没有 `-` 的裸文本，也不要改成 block list。
- 空环境使用 `env: {}`；没有 `system_setup` 时省略该键。
- 不为了保留 `0.90` 的文本写法而把数字改成字符串；语义比较时 `0.90 == 0.9`。
- 不把 flow/block list、引号或注释差异当成结构错误。

## 验证清单

1. 运行 `scripts/normalize_input.py`，输入无错误和待确认警告。
2. 运行 `scripts/validate_yaml.py --engine ... --scenario ... --reasoning-registry wings_control/docs/features/reasoning_parser/reason_parser.yaml`；存在 `features.reasoning` 时必须提供 registry。
3. 执行 `scripts/check_dry_run.py`，重建每个策略/节点命令，并把 `features`（至少包括 `tool_calling` 和 `reasoning`）合并回命令进行 normalized diff。`system_setup.commands` 中严格形如 `source <path>` 的命令也必须与原始脚本逐条、按顺序比较。用户直接粘贴 inline 命令时，必须先将原始命令原样物化为临时 command file 再执行；不能因为没有现成脚本文件而跳过。只有用户没有提供完整原始命令时，才可报告 round-trip 未完成。
4. dry-run 比较必须报告缺失参数、额外参数、值不一致、source 命令不一致和节点数量不一致；任一项存在都必须失败。
5. 仅运行 skill 自带的结构校验和 dry-run 校验；本 skill 不要求不存在的项目级验证器。
6. 校验结果必须说明是否完成参数白名单检查以及 dry-run 参数一致性检查。
