# wings-control TP/DP 并行策略

本文说明 `--device-count` 在单机、多机和 PD 分离场景下如何影响 TP/DP。MaaS 字段定义见[MaaS 接口参数契约](../guideline/Maas侧与wins-control侧交互接口参数锲约说明.md)。

## 前提

- `cnt` 表示当前 Pod 内该 engine 实例可用的 GPU 数，不是集群总卡数。优先使用 `--device-count`，其次使用 `DEVICE_COUNT` 环境变量；两者都未提供时，沿用模板默认值。
- 模板 recipe 位于 `config/engines/` 下的 `model.yaml`，其中记录推荐的 TP/DP。
- 每次改写都会记录最终值、来源层、来源路径和覆盖历史，可在 `audit.json` 中追溯。

## 并行策略速查

1. **单机（standalone）**
   - `cnt >= TP`：TP 不变，改 DP。
   - `cnt < TP`：满足守卫时收缩 TP。
2. **多机（multi_node）**
   - **DP 跨 Pod（DP_across）**：TP 不变，改 DP。
   - **TP 跨 Pod（TP_across）**：DP 不变，改 TP。
3. **PD 分离（pd_disaggregation）**
   - **普通 1P1D**：TP 取 `cnt`，DP 等于 1。
   - **大 EP**：TP、DP 不变，严格使用 recipe 和 MaaS 下发值。

| 场景 | 一句话 | TP 会变？ | DP 会变？ |
| --- | --- | --- | --- |
| 单机 | `cnt >= TP` 时改 DP；`cnt < TP` 时尝试收缩 TP | 仅少卡时收缩 | 够卡时 `DP = cnt / TP` |
| 未知硬件 generic 单机 | 未知模型无可信推荐 TP，全部卡组成一个 TP 组 | `TP = cnt` | `DP = 1`（不显式渲染） |
| DP 跨 Pod | TP 在 Pod 内不动，DP 按 `cnt` 缩放 | 不变 | `DP = P * (cnt / TP)` |
| TP 跨 Pod | 所有 Pod 的卡组成一个 TP 组 | `TP = world_size` | 不变 |
| PD：普通 1P1D | 按 `cnt` 派生单 Pod 并行度 | `TP = cnt` | `DP = 1` |
| PD：大 EP 显式分配 | 严格按 recipe 与 MaaS 六字段 | 不变 | 不变 |

## 单机

入口：`strategy/post_template.py` -> `strategy/parallelism.py::resolve_replica_tp_dp`。

| 条件 | 策略 | 说明 |
| --- | --- | --- |
| `cnt >= TP` 且 `cnt % TP == 0` | TP 不变，`DP = cnt / TP` | 卡够一个 TP 组，多余卡用于 DP 副本。计算出的 DP 与模板相同时不改写。 |
| `cnt >= TP` 但 `cnt % TP != 0` | 报错退出 | 卡数不是 TP 的整数倍，不能向下取整。 |
| `cnt < TP` | `TP = cnt`，`DP = 1` | 卡数不足一个 TP 组时收缩。必须通过显存和结构守卫，否则报错。 |

收缩 TP 前要满足三个条件：`cnt * 单卡显存 >= 1.5 * 模型权重`；`cnt` 是正的 2 次幂；模型配置可读取时，attention heads 必须能被 `cnt` 整除。

未知硬件同时使用 `_generic/default_model.yaml` 的 standalone 保底路径是唯一例外：模板 TP=1 仅用于未提供卡数时的占位；提供 `cnt` 后由独立 `strategy_generic_fallback` 层写入 `TP=cnt`，不生成 DP 参数（引擎默认 DP=1）。未提供 `cnt` 时保留模板值并记录 warning。用户 CLI 位于更高优先级，仍可覆盖 TP/DP。该例外不影响具体硬件/模型 recipe，也不影响 multi-node。

例子：

- 模板 `TP=1, DP=1`，下发 `cnt=2`：TP 仍为 1，DP 变为 2。
- 模板 `TP=4, DP=2`，下发 `cnt=8`：TP 仍为 4，DP 为 2。
- 模板 `TP=4, DP=2`，下发 `cnt=4`：DP 变为 1，覆盖模板中的 2。
- 模板 `TP=8`，下发 `cnt=4`：显存闸和结构守卫通过后，TP 收缩为 4，DP 为 1，并记录 warning 和 trace。

## 多机

入口：`strategy/topology_inject.py::coordinate_parallelism`。

模板中是否有 `node_rank` 决定布局：没有 `node_rank` 时为 DP 跨 Pod；有 `node_rank` 时为 TP 跨 Pod。

### DP 跨 Pod

TP 只在单个 Pod 内使用，DP 在多个 Pod 间复制。设 `P = pod_count`。

| 条件 | 策略 |
| --- | --- |
| `cnt >= TP` 且 `cnt % TP == 0` | TP 不变。每个 Pod 的 `dp_local = cnt / TP`，集群 `DP = P * dp_local`，`start_rank = index * dp_local`。 |
| `cnt < TP` 或 `cnt % TP != 0` | 报错，不向下取整。 |

### TP 跨 Pod

所有 Pod 的卡组成一个 TP 组，`world_size = P * cnt`。

| 条件 | 策略 |
| --- | --- |
| `world_size` 是 2 的幂 | `TP = world_size`，DP 保持模板值。 |
| `world_size` 不是 2 的幂 | 报错。 |

`world_size` 与模板 TP 不一致时，直接将 TP 调整为 `world_size`，DP 不变，并记录 warning。这个调整可能是收缩，也可能是增大；发生收缩时也会经过显存检查。

多机统一限制：

- `pipeline_parallel_size > 1` 直接报错，PP 暂不支持。
- `dp_local` 和 `dp_start_rank` 只能由公共函数计算，不能在不同位置重复推导。

## PD 分离

入口：`pd/planner.py::resolve_pd_topology`。PD 是 Prefill/Decode 分离部署。

### 普通 1P1D

recipe 的 `topology_input_policy` 为 `derived_1p1d` 时：

- Prefill 和 Decode 各一个 Pod、各一个进程。
- 不接收 MaaS 六个显式 PD topology 字段，全部由 `cnt` 推导。
- `TP = cnt`，`DP = 1`，`local-DP = 1`。
- `cnt` 必须是正的 2 次幂；不生成 `--data-parallel-*` 参数。

### 大 EP 显式分配

recipe 的 `topology_input_policy` 为 `explicit_allocation` 时：

- MaaS 一次下发 `PD_INDEX`、P/D 两侧的 TP、DP，以及 `DP_SIZE_LOCAL` 六个字段。
- 策略层不重新计算并行度，只校验字段、recipe 形状和 placement 是否闭合。
- 校验通过后，按六字段和当前 Pod 身份生成 rank 范围。

普通 PD 不下发这六个字段；大 EP 必须完整下发。大 EP 不收缩 TP。MaaS 在创建前保证 P/D 两侧的 `device_count` 一致。

## 配置选择和来源规则

普通 recipe 路径依次确定配置根、硬件类型、引擎版本、模型和 topology scenario。硬件按精确名称、别名、去显存后缀的顺序定位；均未命中且引擎根目录提供跨所有引擎版本兼容的 `_generic/models/default_model.yaml` 文件时，使用该通用资产尽力生成 standalone 或固定双 Pod multi-node 命令，并禁用 Wings Accel。该路径不校验 engine 与 `hardware.device` 是否匹配，只输出明确 warning；调用方负责二者兼容。PD 和 MindIE 不使用该硬件回退。模型按 `variant_name` 精确匹配、`name_pattern` 匹配、`default_model.yaml` 的顺序选择；有多个候选时直接失败。具体模型与 `default_model` 互斥，PD 只允许精确模型匹配。

显式引擎版本优先匹配精确目录。普通路径找不到时选择 latest，并在 warning 和 audit 中记录请求版本与实际版本；PD 和 SGLang 的特定契约要求精确版本时，不允许回退。

配置字典按层递归合并，列表和普通值整体替换。普通 recipe 的主要顺序：

```text
builtin_default
  -> model/default scenario
  -> request_default
  -> strategy_generic_fallback / strategy_device_count / strategy_topology_inject
  -> strategy_feature / strategy_feature_inject
  -> strategy_accel
  -> user_cli
```

`request_default` 仅在 fallback 的 `default_model` 未声明 `model`/`model_path` 时补入本次请求模型名，来源固定记录为 `<request>` / `request.model`，不能伪装成 YAML 来源。`strategy_generic_fallback` 仅用于 generic hardware fallback 的 standalone 且已传 `device_count`：写入 `TP=device_count`、保持 DP=1，不经过普通 `strategy_device_count` 的 DP 扩展；`user_cli` 仍可在更高层覆盖。

合并完成后不得绕开 trace 直接修改最终参数。`supported_params` 校验只告警，不删除参数，也不阻止启动。

## 关键源码位置

| 文件 | 职责 |
| --- | --- |
| `strategy/parallelism.py` | 公共计算：`dp_local_from_device_count`、`resolve_replica_tp_dp`、容量检查。 |
| `strategy/post_template.py` | 单机 `device_count_transform` 入口。 |
| `strategy/topology_inject.py` | 多机 `coordinate_parallelism` 入口。 |
| `core/config_resolver.py` | TP 收缩前置检查，以及 standalone/multi-node 解析编排。 |
| `pd/planner.py` | PD 拓扑解析、普通 1P1D 和大 EP 显式分配。 |
