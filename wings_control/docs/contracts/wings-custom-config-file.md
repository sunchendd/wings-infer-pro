# Wings-infer-pro 自定义传参（`--config-file`）功能说明

> **文档定位**：给**接手这段代码的研发同学**的特性交接文档。基于当前代码现状，说明自定义传参特性的能力边界、核心策略、当前状态与遗留待办、以及后续维护入口。
>
> **特指范围**：MaaS 第 3 页引擎运行时参数的**自定义传参方式**（`--config-file`），覆盖 **standalone / multi_node / PD** 三场景。三者在 wings-control 内部统一为一条"自定义传参"主线，本文档整合说明。
>
> **实现状态**：三场景**均已按既定方案完成开发**（standalone、multi_node、PD）。剩余两条**后续待办/规划**见 **§5**（前端模板对齐收口、custom PD 支持 accel）。

---

## 目录

- [1. 特性概述](#1-特性概述)
- [2. 新旧方案差异（交接核心）](#2-新旧方案差异交接核心)
- [3. 能力边界](#3-能力边界)
- [4. 策略说明](#4-策略说明)
- [5. 后续待办（规划）](#5-后续待办规划)
- [6. 维护说明（研发接手）](#6-维护说明研发接手)
- [7. 附录](#7-附录)

---

## 1. 特性概述

### 1.1 它是什么

MaaS 配置页面把 `wings_start.sh` 的参数分成三个逻辑页：

| 分页 | 参数 | 传参方式 |
|------|------|----------|
| 第 1 页 | `--model-name` / `--model-path` / `--port` | 始终 CLI |
| 第 2 页 | `--engine` / `--gpu-usage-mode` / `--device-count` 等启动引导参数 | 始终 CLI |
| 第 3 页 | 引擎运行时参数（长度/序列数/批处理/显存等） | **配置传参** 或 **自定义传参** |

第 3 页有两种**输入方式**（MaaS 页面层的区分，与 wings-control 内部实现无关）：

- **配置传参方式**（面向小白）：第 3 页只暴露少量参数走 CLI，其余由 wings-control 按 recipe 补齐。
- **自定义传参方式**（面向高阶）：第 3 页参数自由，通过 `--config-file` JSON（`params` + `env`）传入，由用户自管。

本特性实现的是**自定义传参方式**。

### 1.2 config-file JSON 格式

```json
{
  "params": { "tensor_parallel_size": 2, "gpu_memory_utilization": 0.9, "max_num_seqs": 256 },
  "env":     { "OTEL_RESOURCE_ATTRIBUTES": "service.instance.id=$(hostname)", "VLLM_PORT": "18000" }
}
```

- `params`：引擎运行时参数（引擎原生参数）。支持 kebab-case（如 `tensor-parallel-size`），内部归一 snake_case；**不做字段映射/解释**，用户对参数内容负责。
- `env`：环境变量，engine 侧启动前注入。值可含 `$(hostname)`/`$VAR`，双引号包裹走 unsafe 渲染（跳过安全校验），在 shell 执行时展开。用户可注入任意 shell 命令——此安全边界让步是既定设计（"用户对自己的输入负责"）。

### 1.3 运行时流程（双容器）

```
k8s 下发 pod
  ├─ wings-control 容器:  bash wings_start.sh <参数>  →  python -m wings_ctl <参数>
  │        （解析参数 / 匹配配置 / 生成脚本，只生成产物，不拉起 engine）
  │        产物写入共享卷: /shared-volume/start_command.sh (+ repro.sh + audit.json)
  └─ engine 容器:         bash /shared-volume/start_command.sh  →  拉起 vllm serve ...
```

### 1.4 三种部署场景（均已实现）

| 场景 | 识别 | 说明 |
|------|------|------|
| standalone | 无 `--distributed`、无 `PD_ROLE` | 单 Pod 单节点 |
| multi_node | `--distributed` + env 三件套（`MASTER_IP`/`NODE_IPS`/`RANK_IP`） | 跨 Pod 部署一个模型副本 |
| PD 分离 | `PD_ROLE=P`/`D` | prefill/decode 分离；单 Pod PD 也支持 |

> 接手提示：三场景在 wings-control 侧并不是三条各自独立的代码路径，而是**一条自定义传参主线 + 一个按场景补齐“用户填不出的运行时参数”的策略层**（见 §4）。

---

## 2. 新旧方案差异（交接核心）

> 本特性迁移到新版 Wings-infer-pro 后，与旧版实现存在**根本性架构差异**。接手人最容易踩的坑就是用旧版心智去理解新版代码，务必先读透本章。

### 2.1 配置资产与架构差异

| 维度 | 旧版 Wings-infer | 新版 Wings-infer-pro |
|------|------|------|
| 配置资产 | JSON（`nvidia_default.json` / `pd_config.json` / `distributed_config.json`） | recipe YAML（`model.yaml` + `_platform.yaml`，按 engine×硬件族×模型组织） |
| 配置合并 | 4 层，无追溯 | 8+ 层 trace-aware 合并，每参数带 `TracedValue` 来源链 |
| 入口 | `wings_start.sh` → `python -m wings_control` | `wings_start.sh` → `python -m wings_ctl`（纯透传，只生成产物） |
| 分布式架构 | **运行时** Master-Worker（Master API 分发参数到 Worker） | **配置时**拓扑推导（单进程解析期合并，无运行时 Master-Worker） |
| PD 分离 | 已实现（`PD_ROLE` + `pd_config.json` 注册表 + external-lb fork） | 已实现（custom 路径：RecolvedPdTopology + ProcessPlan，见 §4.4） |
| `--config-file` | 已实现（两种方式共享生成逻辑） | 已实现（两条独立支线，见下） |

### 2.2 核心差异：两条支线（旧版共享逻辑，新版分叉）

> 这是本特性与旧版**最根本的差异**，也是新版自定义传参的设计核心。

**旧版**：配置传参和自定义传参**仅是 `wings_start.sh` 的传参方式不同，内部生成 `start_command.sh` 的逻辑完全相同**——不是两条独立代码路径，无分叉点。

**新版**：不仅区分入口传参，内部生成逻辑也是**两条支线**：

```
cli.main()
  ├─ 无 --config-file → resolve_pipeline()         # 支线 A：配置传参（现有 CLI 路径，完全不变）
  │                       └─ resolve_config()      # 经 recipe(model.yaml) 匹配 + 8 层 trace 合并
  └─ 有 --config-file → resolve_pipeline_config()  # 支线 B：自定义传参（新增）
                          └─ resolve_custom_config() # 跳过 recipe 匹配，参数以 config-file 为准
```

- **支线 A（配置传参）**：走 recipe 匹配，8 层 trace 合并生成 `ResolvedConfig`。**完全不变**。这里所谓的"config 传参"依赖 recipe YAML。
- **支线 B（自定义传参）**：**跳过 recipe 匹配**（无 scenario 选择 / `feature_overlay` / `device_count_transform` / `coordinate_parallelism` 这些依赖 recipe 的环节），参数主源是 config-file JSON。

两条支线互不干扰：不传 `--config-file` 时现有逻辑零改动；传了走独立 `resolve_custom_config()`。

> **为何新版要分叉而非沿用旧版共享逻辑**：新版中"自定义传参方式"的定位是**用户自管参数、不依赖 recipe**。故独立成支线 B，跳过 recipe，参数以 config-file 为准，仅黑名单拦截。

---

## 3. 能力边界

### 3.1 支持的引擎 × 部署方式

| 引擎 | standalone | multi_node | PD |
|------|:---:|:---:|:---:|
| vllm | ✅ | ✅ | ✅ |
| vllm-ascend | ✅ | ✅ | ✅ |
| sglang | ✅ | ✅ | ❌（不支持） |
| mindie | ❌（不支持） | ❌（不支持） | ❌（不支持） |

### 3.2 支持的能力

- `params` 自由透传：引擎原生参数（含 kebab-case），内部归一 snake_case，canonical 别名归并（见 §4.6）。
- `env` 注入：含 `$(hostname)` 等 shell 变量 unsafe 展开（`allow_unsafe=True`）。
- 复用能力（与 recipe 解耦的下游全部复用）：`resolve_config_root` / `resolve_hardware` / `resolve_engine_version`、`pre_template_strategy`（topology 推导）、`feature_inject`、`apply_smart_accel`、`trace_merge`/`MergeLayer`、`select_node`、`apply_network_env_strategy`、`build_argv`/渲染/审计/校验。

### 3.3 边界（明确不做）

| 边界 | 说明 |
|------|------|
| **不做字段映射/解释** | config-file 的 `params` 只做 snake_case 归一 + canonical 别名归并，不解释参数含义（用户对内容负责）。`CLITranslator.translate_overrides` 不涉及 custom。 |
| **不做参数正确性校验** | 仅黑名单拦截（§4.3）+ 校验告警（如 `dp_local≤DP`），不阻断推理服务拉起。参数有误，交由引擎报错兜底。 |
| **sglang × PD 首期不支持** | PD 派生器仅登记 vllm / vllm-ascend；sglang 走 skip 兜底（不崩溃、记 note）。 |
| **mindie** | multi_node 派生与前端模板均暂不提供，待其派生层落地后补。 |
| **自定义 PD 不启用 accel** | 与配置传参 PD 一致：**无论 accel 开关都直接忽略**（不获取、不 merge、不报错）。注意"不启用 accel"≠"昇腾不能跑 PD"，仅是不叠加 accel 加速 feature 层。 |
| **黑名单是内部规则** | 用户视角 config-file 自由填写，不出现"黑名单/哪些键不能填"文案；黑名单内键被静默弃置 + audit，不阻断、用户无感。 |
| **`env` 安全边界让步** | 用户 env 值走 unsafe 渲染可注入任意 shell 命令——既定设计，用户在自定义方式下自担风险。 |


### 3.4 复用边界速查

| 模块 | custom 复用？ | 说明 |
|------|--------|------|
| `resolve_config_root`/`resolve_hardware`/`resolve_engine_version` | ✅ | 不依赖 recipe |
| `pre_template_strategy` | ✅ | topology 推导直接复用 |
| `CLITranslator.translate_overrides` | ❌ | 配置传参专属；custom 输入是 json params，不做字段映射 |
| `feature_inject_transform` / `apply_smart_accel` | ✅ | 只依赖 switches+engine（custom PD 例外：忽略 accel） |
| `trace_merge`/`MergeLayer` | ✅ | 纯函数，layers 不同而已 |
| `select_node` | ✅ | 判 head/worker/index |
| `apply_network_env_strategy` | ✅ 两条支线共用 | post-merge 按本 Pod IP 覆盖通信 env（`HCCL_IF_IP`/`*_SOCKET_IFNAME`） |
| `substitute_literal_placeholders` | ❌ custom 不用 | recipe 专属（处理 yaml `$local_ip`/`$HEAD_IP`）；custom 由策略层直接派生真实值 |
| `build_argv`/`render_param_tokens`/`key_to_flag` | ✅ | 透传参数进 traces |
| `render_env_export`/`script_builder`/`emit_audit`/`emit_startup_summary` | ✅ | 纯消费 ResolvedConfig |
| `validate_engine_params` | ✅ | warn-only |
| `dp_local_from_device_count`/`dp_start_rank` | ✅ | 公共核，身份键派生复用 |
| `resolve_family_dir`/`load_model_config`/`_select_scenario`/`feature_overlay_transform`/`device_count_transform`/`coordinate_parallelism` | ❌ 跳过 | 依赖 recipe / 模板 TP |

---

## 4. 策略说明

### 4.1 两条设计原则

1. **参数用户自管**：config-file 原则上只填引擎原生参数，框架不替用户校验正确性（仅黑名单拦截 + 校验告警）。用户对所填参数负责。
2. **用户填不出的平台派生**：IP / 身份 / 拓扑类参数（取决于 Pod 调度后的运行时状态）由 wings-control 自动推断派生。注意**各引擎需要派生的参数不同**，有一个小策略层按引擎派生（`strategy_multinode_custom`，PD 类似）。

### 4.2 参数与 env 优先级

**engine_config 层序**（低 → 高）：

```
builtin_default < strategy_feature_inject < strategy_accel < config_file < user_cli
```

- accel 优先级低于 config_file：嵌套 dict 参数走 `trace_merge` 深合并，非整体替换（见 §4.5）。
- `feature_inject`（SmartQoS/Trace/Metrics）只依赖 `feature_switches + engine`，custom 路径复用。
  - 链路追踪：该开关在第二页，custom 支持。
  - SmartQos、Metrics：这两个开关在第三页，custom不支持。
- accel 由 `apply_smart_accel` 独立定位 smart-accel YAML（custom PD 例外：忽略 accel）。

**env 层序**（低 → 高）：

```
strategy_feature_env < config_file_env
```

### 4.3 黑名单（params 收口，内部规则）

引擎原生参数随版本扩充，原则上不限制用户配置；但为避免与内部逻辑冲突，内置黑名单过滤。分 3 类：

| 类别 | 禁止 key（snake_case） | 理由 |
|------|----------------------|------|
| 归 CLI（第 1/2 页） | `model` `model_path` `served_model_name` `host` `port` | 归属 CLI，避免抢占 |
| 框架权威派生键 | `nnodes` `node_rank` `master_addr`（vllm 系）`headless`  `data_parallel_start_rank` `data_parallel_address` `data_parallel_rank` `HCCL_IF_IP` `*_SOCKET_IFNAME` | 框架按 index/device_count/TP/RANK_IP/nic 派生，用户填不出 |

**关键例外（不在黑名单，用户透传）**：

> **总原则：用户能填的都让用户填，仅派生用户填不出的值。** （`node_rank`/`master_addr`/`headless`/`data_parallel_start_rank`/`data_parallel_address`/`data_parallel_rank`/IP 网卡类等）。

- **全局 `data_parallel_size`**：用户并行度决策，未填默认 DP=1。派生层据 `data_parallel_size` 判布局：`dp>1` → DP_across → 框架派生 `start_rank`/`address`；`dp=1` → NONE（不派生 DP 通信参数）。
- **`data_parallel_size_local`**：需要用户填写（standalone / multi_node / PD 均如此）。PD 场景它作为"用户可填"进 Pod 级生效值，在 ProcessPlan 展开中再拆成每进程 `dp_size_local=1`（§4.4）。
- **`data_parallel_rpc_port`**：用户可填，未填引擎默认 29550。
- **`dist_init_addr`（sglang）**：集群寻址 `host:port` 的**端口部分用户可填**（host 由派生层覆盖），故移出黑名单；未填端口缺省 5000。

**黑名单行为**：黑名单内键无论用户怎么填（填了/改错/删除）都不影响 wings-control——静默忽略用户值、采用框架派生值，记 audit + debug 日志提示（排障可见、用户无感，不阻断启动）。


### 4.4 PD 分离策略（核心）

> 自定义 PD 的设计核心是"**概念统一**"：**一个 PD 实例本质就是一个普通引擎实例（仅多一个 `kv_transfer_config`），运行在某个拓扑里**。

#### 4.4.1 概念统一与基线选择

每个 P/D 实例都是独立 Pod、各带一份 config-file。按 Pod 数选择基线：

| 场景 | 判定 | 继承基线 | 平台额外补充 |
|---|---|---|---|
| 单 Pod PD | `len(NODE_IPS) == 1`（或 placement 单 Pod） | **standalone** | per-rank ProcessPlan 展开、engine_id、DP/TP/DP_LOCAL fallback |
| 跨 Pod PD | `len(NODE_IPS) > 1` | **multi_node** | 继承 multi_node 的 nnodes/node_rank/master_addr/网络 env + per-rank ProcessPlan |

```
resolve_pipeline_custom
  → 传入 request.pd_input
  → 判定 PD（PD_ROLE=P/D）
  → engine 分派（vllm / vllm-ascend 已登记派生器；sglang 未登记走 skip 兜底）
  → accel：无论开关都直接忽略，不获取、不 merge
  → 按 len(NODE_IPS) 选 standalone / multi_node 基线
  → 基线共有流程（参数规范化、黑名单、env 合并、生命周期、渲染）
  → PD 扩展（fallback、校验、ProcessPlan 展开、engine_id）
```

> ⚠️ 跨 Pod PD 的 `target.topology` 仍是 **`PD_PREFILL` / `PD_DECODE`**，**不会改为 `MULTI_NODE`**；只是复用 multi_node 的节点间派生逻辑（nnodes/node_rank/master_addr/网络 env）作为内部基线。因此不会误触 `script_builder.py` 的 `topology==MULTI_NODE` worker 跳过判定——PD 走 `process_plan` 分支。**实现/维护时不得以"topology 是否 MULTI_NODE"作为 PD 跨 Pod 的判定**，要显式按 Pod 数/placement 分支。

#### 4.4.2 并行三字段解析（DP / TP / DP_LOCAL）

config-file 优先、MaaS ENV 兜底：

| 参数 | 用户填（config-file） | MaaS 兜底 |
|---|---|---|
| `data_parallel_size` | 可填 | `PD_PREFILL_DP_SIZE` / `PD_DECODE_DP_SIZE` |
| `tensor_parallel_size` | 可填 | `PD_PREFILL_TP_SIZE` / `PD_DECODE_TP_SIZE` |
| `data_parallel_size_local` | 可填（全面豁免） | `DP_SIZE_LOCAL` |

逐字段规则：

```
config-file 明确填写  → 生效值 = 用户值，source = config_file
config-file 未填       → 若 MaaS ENV 存在，生效值 = MaaS 值，source = maas_env
                      → 若 MaaS ENV 也缺失，报「无法确定完整 PD 并行配置」
```

- **用户值永不被 MaaS 静默覆盖**。
- 「字段为 `null`」≠「字段缺失」：显式 null 视为用户提供了非法值，直接报错；字段 key 不存在才走兜底。
- 三字段可各自缺失，共 8 种组合，统一解析为**有效三元组**后走同一套校验（不因组合不同走不同规则）。
- **生效值校验（唯一强制阻断处）**：三字段都必须为正整数（0/负/bool/字符串 → 报错）；随后 `dp_local ≤ dp`（报错）、`tp × dp_local ≤ device_count`（容量不足报错）。
- 用户 vs MaaS 值**不一致 → 仅 warn-only 审计**（`mismatch`），不覆盖、不阻断；但 mismatch 合成出的生效三元组若触发非法条件，仍按生效值阻断。

#### 4.4.3 DP=1 不派生 `data_parallel_rank`（详见 §4.5.2）

PD 分离场景下，`data_parallel_size==1` 时**不派生** `data_parallel_rank`（否则误触发 vLLM external LB、被拒启动）。完整规则与实现锚点统一收在 **§4.5.2**。

#### 4.4.4 engine_id 恒由 PD_INDEX 派生

`kv_transfer_config.engine_id` 恒黑名单 + 由 `PD_INDEX` 派生：

```
strategy_pd_identity 注入 kv_transfer_config.engine_id = str(PD_INDEX)
```


#### 4.4.5 kv_role 用户可配

`kv_role` 保持用户可配置（engine-native），平台不静默改写，只做兼容性校验：与当前 `PD_ROLE` 不符（Prefill 配成 Decode 所需角色）时报错。用户不填则不伪造 connector 默认。

#### 4.4.6 ProcessPlan 展开（单/多进程）

- **单进程（DP_LOCAL==1）**：`layout=single_process`，1 进程 / 1 endpoint，`dp_size_local=1`，`port=backend_base`（17000）。
- **多进程（DP_LOCAL>1）**：每 local DP rank 一进程（fail-together），进程数=DP_LOCAL：

| 进程项 | 值 |
|---|---|
| `port` | `backend_base + local_index`（17000, 17001, …） |
| `dp_rank` | `rank_start + local_index` |
| `dp_size_local` | 1 |
| `visible_devices` | `device[local_index*TP : (local_index+1)*TP]`（TP 卡组切片） |

- 设备切片合法性以 `tp×dp_local ≤ device_count` 校验为前提。
- `dp_address` / `dp_external_lb` 由框架派生，用户不可改。
- `data_parallel_rpc_port`：config-file 提供则按用户值；**跨 Pod 一致性由用户保证**（PD 是 logical instance 跨多 Pod，各 Pod 必须同一 rpc_port 才能互相通信），平台不强制。
- 每进程 env 复制**必须保留 `allow_unsafe`**（对比 recipe 的 `_build_pd_process_env_traces` 会丢 `$(hostname)`），否则多进程下 `$(hostname)` 静默丢失。

#### 4.4.7 PD 黑名单（§4.3 的 PD 映射）

```python
_CONFIG_FILE_PARAMS_BLACKLIST_PD = {
    "engine_id",        # 嵌套 kv_transfer_config.engine_id，恒由 PD_INDEX 派生
    # port/host/nnodes/node_rank/master_addr → common；data_parallel_rank/address → 引擎黑名单
}
_CONFIG_FILE_ENV_BLACKLIST_PD = {
    "ASCEND_RT_VISIBLE_DEVICES",   # 进程级设备切片
    "RANK_IP", "MASTER_IP", "NODE_IPS",
}
```

**豁免**：`data_parallel_size_local` 已在引擎黑名单**全面豁免**（所有场景用户可填，§4.3），并非 PD 特有——故 `data_parallel_size` / `tensor_parallel_size` / `data_parallel_size_local` 三字段均不放入 PD 黑名单（由 §4.4.2 fallback 解析，不由黑名单决定）。PD 与 standalone/multi_node 的差异仅在于三字段的**取值来源解析**（config-file 优先、MaaS 兜底），而非豁免与否。

### 4.5 DP 参数"不派生"特判

> 两条路径在特定并行配置下**不派生某些 DP 通信参数**（避免误触发 vLLM 的 LB 模式 / 参数组合被拒），统一归此。

#### 4.5.1 multi_node 普通 custom（`DP_across`）

- **hybrid / external / multi-port external 的 worker 不注入 `headless`**：这几类模式每个 Pod/rank 各自对外提供 API，不是"由 master 调起的纯计算节点"。注入 headless 会与 hybrid 互斥（vLLM `arg_utils` 断言）或丢失对外端点。
- **external 不派生 `data_parallel_start_rank`**：vLLM `serve.py` 在未显式设 hybrid/multi-port 时把 `start_rank is not None` 判为 hybrid，与 external 撞成"多种 LB 模式"拒绝启动；multi_node 下 DP rank 由 vLLM 依 `node_rank` 自推断。**hybrid / multi-port 仍派生 start_rank**（自身带标志，不撞车）。
- **external 要求 `data_parallel_size_local==1`；`>1` 需 per-rank 进程展开，而该展开 multi_node 普通 custom 未实现（PD 已实现，见 §4.5.2）**：故 external + `size_local>1` 对用户仅**告警**引导走 PD 分离部署，不校验、不硬报错（保留存量 `external + size_local==1`）。
- **multi-port external 天然支持 `size_local>=2`**：per-rank 展开由 vLLM 内建 supervisor 完成，普通 custom 透传即可、框架零展开（约束在用户侧：`dp>1`、`size_local>=2`、`dp % size_local == 0`）。

#### 4.5.2 PD（DP=1 不派生 `data_parallel_rank`）

**为什么**：PD 分离场景下，`data_parallel_size == 1` 时**不能开启 external LB**。但 vLLM 的规则是：**只要 `data_parallel_rank` 不为 `None`，就会自动开启 external LB**。因此，若 `data_parallel_size=1` 仍派生 `data_parallel_rank`，会误触发 vLLM 的 external LB，而 vLLM 在 DP≤1 时**拒绝该参数组合**，导致启动失败。

**策略**：**仅当有效 global `data_parallel_size > 1` 时才派生 `data_parallel_rank`**（及其配套 `data_parallel_size_local=1`）；DP=1 时不派生，避免误开 external LB。

**实现锚点**（`core/config_resolver.py`）：
- `_role_uses_external_dp(role_shape)` = `dp_size > 1`。
- `_pd_process_derive_vllm`：仅 `uses_external_dp` 时送入 `data_parallel_rank` = `rank_start + local_index`、`data_parallel_size_local=1`。
- ProcessPlan 中 `dp_rank = rank if uses_external_dp else None`。
- 另外：DP=1 且**用户显式填 `data_parallel_external_lb`（非 false）** 时，仅**告警**（vLLM 会拒绝该组合，但 custom 场景交用户负责，不阻断）。

**附**：`data_parallel_rank` 属平台权威键，config-file 黑名单拦截用户填写；PD 进程级也不伪造。不同 P/D 实例可由用户自由混选配置/自定义传参路径，故统一由 PD_INDEX 派生 `engine_id`，保证全局身份连续。

### 4.6 深合并 vs 整体替换（trace_merge）

`trace_merge` 对**嵌套 dict 递归深合并**：两边都是 dict 时逐个内层键合并，冲突键按优先级覆盖、未提及的内层键保留；标量/list/类型不一致则**整体替换**。

以 `strategy_accel`（低优先）与 `config_file`（高优先）在 `kv_transfer_config` 冲突为例——用户只写要改的内层键，未提及的保留 accel 注入值；trace 记录冲突键事件链 `[{accel,…},{config_file,…}]`。**list 是整体替换（非逐元素合并），改 list 字段须写全。**

### 4.7 canonical 别名归并（engine 感知）

用户可能在 config-file 写引擎原生 flag 的简写/双长名（vllm `-tp`/`-dp`/`-n`/`-r`/`-dpa`/`-dpp`，sglang `--tp-size`/`--dp-size`/`--nccl-init-addr`）。`_to_snake` 后、黑名单过滤前，加 `_canonicalize_config_file_params(params, engine=...)` 按引擎把别名归一到 canonical 键。**黑名单与派生层 `cfg.get` 只认 canonical 键**，故用户写长名或简写都能正确命中/读取。

关键结论：
- 黑名单只需认 canonical 键：`n`→`nnodes`、`r`→`node_rank`、`nccl_init_addr`→`dist_init_addr` 归并后命中黑名单被弃/透传，无需在黑名单穷举别名。
- 派生层 `cfg.get("data_parallel_size")`/`cfg.get("tensor_parallel_size")` 只读 canonical 键——归并在前，长名/简写都能读到。
- sglang `--dist-init-addr` == `--nccl-init-addr`（等价），统一归一到 `dist_init_addr`。

---

## 5. 后续待办（规划）

> 本章汇总**接手后需要跟进的两条待办/规划**，均建立在已完成的自定义传参实现之上（§5.1 是理解待办背景的模板机制说明）。代码侧三场景均已实现，剩余规划集中在前端模板资产对齐与能力扩展。

### 5.1 背景：模板机制（engine × 部署方式）

> **澄清：前端模板下发不是"新需求"。** FOA 前端本就提供统一的 JSON 模板（面向旧版自定义传参），但属于**旧模板**（不传并行度、含 `input-length`/`output-length` 等非引擎原生键），**不适用于 wings-infer-pro 实现的自定义传参**。新版自定义传参的差异在于：必须填engine原生参数，因此**必须按 engine × 部署方式展示不同的起始模板，而不能用统一的模板**（各引擎原生参数不同、部署方式派生参数不同）。因此需要 FOAI 前端按 engine × 部署方式下发对应起始模板初始化编辑框，用户在此基础上自由增删改。

**模板结构（建议稿，未拍板）**：派生参数（黑名单内 IP/网卡/per-node 位置参）拟**直接放进 `params`/`env`**，值用语义占位符 `<autofill:...>` 表达：

```json
{
  "params": {
    "trust_remote_code": true,
    "tensor_parallel_size": 16,
    "master_addr": "<autofill:master_ip>",
    "nnodes": "<autofill:nnodes>",
    "node_rank": "<autofill:node_rank>"
  },
  "env": {
    "GLOO_SOCKET_IFNAME": "<autofill:iface_name>"
  }
}
```


### 5.2 后续待办（规划）

> 接手人先看这一节，明确哪些已完成、哪些是你要跟进的待办。

| 状态 | 事项 | 说明 |
|------|------|------|
| ✅ 已完成 | 阶段 1 custom standalone | `--config-file` 独立支线 + 黑名单 + canonical 归并 + env unsafe 渲染 |
| ✅ 已完成 | 阶段 2 custom multi_node | `strategy_multinode_custom` 策略层，vllm/vllm-ascend/sglang |
| ✅ 已完成 | custom PD 分离 | 概念统一 + 三字段解析 + ProcessPlan 展开 + engine_id/kv_role（含 DP=1 不派生 data_parallel_rank，§4.5.2） |
| ✅ 已完成 | 配置传参 PD（recipe） | 既有能力，非本特性新增；custom 与之并存 |
| ⏳ **待办 1** | **新版自定义 JSON 模板落地 FOA 前端，更新后删除临时兼容代码** | 新版自定义 JSON 的实现需要 **FOA 前端更新模板**：按 engine × 部署方式下发起始模板（standalone / multi_node / PD，§5.1），替代当前仍生效的旧模板。**前端更新为新版模板后，删除临时兼容代码 `legacy_json_adapter`**（模块 + 接入点 + 测试，删除注意见 §6.5，勿回滚 accel 短路修复）。与前端约定模板内容与下发规则即可，模板不改代码解析逻辑，可独立推进。 |
| ⏳ **待办 2** | **自定义 JSON PD 暂不支持 accel，后续可支持** | 当前 custom PD 与配置传参 PD 一致，**无论 accel 开关都直接忽略**（不获取、不 merge，见 §3.3），即暂不支持 accel 加速层。**后续规划**：为 custom PD 叠加 accel 加速 feature，需按 §4.4.6 的 per-rank ProcessPlan 维度设计 accel 注入（目前 custom 侧未预留该机制）。 |

**明确不支持/不提供**：

- **mindie**：multi_node 派生与前端模板**不支持、不提供**（非待补；源头即排除，阶段 2 边界）。


---

## 6. 维护说明（研发接手）

### 6.1 文件地图（核心模块 + 入口）

| 模块/文件 | 职责 | 关键入口 |
|---|---|---|
| `wings_control/src/wings_ctl/cli.py` | CLI 入口，`--config-file` flag、`resolve_pipeline`/`resolve_pipeline_custom` 分派 | `_build_parser` / `main` |
| `wings_control/src/wings_ctl/core/config_resolver.py` | **核心**：`resolve_custom_config`（支线 B 主干）、黑名单、canonical 归并、`_resolve_custom_pd_config`（PD）、ProcessPlan 展开 | `resolve_custom_config` / `_resolve_custom_pd_config` / `_build_custom_pd_process_plan` / `_filter_config_file_blacklist` / `_canonicalize_config_file_params` |
| `wings_control/src/wings_ctl/strategy/multinode_custom.py` | multi_node 策略层：按 engine×拓扑×身份派生 per-node 参数/ENV | `strategy_multinode_custom` / `_derive_vllm` / `_derive_sglang` |
| `wings_control/src/wings_ctl/strategy/post_merge.py` | 网卡/IP 通信 env 的 Python 侧解析（`apply_network_env_strategy`） | `apply_network_env_strategy` |
| `wings_control/src/wings_ctl/strategy/topology_inject.py` | 拓扑注入、`select_node`（head/worker 判定）、`_PLACEHOLDERS` | `select_node` / `substitute_literal_placeholders` |
| `wings_control/src/wings_ctl/strategy/feature_inject.py` | feature 注入范式（注册表 + 引擎分派 + skip 兜底），策略层参照 | `feature_inject_transform` |
| `wings_control/src/wings_ctl/strategy/parallelism.py` | DP 拓扑派生公共核 | `dp_local_from_device_count` / `dp_start_rank` |
| `wings_control/src/wings_ctl/strategy/legacy_json_adapter.py` | 临时过渡适配层（FOAI 旧模板翻译，待办 1 落地后删除，§5.1） | `adapt_legacy_config_params` |
| `wings_control/src/wings_ctl/pd/` | PD 契约与拓扑（`input_contract.py`/`planner.py`/`recipe.py`） | `PdRuntimeInput` / `ResolvedPdTopology` |
| `wings_control/src/wings_ctl/rendering/script_builder.py` | 渲染 `start_command.sh`、ProcessPlan renderer | `_render_pd_process_plan` |
| `wings_control/src/wings_ctl/audit/startup_log.py` | 审计 / 启动日志 | `emit_audit` |

### 6.2 如何扩展新引擎（以 vllm / sglang 登记为例）

custom 的引擎扩展采用**注册表 + 引擎分派 + skip 兜底**范式（参照 `feature_inject` / `multinode_custom` / `_register_pd_process`），不是 if/else 硬编码。新增引擎需补齐 4 处：

1. **PD 进程派生器**：`config_resolver.py` 用 `@_register_pd_process(engine)` 注册（如 `_pd_process_derive_vllm`）；未登记引擎走 skip 兜底（不崩溃、记 note）。
2. **黑名单表**：`_CONFIG_FILE_PARAMS_BLACKLIST_BY_ENGINE` / `_CONFIG_FILE_ENV_BLACKLIST_*` 增补该引擎的权威派生键。
3. **canonical 别名表**：`_CONFIG_FILE_PARAM_ALIASES` 增补该引擎的简写/双长名 → canonical 键。
4. **multi_node 派生器**：`multinode_custom.py` 登记该引擎 multi_node 需派生的 per-node 参数/ENV（含 DP 通信参数）及 network env 策略。

> 各引擎 "multi_node 多出参数" 的对照（vllm / vllm-ascend / sglang / mindie）可作为新增引擎派生的参考锚点（§4 策略说明）。

### 6.3 两条支线分叉点（避坑）

- `cli.main()` 里 `args.config_file` 存在与否 → 分 `resolve_pipeline`（A）/ `resolve_pipeline_config`（B）。
- **改支线 A 的 recipe 逻辑不要以为会影响 custom**；反之亦然。两块代码路径独立。
- custom 跳过：`CLITranslator.translate_overrides`、`substitute_literal_placeholders`、`feature_overlay_transform`、`device_count_transform`、`coordinate_parallelism`（§3.4）。
- `substitute_literal_placeholders`（处理 yaml `$local_ip`/`$HEAD_IP`）custom 不用——custom 由策略层直接派生真实值，网卡/IP env 再经 `apply_network_env_strategy` Python 侧解析。

### 6.4 测试入口

- custom 解析/黑名单/canonical/legacy 适配：`tests/integration/test_custom_config_legacy.py`（14 例）等。
- **placeholder 不泄漏安全测试**：`test_e2_vllm_placeholder_dropped` / `test_e2_sglang_placeholder_covered`（锁死"占位符不会泄漏"承诺）。
- PD ProcessPlan / parallel resolution 审计 / DP_LOCAL 展开：PD 相关 integration 用例。
- 回归要点：custom standalone、custom multi_node、custom PD、recipe PD、配置传参 PD 行为互不破坏。

### 6.5 删除 `legacy_json_adapter` 的注意

过渡结束后（FOA 前端切新版模板）删除时，删除三处：模块文件、`resolve_custom_config` 接入点、对应测试；**保留 accel 短路修复**（`resolve_custom_config` 步 3 的 `collect_accel_switches` 短路是独立基础修复，勿回滚）。

---

## 7. 附录

### 7.1 关键提交

> 以下提交 hash 在**远程仓**（codehub 内部仓，见 `git remote -v`）可查，供交接核对实现历史。

| Commit | 内容 |
|--------|------|
| `8cea1ef` | Add `--config-file` custom param path（standalone + multi_node） |
| `c85b349c` | Custom PD config-file env injection and network key derivation |
| `528204b` | Fix PD DP=1 external data-parallel handling（对应 §4.5.2 DP=1 不派生 data_parallel_rank） |
| `61158c6` | Merge `fix/multinode-custom-hybrid-headless` into develop（MR !146），修 multi_node Hybrid/External DP worker 误注入 headless、external 误派生 start_rank（对应 §4.5.1） |

---

*文档结束。*