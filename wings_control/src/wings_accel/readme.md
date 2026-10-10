# wings_accel — SmartAccel 加速模块详细设计文档

> 范围:`src/wings_accel/`(13 个 Python 文件,~1900 行 + 随包 `smart-accel/` YAML 资产)。
> 状态基线:`pytest tests/wings_accel -q` 全绿(以实际运行为准,不固定用例数)。
> 本文整合历史设计文档(`docs/archive/wings-accel/` 走读 28W、收口 48、作者指南 55、文件渲染 54×2)与**当前代码真件**。代码与本文冲突时以代码为准。

---

## 0. 模块定位

`wings_accel` 是 **SmartAccel 加速特性模块**,负责把模型 YAML 中的 `smart_accel` 块展开成结构化的引擎参数(`engine_config` dict + 进程环境变量 `env` + pip 依赖 + 降级诊断),交给 wings-control 渲染成最终 vLLM 启动 argv / 容器 env。

**四类特性**:

| 特性 | expander | 作用 |
|---|---|---|
| **SmartDecoding** | `decoders.py` | 智能投机解码(eagle3 / mtp / suffix / draft_model / eagle / dflash …) |
| **SmartSparse** | `sparse.py` | 智能 KV 稀疏(performance_first / accuracy_first) |
| **KVOffload** | `offload.py` | 智能 KV 缓存卸载(cpu / disk / cpu_disk + QAT 压缩) |
| **CustomFeatures** | `custom.py` | 与三大特性正交的自由启动参数(`--mamba-cache` 等杂项) |

**关键设计约束**:

1. **与 wings_ctl 解耦** —— 可独立测试、独立发版;诊断信息走扁平 dict,不引入 trace 嵌套。
2. **MaaS 开关为唯一驱动** —— YAML 块「存在」≠「启用」;特性是否产出 100% 由 MaaS env 开关决定(`docs/48` 收口)。裸 `LoadFlags()` = 全关真 no-op。
3. **校验 warn-only** —— 永远不阻塞启动,警告只进日志。
4. **数据驱动渲染** —— YAML 里任意键值对都能表达成引擎参数,无需为每个 flag 写专门 Python 代码(`render.py`)。
5. **红线**:`src/wings_ctl` 主流水线绝不 `if engine ==`;`wings_accel` 包内仅保留一处引擎能力判定(QAT 仅原生 vLLM 支持,见 §6.3)。

---

## 1. 整体架构

```
                    ┌──────────────────────────────────────────────────┐
   入参四元组       │ api.resolve_smart_accel_from_config()            │
   engine/version/  │  ├─ find_smart_accel_yaml_path()  三层匹配定位   │
   hardware/model   │  └─ load_smart_accel_from_yaml()  解析 + 构造    │
   + MaaS flags ──► │     → SmartAccelInput(上下文 + 开关 + smart_accel)│
                    └────────────────────┬─────────────────────────────┘
                                         ▼
                   ┌──────────────────────────────────────────────────┐
                   │ core.func_smart_accel(smart_input)               │
                   │                                                  │
                   │  ① collect_smart_accel_warnings  (log-only)      │
                   │  ② sglang 短路 → 空 SmartAccelOutput              │
                   │  ③ _build_placeholder_context                    │
                   │  ④ 四 expander 各取 smart_accel 子块展开:        │
                   │     decoding / sparse / kv_offload / custom*     │
                   │  ⑤ resolve_conflicts  (扩展点,当前 no-op)        │
                   │  ⑥ merge_engine_params 合并 + packages 去重      │
                   │  ⑦ 组装 SmartAccelOutput                          │
                   └────────────────────┬─────────────────────────────┘
                                         ▼
                   SmartAccelOutput
                     ├─ 3 × scheme 名(decoding / kv_cache / sparse)
                     ├─ engine_params(合并后 env + engine_config)
                     ├─ diagnostics(仅降级特性)
                     └─ packages(pip 依赖,去重保序)
                                         │
                                         ▼
                   wings-control:env 注入容器 / engine_config → argv
```

**两类入口**:

- **自闭环入口**(推荐):`resolve_smart_accel_from_config(engine, engine_version, hardware_family, model_name, flags, config_root)` —— 只依赖入参四元组 + 开关,自行定位包内/外部 smart-accel YAML 后解析。找不到 YAML 返回 `None`(语义是 no-op,不是异常)。出处 `api.py`。
- **主流水线**:`func_smart_accel(smart_input: SmartAccelInput) -> SmartAccelOutput` —— 只消费结构化输入,不读 YAML、不依赖文件路径。调用方负责组装 `SmartAccelInput`。出处 `core.py`。

```python
from wings_accel import resolve_smart_accel_from_config, LoadFlags

out = resolve_smart_accel_from_config(
    engine="vllm",
    engine_version="0.23.0",
    hardware_family="rtx_pro_5000_48G",
    model_name="Qwen3.5-397B-A17B-nvfp4",
    flags=LoadFlags(decoding_enabled=True, kv=True, memory_offload_size_mode="64"),
)
# out: SmartAccelOutput 或 None(无匹配 YAML)
```

---

## 2. 文件结构

```
src/wings_accel/
├── __init__.py          公共出口(re-export 全部 API)
├── api.py               自闭环入口 resolve_smart_accel_from_config
├── core.py              主流水线 func_smart_accel(7 步编排)
├── schemas.py           数据契约层(SystemConfig / ModelConfig / ... / SmartAccelOutput)
├── yaml_loader.py       YAML → SmartAccelInput + 三层路径匹配 + LoadFlags
├── memory_estimator.py  智能内存估算(auto 模式,CPU 卸载容量)
├── render.py            渲染层(占位符填充 + 配置文件计划 + 合并)
├── validators.py        输入提示(4 条 warn-only 规则)
├── decoders.py          SmartDecoding expander
├── sparse.py            SmartSparse expander
├── offload.py           KVOffload expander(cpu/disk/cpu_disk 三选一 + QAT)
├── custom.py            CustomFeatures expander(正交自由参数)
├── conflict.py          冲突仲裁(扩展点,当前 no-op)
└── smart-accel/         随包分发的生产 YAML 资产
    └── vllm/v{version}/{hardware_family}/models/{model}/*.yaml
```

| 文件 | 行数 | 职责 |
|---|---|---|
| `schemas.py` | 226 | 全部输入输出 dataclass + MaaS 来源注释 |
| `yaml_loader.py` | 488 | YAML 解析、三层路径匹配、LoadFlags、auto 内存 |
| `render.py` | 324 | 占位符单一判定点 + files 计划 + 两种合并 |
| `core.py` | 166 | 7 步管线编排 + 占位符上下文派生 |
| `memory_estimator.py` | 118 | 单常数最坏值内存估算 |
| `decoders.py` | 273 | draft_arch 专用匹配 + 错配守卫 + 通用草稿 + no_model 双分支 |
| `offload.py` | 138 | 三 scheme 三选一 + fallback + QAT 门控 + files 计划 |
| `sparse.py` | 96 | mode 匹配 + perf→acc 降级 |
| `custom.py` | 64 | always-on 方案深合并 |
| `api.py` | 51 | 自闭环入口 |
| `validators.py` | 45 | 4 条 warn-only 输入提示 |
| `__init__.py` | 66 | 公共导出 |
| `conflict.py` | 21 | no-op 扩展点 |

---

## 3. 数据契约 `schemas.py`

文件只定义数据结构,不含选择/渲染逻辑。所有可空字段用 `Optional`,可变默认值用 `field(default_factory=...)`。

### 3.1 输入侧

```python
@dataclass
class SmartAccelInput:
    hardware_config: SystemConfig        # 硬件族(定位 yaml)+ 卡数 + pod 内存
    model_config: ModelConfig            # 主模型元数据(name 定位 yaml / arch 选草稿)
    engine_config: EngineConfig          # 引擎标识(sglang → 全 None)
    deployment_mode: DeploymentMode      # PD 角色(prefill 节点跳过 decoding)
    smart_decoding_config: SmartDecodingConfig
    smart_kv_cache_config: SmartKVCacheConfig
    smart_kv_sparse_config: SmartKVSparseConfig
    smart_accel: Dict[str, Any] = {}     # smart_accel 模板块,精确读取自 model.yaml
```

各子配置与 MaaS 入参的对应(详见 `schemas.py` 各 dataclass docstring):

| 子配置 | 字段 | MaaS 来源 |
|---|---|---|
| `SystemConfig` | `gpu_count` | `--device-count`(int,必填) |
| | `pod_available_memory_gb` | `AVAILABLE_POD_MEM_SIZE`(int **MiB**,必填;入口 /1024 换算为 GB 后再扣 15GB——MaaS 页面下发口径补偿:页面 bug 实际下发=总内存−5GB,正确契约=总内存−20GB,页面修复后移除) |
| | `gpu_type` | 硬件族目录名(非 MaaS 直传,yaml 定位键) |
| `ModelConfig` | `model_path` | `--model-path`(主模型路径) |
| | `model_name` | `--model`/`-m`(yaml 定位键) |
| | `model_arch` | model.yaml `architecture`(decoders 选草稿) |
| `EngineConfig` | `name` | `--engine`(如 vllm / vllm-ascend) |
| | `version` | `ENGINE_VERSION` |
| `SmartDecodingConfig` | `enabled` | `ENABLE_SPECULATIVE_DECODE`(bool) |
| | `model_path` | `SPECULATIVE_DECODE_MODEL_PATH`(spec=true 时必填) |
| `SmartKVCacheConfig` | `enabled` | `ENABLE_KV_OFFLOAD`(一级开关) |
| | `memory_offload_enabled` | `ENABLE_KV_MEM_OFFLOAD` + `KV_MEM_OFFLOAD_SIZE` |
| | `memory_offload_size_mode` | `KV_MEM_OFFLOAD_SIZE`("auto"/数值 GB) |
| | `disk_offload_enabled` | `ENABLE_KV_DISK_OFFLOAD` |
| | `disk_capacity_gb` / `disk_path` | `KV_DISK_OFFLOAD_SIZE` / `KV_DISK_OFFLOAD_PATH` |
| | `qat_enabled` | `ENABLE_KV_QAT`(挂 disk 下) |
| | `qat_device_count` / `qat_compression_level` | `KV_QAT_INSTANCE_NUM` / `KV_QAT_COMPRESS_LEVEL` |
| `SmartKVSparseConfig` | `enabled` | `ENABLE_SPARSE`(bool) |
| | `mode` | `SPARSE_LEVEL`(performance_first / accuracy_first) |
| `DeploymentMode` | `pd_role` | `PD_ROLE`(P / D / none) |

> `KV_MEM_OFFLOAD_SIZE` 是「内存卸载大小」:下发 `auto` 表示智能推荐(走 `memory_estimator`);下发数值字符串表示固定 GB;空/false 表示不显式下发内存卸载。`yaml_loader._resolve_memory_offload` 解析它,组合 `ENABLE_KV_MEM_OFFLOAD` 语义。

### 3.2 输出侧

```python
@dataclass
class EngineParams:                # 单特性产出形态
    env: Dict[str, str]            # 进程环境变量(已填占位符)
    engine_config: Dict[str, Any]  # 结构化引擎参数(如 {"speculative_config": {...}})

@dataclass(frozen=True)
class PackageRequirement:          # 已解析的精确 pip 依赖(render 解析产出)
    name: str                      # YAML 声明的原始包名(交付用)
    version: str                   # YAML 声明的原始版本(如 v0.4.5;交付用)
    canonical_name: str            # 规范化包名(冲突比较键)
    canonical_version: str         # PEP 440 规范化版本或其他交付版本原文(冲突比较键)
    manifest: str                  # property,渲染为原始 "name:version"(交付 install.py)

@dataclass
class _FeatureOutput:              # expander 内部返回形态(不导出)
    scheme: str                    # 选中方案名(如 "eagle3" / "cpu" / "performance_first")
    engine_params: EngineParams    # 已渲染
    degraded: bool = False         # 是否降级
    degrade_reason: str = ""       # 降级原因
    packages: List[PackageRequirement] = []  # 规范化精确 pip 依赖

@dataclass
class SmartAccelOutput:            # 总输出
    smart_decoding_scheme: Optional[str] = None
    smart_kv_sparse_scheme: Optional[str] = None
    smart_kv_cache_scheme: Optional[str] = None
    engine_params: EngineParams = EngineParams()       # 合并后 env + engine_config
    diagnostics: Dict[str, Dict[str, Any]] = {}        # 仅降级特性,形如 {"decoding": {"degraded": True, ...}}
    packages: List[str] = []                            # 去重保序的 pip 依赖
```

**设计要点**:

- **scheme 字段只表达「选中了什么」**,未产出则为 `None`(不是 `disabled` 字符串)。
- **`engine_config` 是结构化 dict**,不是预渲染 argv。最终 argv 渲染由 wings-control 完成(避免本模块耦合引擎 CLI 形态)。
- **`diagnostics` 只承载 wings-control 推不出的降级信息**;未降级特性不出现,降级特性带 `degraded` + `degrade_reason`,原样落 audit。
- **`packages` 供 install 段拼 `--config` 依赖列表**,跨特性去重保序(`core.py` 用 `dict.fromkeys`)。
  `_FeatureOutput.packages` 是 `List[PackageRequirement]`(已规范化);`SmartAccelOutput.packages`
  是其 manifest 字符串列表。合法声明形态:缺失/`null`(→ 空依赖)、`name→version` dict、
  恰好一个冒号的 `name:version` 字符串、二者构成的 list(后两者为兼容旧形态);其余类型
  (如 int)或缺 version 的裸包名属确定性配置错误,抛 `SmartAccelPackageFormatError` 并穿透
  `apply_smart_accel()` fail-fast。版本允许非空交付标识:PEP 440 版本规范化,其他版本按
  原文比较(同 canonical 包名 + 不同版本比较键 → 抛 `SmartAccelPackageConflictError`;
  同版本重复声明自动去重);**交付保留 YAML
  首次声明的原始 `name:version`**——wings-accel `install.py` 按 manifest 键精确查找,
  镜像包目录名带 `v` 前缀(如 `packages/lmcache-ascend/v0.4.5`),改写会导致
  `Package not found`。

---

## 4. 主流水线 `core.py`

```python
def func_smart_accel(smart_input: SmartAccelInput) -> SmartAccelOutput:
    # ① 输入检查(log-only,不阻塞、不污染输出)
    for w in collect_smart_accel_warnings(smart_input):
        logger.warning("SmartAccel input warning: %s", w)

    # ② sglang 短路:不支持 smart accel → 空 output
    if (smart_input.engine_config.name or "").lower() == "sglang":
        return SmartAccelOutput()

    # ③ smart_accel 模板块 + 占位符上下文(从各子配置派生)
    smart_accel = smart_input.smart_accel or {}
    ctx = _build_placeholder_context(smart_input)

    # ④ 四 expander 各取子块(互不知道彼此)
    decoding = smart_decoding_expander(..., smart_accel.get("decoding"), ctx, pd_role=...)
    sparse   = smart_sparse_expander(..., smart_accel.get("sparse"), ctx)
    offload  = smart_kv_offload_expander(..., smart_accel.get("kv_offload"), ctx, engine_name=...)
    custom = None
    if decoding or sparse or offload:                      # custom 仅当前三者至少一项产出
        custom = smart_custom_features_expander(smart_accel.get("custom_features"), ctx)

    # ⑤ 冲突仲裁(扩展点,当前 no-op,原样返回)
    decoding, sparse, offload, _ = resolve_conflicts(decoding, sparse, offload, ..., ctx)

    # ⑥ 合并 EngineParams(env 覆盖 + engine_config 深合并)+ packages 去重保序
    engine_params = EngineParams()
    packages = []
    for feature in (decoding, offload, sparse, custom):
        if feature:
            engine_params = merge_engine_params(engine_params, feature.engine_params)
            packages.extend(feature.packages)
    packages = list(dict.fromkeys(packages))

    # ⑦ 组装(仅降级特性进 diagnostics)
    return SmartAccelOutput(
        smart_decoding_scheme=decoding.scheme if decoding else None,
        smart_kv_cache_scheme=offload.scheme if offload else None,
        smart_kv_sparse_scheme=sparse.scheme if sparse else None,
        engine_params=engine_params,
        diagnostics=_collect_diagnostics({"decoding": decoding, "kv_cache": offload, "sparse": sparse}),
        packages=packages,
    )
```

**关键决策**:

| 决策 | 出处 | 理由 |
|---|---|---|
| 校验 warn-only | `core.py` + `validators.py` | 能跑就跑,警告进日志,不阻塞 |
| `smart_accel` 块嵌入 `SmartAccelInput` | `yaml_loader` / `core.py` | loader 精确读取 model yaml,core 不做二次 I/O |
| 四 expander 无横向通信 | `core.py` | 横向交互只靠 `conflict.py` 在最后阶段仲裁 |
| conflict 在 expander 之后 | `core.py` | 冲突要看**最终产出状态**,不是输入 |
| custom 条件启用 | `core.py` | 自由参数不应在无任何 smart 特性时凭空产出 |
| 合并顺序 `decoding, offload, sparse, custom` | `core.py` | env 后者覆盖前者;engine_config 深合并,顺序影响同 key 标量覆盖 |

### 4.1 占位符上下文派生 `_build_placeholder_context`

`core.py` 从 `SmartAccelInput` 各子配置派生 `PlaceholderContext`:

- KV 容量/介质 ← `SmartKVCacheConfig`(memory_capacity_gb 经 `_memory_capacity_gb()` 读 loader 设的私有属性 `_memory_capacity_gb`)
- QAT ← `SmartKVCacheConfig`
- 草稿模型路径 ← `SmartDecodingConfig.model_path`

> `_memory_capacity_gb` 是 `yaml_loader` 在构造 `SmartKVCacheConfig` 后用 `setattr` 贴上的私有属性(`yaml_loader.py:190`),承载 auto 模式估算出的 GB 值;`core._memory_capacity_gb()` 把 `memory_offload_size_mode` 的字符串/数值统一解析回 int。该值不作为 `SmartKVCacheConfig` 的公开入参暴露。

---

## 5. 三个 Expander + CustomFeatures

所有 expander 签名一致:`(cfg, block, ctx, ...) -> Optional[_FeatureOutput]`。**产出 `_FeatureOutput` 或返回 `None`**——没有 `disabled`/`fallback_disabled` 状态字符串(旧设计的状态码分类已移除)。降级信息靠 `degraded` + `degrade_reason` 承载。

### 5.1 SmartDecoding(`decoders.py`)

投机解码方案选择。`block` 兼容两种写法:list 直接为方案序列;dict 取 `methods`(`_as_methods`)。

**返回路径**(`decoders.py:20-31`):

| 条件 | 结果 |
|---|---|
| `enabled=False` | `None` |
| `pd_role == "prefill"` | `None`(PD 分离时 prefill 节点不做投机) |
| 无 methods | `None` |
| 有草稿路径,但非本地挂载目录(缺 config.json / 传了 config.json 文件路径 / HF repo id / 未挂载) | warning + `None`(仅支持本地挂载草稿目录,不猜架构) |
| 本地草稿目录 + draft_arch 专用命中 | `enabled`(专用方法,优先级最高) |
| 本地草稿目录 + 专用架构错配(含专用方法关键字但资产未声明可消费方案) | warning + `None`(专用草稿头不是完整 LM,不喂其他方法) |
| 本地草稿目录 + 普通架构 + 资产声明通用草稿(draft_model 块) | `enabled`(资产声明,参数可按模型调) |
| 本地草稿目录 + 普通架构 + 无通用草稿声明 | warning + `None`(不内置合成、不降级 no_model) |
| 无草稿路径 + 有 no_model 方案 | `enabled`,取首序(至多一个) |
| 无草稿路径 + 无 no_model 方案 | `None` |

**方法分类 `_is_model_based`**:`requires_model_path: true` → `model_based`(需草稿路径);否则 `no_model`(架构无关)。

**priority 已不用**:
- model_based 分支按 draft_arch 匹配选定(与顺序无关);
- no_model 分支取首序(至多一个,多声明时 warning);
- sparse 已不用 priority。

**草稿路径注入**:YAML 中用 `$path` / `$draft_model_path` 令牌声明,由 `PlaceholderContext.draft_model_path` 渲染(`render._fill_str`),不在 Python 硬编码。

### 5.2 SmartSparse(`sparse.py`)

最简单。`block` 为 scheme list,每个 scheme 的 `name` 即 mode 门键(`performance_first` / `accuracy_first`)。

**返回路径**(`sparse.py:36-72`):

| 条件 | 结果 |
|---|---|
| `enabled=False` / 非 list / 空 | `None` |
| `cfg.mode` 命中 scheme.name | `enabled`,取命中**首个**(mode 在 yaml 唯一,多命中告警) |
| `mode=performance_first` miss + `accuracy_first` 存在 | `enabled(degraded, reason="performance_first_miss->accuracy_first")` |
| 仍无命中 | `None` |

**设计要点**:模块不解释 `hf_overrides` / `kv_cache_dtype` 等参数内容,纯选择 + 交给 `render` 渲染。`hf_overrides`(dict)→ `--hf-overrides '<json>'`;`kv_cache_dtype`(scalar)→ `--kv-cache-dtype fp8`(argv 渲染由 wings-control 完成)。

### 5.3 KVOffload(`offload.py`,最复杂)

**三 scheme 三选一**,由 `(memory_offload_enabled, disk_offload_enabled)` 组合决定(`offload.py:82-93`):

| (mem, disk) | 选中 scheme | 后端 |
|---|---|---|
| (T, F) | `cpu` | vLLM 原生 `OffloadingConnector`,**无 lmcache 包、无配置文件** |
| (F, T) | `disk` | lmcache(`LMCacheConnectorV1`),需 `lmcache` 包 + `lmcache_config.yaml` |
| (T, T) | `cpu_disk` | lmcache 同时管 cpu+disk(比 disk 多 `local_cpu:true` + `max_local_cpu_size`) |
| (F, F) | — | `None`(不卸载) |

**fallback**(`offload.py:95-105`):目标 scheme 缺失时——
- `cpu_disk` 缺 → 退化 `disk > cpu > None`(告警);
- `cpu` / `disk` 缺 → `None`(告警)。

> 这是当前**唯一的 scheme 选择模型**——按 name 三选一,不再深合并 cpu+disk,也不再有旧版的 `media` / `ladder` / `levels` 格式。`kv_offload` 是一个 scheme list,每个 scheme 的 `name ∈ {cpu, disk, cpu_disk}`(各最多一项,重名取后者)。

**CPU 卸载 key 随后端分叉**(占位符不同,故意的非 bug):
- NPU(vllm-ascend):`num_cpu_blocks`(块数),占位符 `{mem_gb_to_blocks}`(GiB→块,÷16 KiB)。
- 原生 vLLM(CUDA)≥v0.14:`cpu_bytes_to_use`(字节,全 TP 合计),占位符 `{mem_gb_to_bytes}`(GiB→字节)。原生侧静默忽略 `num_cpu_blocks`,故 CUDA 配置必须用 `cpu_bytes_to_use`。生产 `rtx_pro_5000_*/Qwen3.5` 用此形态。

**QAT 门控 + 配置文件计划**(`offload.py`):

disk / cpu_disk 命中且 scheme 有 `files:` 块时:
1. 算 `effective_qat = cfg.qat_enabled and engine_name == "vllm"`(三门:`cfg.qat_enabled` + vllm + disk 命中)。
2. `render_ctx = replace(ctx, qat_enabled=effective_qat)`。
3. `plan_scheme_files(files, render_ctx)` 只渲染 `GeneratedFile` 计划；wings-control 在正式产物阶段写入共享卷。
4. 注入派生 env `LMCACHE_QAT_ENABLED = "True"/"False"`(随 effective_qat)。

disk 命中但缺 `files:` 块 → 仅 warning，不产生文件计划也不注入(不阻塞启动)。

> `LMCACHE_CONFIG_FILE` 等指向文件的 env 由 scheme 的 `envs:` 字面量声明(作者写),**不再代码注入**;**仅 `LMCACHE_QAT_ENABLED` 一项仍代码注入**(它是派生 env,值依赖 engine ∧ qat,无法静态写死)。见 §8.2。

### 5.4 CustomFeatures(`custom.py`)

与三大特性正交的「自由特性」段,表达引擎级杂项开关(`--mamba-cache`、`--trust-remote-code` 等)。

- `block` 必须是非空 list,否则 `None`。
- **所有方案 always-on**:深合并各自 `cli_params`(`deep_merge_dicts`),`envs` 后者覆盖前者,一次性渲染进同一个 `EngineParams`。
- scheme 名拼接所有方案 name(如 `"Mamba prefix caching"`),仅用于诊断,不影响渲染。
- 由 `core` 控制门控:**仅当 decoding / kv_cache / sparse 至少一项产出时才调用**。

---

## 6. 渲染层 `render.py`

数据驱动扩展性的核心:YAML 里任意键值对都能被表达成引擎参数,无需为每个 flag 写专门代码。

### 6.1 占位符单一判定点 `_resolve_token`

占位符解析**只在一处判定**:`_resolve_token(token, ctx) -> Optional[str]`(`render.py:64-109`)。两个填充入口共用它,杜绝两处各判一次:

| 入口 | 用途 | 匹配方式 |
|---|---|---|
| `_fill_str(value, ctx)` | cli_params / envs 的**整值**(值 = 单个占位符或纯字面量) | 整值精确匹配 |
| `_fill_str_substr(value, ctx)` | `files:` content 的**多行文本** | 正则 `\{[a-zA-Z_]\w*\}` 逐个替换 |

**统一规则**:未识别 / 条件未满足的占位符 → 返回 `None` → 调用方**原样保留字面量**(不报错、不替换成 "0")。例外:`{mem_gb_to_blocks}` / `{mem_gb_to_bytes}` 恒有返回值(未启用 → "0");`{qat_device_count}` / `{qat_compression_level}` 恒渲染数值(使 `lmcache_config.yaml` 始终合法)。

> files content 是纯文本子串替换,因此 `{qat_device_count}` → `4`、`{qat_enabled}` → `true` 落进 YAML block scalar 后自然解析为 int / bool,**不带引号**——无需专门的原生类型渲染。

### 6.2 占位符总表

| 占位符 | 渲染为 | MaaS 来源 | 启用条件 | 公式 |
|---|---|---|---|---|
| `{memory_capacity_gb}` | CPU 容量(GB) | `KV_MEM_OFFLOAD_SIZE` | `ENABLE_KV_MEM_OFFLOAD` | — |
| `{disk_capacity_gb}` | 磁盘容量(GB) | `KV_DISK_OFFLOAD_SIZE` | `ENABLE_KV_DISK_OFFLOAD` | — |
| `{disk_path}` | 磁盘路径 | `KV_DISK_OFFLOAD_PATH` | 同上 | — |
| `{mem_gb_to_bytes}` | CPU 容量(**字节**) | 同 `{memory_capacity_gb}` | `ENABLE_KV_MEM_OFFLOAD` | `int(cap) × 1024³` |
| `{mem_gb_to_blocks}` | CPU 容量(**块数**) | 同上 | 同上 | `int(cap×1024) // 16`(16 KiB/块) |
| `{cpu_swap_space_gb}` | 恒 `0` | — | `ENABLE_KV_MEM_OFFLOAD` | 策略常量(swap_space=0) |
| `{qat_enabled}` | `true`/`false` | `ENABLE_KV_QAT` | 随 qat(effective) | — |
| `{qat_device_count}` | QAT 实例数(int) | `KV_QAT_INSTANCE_NUM` | 恒渲染 | — |
| `{qat_compression_level}` | QAT 压缩级(int) | `KV_QAT_COMPRESS_LEVEL` | 恒渲染 | — |
| `$path` / `$draft_model_path` | 草稿模型路径 | `SPECULATIVE_DECODE_MODEL_PATH` | decoding | — |

> 公式就地写死在 `_resolve_token` 里是**显式 Python 表达式**,不是字符串公式,**禁止 eval/exec**(不造公式 DSL)。改公式 = 改这一处代码 + 注释。

### 6.3 文件计划 `plan_scheme_files`

```python
def plan_scheme_files(files, ctx, volume=None, source_path_prefix="") -> List[GeneratedFile]
```

函数把 `files` 中的文本填充为 `GeneratedFile` 计划，不创建目录、不写文件。每项带目标路径、内容、权限、scope、运行时变量和 YAML 来源；wings-control 仅在非 dry-run 的产物阶段校验并写入共享卷。

- `None` / 空 → 返回 `[]`，无文件系统副作用；
- 元素非 dict 或缺 `name` / `path` → 跳过；
- 返回计划保持输入顺序，调用方不得假定目标文件已存在。

### 6.4 两种合并

| 函数 | 合并对象 | 语义 |
|---|---|---|
| `deep_merge_dicts(base, override)` | **未渲染** cli_params dict | 嵌套 dict 递归合并;标量/list last-write-wins;原地改 base |
| `merge_engine_params(base, override)` | **已渲染** EngineParams | env 后者覆盖前者;engine_config 深合并;返回新对象 |

`merge_engine_params` 供 `core` 合并多特性产出;`deep_merge_dicts` 供 `custom` 合并多方案 cli_params。

### 6.5 packages 提取 `extract_packages`

YAML `packages` 是**键值对**(name→version,无 list dash):

```yaml
- name: suffix
  packages:
    arctic-inference: 0.1.1
```

兼容旧形态:单字符串 `"name:version"` 及其构成的 list。输出保留 YAML 声明的原始
`["name:version", ...]`(与 install.py manifest 键精确匹配,镜像包目录名带 `v` 前缀)。
规范化值(包名 `canonicalize_name`、PEP 440 版本规范化或其他版本原文)仅用于
跨 feature 冲突比较,不改写交付内容;版本不要求符合 PEP 440。

非法形态是确定性配置错误,抛 `SmartAccelPackageFormatError`(不静默丢弃、不降级):

- 顶层非 dict/str/list 类型(如 `42`);
- 字符串缺 version(裸包名,如 `lmcache`)或多冒号(如 `a:b:c`);
- list 元素非 dict/合法 `name:version` 字符串(如 `[42]` / `["lmcache"]`);
- 空 name 或空 version。

多个 feature 对同一规范化包名声明不同版本 → `SmartAccelPackageConflictError`(同版本去重保序)。

---

## 7. 内存估算 `memory_estimator.py`

auto 模式下估算 KV 卸载可用 CPU 内存。**单常数最坏值模型,不查表**。

```
worker_count   = tp_size × dp_size                       (vLLM V1 进程模型)
engine_self    = base_overhead_gb + worker_overhead_gb × worker_count
                 ≈ 3G + 7G × (TP × DP)
margin         = container_memory_gb × margin_ratio       (默认 10%)
available      = container_memory_gb − engine_self − margin
swap_space     = 0   (启动设 swap_space=0,无 beam search 前提)

available < min_threshold_gb(默认 20) → enabled=False(关闭卸载)
```

- `worker_overhead_gb=7` 取自实测最坏值(MiniMax-M2.5 TP16 full graph 均摊 ≈ 6.2G/worker)+ 一档头;一个常数覆盖全部配置。
- `base_overhead_gb=3` = api server / engine core / coordinator 固定基座。
- `margin_ratio=0.10` 吸收 OS 预留与 RSS/PSS 波动,取代旧 `os_reserved` 固定值。
- 返回 `MemoryEstimate` dataclass,携带完整诊断字段;`disable_reason` 保留公式变量供 audit 定位。

调用方(`yaml_loader`)在 `memory_offload_size_mode="auto"` 时调用:`available >= threshold` → 回填容量;否则关闭 memory_offload(显式开启则保留用户意图 + 告警)。

---

## 8. YAML 定位与加载 `yaml_loader.py`

### 8.1 三层路径匹配 `find_smart_accel_yaml_path`

目录:`smart-accel/{engine}/v{version}/{hardware_family}/models/{model_dir}/*.yaml`。

MaaS 不下发精度参数,变体信号 = `--model-name` 带完整精度后缀(如 `Qwen3.5-397B-A17B-nvfp4`)。三层优先级(逐层回退,每层 1 命中→取 / >1 命中→报错 / 0 命中→落下一层):

| 层 | 匹配键 | 判定 | 性质 |
|---|---|---|---|
| ① 精确 | `model.variant_name` | 与 model_name 小写归一**精确相等**(非正则) | 确定性主路径 |
| ② 模糊 | `model.match[].name_pattern` | `re.search` 命中 | 家族级兜底 |
| ③ 兜底 | `model.name` / `model.model_id` / 目录名 / yaml stem | 精确相等 | 单变体向后兼容 |

全部 0 命中返回 `None`(上层 no-op)。>1 命中抛 `ValueError`(带候选清单,避免静默选错)。非法正则记日志后跳过,不中断全量扫描。

### 8.2 LoadFlags —— MaaS 唯一驱动

```python
@dataclass
class LoadFlags:
    kv: bool = False                         # ENABLE_KV_OFFLOAD
    sparse: bool = False                     # ENABLE_SPARSE
    disk: bool = False                       # ENABLE_KV_DISK_OFFLOAD
    qat: bool = False                        # ENABLE_KV_QAT
    disk_gb: int = 512                       # KV_DISK_OFFLOAD_SIZE
    disk_path: str = "/var/cache/lmcache"    # KV_DISK_OFFLOAD_PATH
    qat_devices: int = 2                     # KV_QAT_INSTANCE_NUM
    qat_level: int = 1                       # KV_QAT_COMPRESS_LEVEL
    decoding_enabled: bool = False           # ENABLE_SPECULATIVE_DECODE
    decoding_model_path: str = ""            # SPECULATIVE_DECODE_MODEL_PATH
    sparse_level: str = "performance_first"  # SPARSE_LEVEL
    pd_role: Optional[str] = None            # PD_ROLE
    memory_offload_size_mode: str = ""       # KV_MEM_OFFLOAD_SIZE("auto"/数值 GB)
    pod_available_memory_gb: int = 0         # AVAILABLE_POD_MEM_SIZE
    min_offload_threshold_gb: int = 20
```

**全字段默认 False / 空 → 裸 `LoadFlags()` = 全关真 no-op**(`docs/48` D2)。

**启用规则**(`yaml_loader.py:132-164`):
- `enable_kv = flags.kv`(纯 flag,**不再** `or has_kv`——YAML 块存在不自动启用任何特性);
- `enable_sparse = flags.sparse`;
- `memory_on = (memory_intent is True) and enable_kv and has_memory_method`(内存卸载另需 `KV_MEM_OFFLOAD_SIZE` 下发 auto/数值 **且** YAML 有内存方法:cpu/cpu_disk scheme 或选中的 backend);
- `disk_on = flags.disk and enable_kv and has_disk`(磁盘另需 YAML 有 disk scheme)。

> **模板存在性护栏**:即使开关开了,YAML 没有对应 scheme(cpu/disk/cpu_disk)也不产出。主开关开但无介质时不兜底、不凭空生成参数——offload expander 自然返回 `None`。

### 8.3 auto 内存回填

`memory_offload_size_mode="auto"` 时,从 `scenarios.*.engine_config` 读 TP/DP,结合 `pod_available_memory_gb` 估算:
- `available >= threshold` → 回填 `memory_capacity_gb`;
- 不足且**未显式开启** → 关闭 memory_offload + 告警;
- 不足但**显式开启** → 保留用户意图(取 `max(available, 0)`)+ 告警。

数值字符串(如 `"64"`)→ 固定 GB 值。最终容量经 `setattr` 贴到 `SmartKVCacheConfig._memory_capacity_gb`(`yaml_loader.py:190`),由 `core` 读回派生占位符上下文。

### 8.4 引擎配置读取

`_get_chosen_engine_config` 从 `scenarios.{topology}.strategies.{name}.engine_config` 取选中策略(第一个 `default_strategy=true`,否则第一个策略),读 `engine` / `version` / `tensor_parallel_size` / `data_parallel_size`。缺失返回默认 `EngineConfig(vllm / 0.22.0)`。

---

## 9. 冲突仲裁 `conflict.py`

**当前是 no-op 扩展点**:`resolve_conflicts` 原样返回三个特性输出 + 空 dict(`conflict.py`)。

```python
def resolve_conflicts(decoding, sparse, offload, decoding_block, ctx):
    """返回原始特性输出;当前 MTP + LMCache/KV offload 不再冲突。"""
    return decoding, sparse, offload, {}
```

历史上有 MTP × KVOffload 互斥规则(MTP 命中时降级 suffix 或禁用 decoding),现已移除——decoding / kv_offload / sparse 可同时生效。保留入口避免 core 流水线形状随规则开关变化;未来新增冲突规则在此处加。

---

## 10. 输入校验 `validators.py`

4 条 warn-only 规则(永远 `return warnings`,不 raise、不改输入):

| 规则 | 触发 |
|---|---|
| 开磁盘必须先开内存 | `kv.enabled and disk_on and not memory_on` |
| 磁盘路径不能空 | `disk_on and not disk_path` |
| 磁盘容量 sanity | `disk_on and disk_capacity_gb < 0` |
| 草稿路径缺架构 | `dec.enabled and model_path and not model_arch` |

> 适合放跨特性 / 用户意图提示,不适合放 YAML schema 强校验。warnings 由 `core` 写日志,**不进 SmartAccelOutput**。

---

## 11. 状态与诊断模型

当前模型比旧版(状态码 `disabled`/`fallback_disabled`/`enabled`)更简单:

| 产出 | 含义 | 触发 |
|---|---|---|
| `None` | 特性未产出 | 开关关 / PD prefill / 无 block / 无合格方案 / 目标 scheme 缺失 |
| `_FeatureOutput(degraded=False)` | 正常启用 | 命中方案 / scheme / 介质 |
| `_FeatureOutput(degraded=True, reason=...)` | 降级启用 | perf→acc / cpu_disk 退化 disk(decoding 无降级路径:有草稿路径时要么命中声明方案、要么直接 `None`) |

**diagnostics** 只收集 `degraded=True` 的特性(`core._collect_diagnostics`),形如:

```python
{"sparse": {"degraded": True, "degrade_reason": "performance_first_miss->accuracy_first"}}
```

未降级特性不出现;原样落 wings-control audit。降级原因汇总:

| 场景 | degrade_reason |
|---|---|
| sparse performance_first miss | `performance_first_miss->accuracy_first` |
| kv_offload cpu_disk 缺失退化 | (WARN 日志,scheme 退化非 degraded 标记) |

---

## 12. YAML 配置格式(作者指南)

### 12.1 顶层结构

```yaml
upstream_sources: [...]        # 来源追溯(wings_accel 不读)
model:                         # 模型身份(yaml_loader 读 name / variant_name / match / architecture / model_id)
  name: <家族名>
  variant_name: "<精确 --model-name>"    # 必填(docs/48 主路径)
  match:
    - name_pattern: "<家族正则>"          # 兜底
hardware_profile: {...}        # 硬件(yaml_loader 读 gpu_type / gpu_count)
scenarios: {...}               # 部署场景(yaml_loader 读 engine_config + TP/DP)
smart_accel:                   # ← 本模块核心
  decoding:    [ <方案>, ... ]
  kv_offload:  [ <scheme>, ... ]
  sparse:      [ <scheme>, ... ]
  custom_features: [ ... ]     # 可选
```

每个方案 / scheme 通用字段:`name` / `packages`(name:version)/ `cli_params`(结构化引擎参数)/ `envs`(K=V,支持占位符)。decoding 还有 `requires_model_path`(bool)与专用方案的 `draft_arch`(list)。kv_offload 的 disk/cpu_disk 还有 `files`(配置文件列表)。(`priority` 字段已无消费方,方案选择不按它排序,勿再声明)

### 12.2 decoding

```yaml
decoding:
  - name: mtp                       # no_model(架构无关;无草稿时取首序,至多一个)
    cli_params:
      speculative_config: { method: mtp, num_speculative_tokens: 3 }
    envs: {}
  - name: eagle3                    # model_based(需草稿)
    requires_model_path: true
    draft_arch: [eagle3]            # 专用方案按草稿架构匹配(数字边界),必须声明
    cli_params:
      speculative_config:
        method: eagle3
        model: $path                # $path 令牌 → 草稿模型路径
        num_speculative_tokens: 3
      enforce_eager: true           # 顶层 bool flag(不进 speculative JSON)
    envs:
      EARS_TOLERANCE: "0.3"
```

**动态投机解码(按 batch size 分档)**:`speculative_config` 还可声明 `num_speculative_tokens_per_batch_size`(上游 vLLM `SpeculativeConfig` 字段),按 batch size 闭区间动态选投机 token 数;`num_speculative_tokens` 保留作兜底。**必须写在 `speculative_config` 内**(提顶层会渲染成 `--num-speculative-tokens-per-batch-size`,vLLM 无此 flag)。紧凑写法:

```yaml
# speculative_config 内:
num_speculative_tokens: 3            # 兜底(调度表未命中 / DP 禁用动态 SD 时用)
num_speculative_tokens_per_batch_size: [[1, 64, 3], [65, 128, 1], [129, 512, 0]]
```

完整规则与渲染效果见 docs/55 §3。

### 12.3 sparse

```yaml
sparse:
  - name: performance_first         # name = mode 门键
    cli_params:
      hf_overrides: { use_index_cache: true, index_topk_freq: 8 }
    envs: {}
  - name: accuracy_first
    cli_params:
      hf_overrides: { use_index_cache: true, index_topk_freq: 4 }
    envs: {}
```

### 12.4 kv_offload(cpu / disk / cpu_disk)

```yaml
kv_offload:
  # cpu:纯 CPU 卸载,vllm 原生 OffloadingConnector。无 lmcache 包 / 无配置文件。
  - name: cpu
    cli_params:
      kv_transfer_config:
        kv_connector: OffloadingConnector
        kv_role: kv_both
        kv_connector_extra_config:
          cpu_bytes_to_use: "{mem_gb_to_bytes}"   # CUDA 字节口径;NPU 用 num_cpu_blocks: "{mem_gb_to_blocks}"
    envs: {}

  # disk:纯磁盘卸载,lmcache。需 lmcache 包 + lmcache_config.yaml(files 计划)。
  - name: disk
    packages:
      lmcache: v0.3.15
    cli_params:
      kv_transfer_config:
        kv_connector: LMCacheConnectorV1
        kv_role: kv_both
        kv_connector_extra_config:
          local_disk: "{disk_path}"
          max_local_disk_size: "{disk_capacity_gb}"
    envs:                                       # 指向文件的 env 在此字面量声明(非代码注入)
      LMCACHE_CONFIG_FILE: /shared-volume/lmcache_config.yaml
      LMCACHE_LOCAL_DISK: "{disk_path}"
      LMCACHE_MAX_LOCAL_DISK_SIZE: "{disk_capacity_gb}"
    files:                                      # 通用写文件:content 填占位符(子串)后落 SHARED_VOLUME_PATH/<name>
      - name: lmcache_config.yaml
        content: |
          chunk_size: 256
          local_disk: {disk_path}
          max_local_disk_size: {disk_capacity_gb}
          extra_config:
            wings:
              qat:
                enabled: {qat_enabled}          # 子串替换 → true/false
                module_name: kv_agent
                instance_num: {qat_device_count}   # → int(不带引号)
                loss_level: {qat_compression_level}
                log_enabled: 1

  # cpu_disk:比 disk 多 local_cpu:true + max_local_cpu_size:{memory_capacity_gb}
  - name: cpu_disk
    packages: { lmcache: v0.3.15 }
    cli_params: { kv_transfer_config: { ... local_cpu: true, max_local_cpu_size: "{memory_capacity_gb}", ... } }
    envs: { LMCACHE_CONFIG_FILE: /shared-volume/lmcache_config.yaml, LMCACHE_LOCAL_CPU: "true", ... }
    files: [ { name: lmcache_config.yaml, content: | ... } ]
```

### 12.5 custom_features

```yaml
custom_features:
  - name: Mamba prefix caching
    cli_params:
      mamba_cache: true            # bool → --mamba-cache
    envs: {}
```

### 12.6 ⚠️ 作者规则:async_scheduling × suffix

若该模型在 `config/engines/` 的 engine_config 里设了 `async_scheduling: true`,则其 smart-accel yaml 的 `decoding` 块**不得声明 `suffix`**(写 `mtp` 等即可)。判断看 `async_scheduling` 的**值**,与引擎名无关(不是 `if engine ==`)。

> `async_scheduling` 由 `config/engines/` 配置树持有,smart-accel 解析时看不到它(`api.py` 只吃四元组 + 开关)。故本规则目前是**作者侧约定**(写新 yaml 时自查),不靠运行时强制。存量违例(DeepSeek-V4-Flash 48G/72G)已修复:从 smart-accel 资产移除 `suffix`,仅保留 `mtp`。

---

## 13. 公共 API(`__init__.py`)

| API | 用途 |
|---|---|
| `resolve_smart_accel_from_config(...)` | 自闭环入口:入参四元组 + flags → 定位 YAML → 解析 → SmartAccelOutput(无匹配 → None) |
| `func_smart_accel(smart_input)` | 主流水线:SmartAccelInput → SmartAccelOutput(sglang → 空) |
| `load_smart_accel_from_yaml(path, flags)` | YAML → SmartAccelInput(快速验证 / 调试) |
| `load_smart_accel_from_config(...)` | 按硬件目录扫描定位 + 加载 |
| `find_smart_accel_yaml_path(...)` | 三层匹配定位 YAML |
| `build_smart_accel_yaml_path(...)` | 拼固定路径(兼容旧调用) |
| `LoadFlags` | MaaS 开关覆盖(全默认 False) |
| `PlaceholderContext` | 占位符上下文 |
| `render_engine_config` / `fill_envs` / `render_scheme` / `plan_scheme_files` | 渲染工具(供单测复用) |
| `deep_merge_dicts` / `merge_engine_params` | 合并工具 |
| 全部 schema dataclass | `SmartAccelInput` / `SmartAccelOutput` / `EngineParams` / `SystemConfig` / `ModelConfig` / `EngineConfig` / `SmartDecodingConfig` / `SmartKVCacheConfig` / `SmartKVSparseConfig` / `DeploymentMode` |

---

## 14. 关键设计决策(收口记录,`docs/48` + `docs/54`)

| # | 决策 | 理由 | 落码 |
|---|---|---|---|
| D1 | 删 `LoadFlags.no_auto` + auto-enable 分支 | 消除「yaml 存在即开」旁路,特性启用 100% 由 MaaS flag 决定 | `yaml_loader.py` |
| D2 | `LoadFlags` 全 flag 默认 False(含 `decoding_enabled`) | 裸 `LoadFlags()` = 全关真 no-op | `yaml_loader.py` |
| D3 | QAT 三门门控:`cfg.qat_enabled` + `engine=="vllm"` + `disk_selected` | 非 vllm 不支持 QAT 硬件压缩;QAT 依赖 LMCache 磁盘卸载 | `offload.py:117-128` |
| D4 | QAT `lmcache_config.yaml` 模板化 | QAT 配置进 yaml `files:`(占位符 + MaaS 填充),删 Python 硬编码 | `offload.py` + `render.plan_scheme_files` |
| D5 | priority 全删:sparse / decoding model_based / decoding no_model 均不消费(选择按声明与匹配规则,不排序;`_pick_priority` 已删) | mode 唯一 / 有草稿按 `draft_arch` 匹配 / 无草稿 no_model 至多一个取首序 ⇒ 无需 priority | `decoders.py` / `sparse.py` |
| D6 | 通用 `files:` 配置文件渲染 | lmcache / mooncake / mmc 统一生成计划,一种机制覆盖任意格式(`docs/54`) | `render.plan_scheme_files` |
| D7 | 占位符单一判定点 `_resolve_token` | cli_params/envs(整值)与 files content(子串)共用,杜绝两处各判一次 | `render.py:64` |
| D8 | 状态码简化为 None / `_FeatureOutput` | 旧 `disabled`/`fallback_disabled`/`enabled` 字符串分类多余,降级用 `degraded` 标记 | 各 expander + `schemas._FeatureOutput` |
| D9 | 扁平 dict 承载诊断 | 与 wings_ctl trace 解耦,模块可独立发版 | `schemas.SmartAccelOutput.diagnostics` |
| D10 | `engine_config` 结构化 dict,不预渲染 argv | 本模块不耦合引擎 CLI 形态;argv 渲染归 wings-control | `render.render_engine_config` |

> **红线合规**:D3 的 `engine == "vllm"` 判定在 `src/wings_accel/offload.py`(旁路包),不在 `src/wings_ctl` 主流水线;`src/wings_ctl` 的 `engine ==` 命中数不变。

---

## 15. 边界与已知约束

1. **生产 yaml 缺 disk scheme**:DeepSeek-V4-Flash / Qwen3.5 等目前 `kv_offload` 只有 `cpu`。要真正端到端用 QAT,需补 `disk` / `cpu_disk` scheme(带 `files:` 模板)。disk/cpu_disk 目前仅存在于测试 fixture。
2. **`LMCACHE_QAT_ENABLED` 仍代码注入**:它是派生 env(值依赖 engine ∧ qat),不是静态字面量,故未移入 yaml `envs:`。若要完全 yaml 化,需引入「effective-qat 大写布尔」占位符(当前无)。
3. **解析期无文件系统副作用**：`func_smart_accel` 只返回 `SmartAccelOutput.generated_files`；wings-control 在正式产物阶段写入文件，dry-run 不写盘。
4. **mooncake / mmc scheme 未落地**:它们是 KV 传输连接器,不套用现 `cpu/disk/cpu_disk` 选择模型;`files:` 语法已就位,等 scheme 落地时直接复用。
5. **`content` 占位符来源限 PlaceholderContext 现有字段**:mooncake 若要参数化 `master_server_address` / `world_size` 等,需先在 `PlaceholderContext` + `LoadFlags` 增字段。

---

## 16. 测试与验证

### 16.1 单元测试(`tests/wings_accel/`)

| 文件 | 覆盖 |
|---|---|
| `test_core.py` | 7 步管线 + sglang 短路 + custom 门控 + diagnostics |
| `test_decoders.py` | draft_arch 专用命中、专用错配守卫、通用草稿、miss→告警关闭、本地目录门控、no_model 首序 |
| `test_sparse.py` | mode 命中、perf→acc 降级 |
| `test_offload.py` | cpu/disk/cpu_disk 三选一、fallback、QAT 门控、files 计划、占位符 |
| `test_custom_features.py` | always-on 深合并、空 block→None |
| `test_conflict.py` | no-op 原样返回 |
| `test_render.py` | 占位符整值/子串、files 计划多格式、合并、packages 提取 |
| `test_validators.py` | 4 条 warn-only 规则 |
| `test_schemas.py` | dataclass 默认值 |
| `test_memory_estimator.py` | auto 估算公式 + 阈值关闭 |
| `test_yaml_loader.py` | 三层匹配、auto 内存、PD role、LoadFlags 默认 no-op |
| `test_smart_accel.py` | 集成 + trip-wire(LoadFlags 不带 `no_auto`) |
| `test_demo_all_on.py` | 三模型全开/全关 demo |

### 16.2 手动脚本验证

```bash
# 单模型矩阵(推荐):逐特性逐变体隔离测试,decoding/sparse/offload 全覆盖
PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py \
    tests/wings_accel/fixtures/smart_accel_all_features.yaml --matrix

# legacy 组合态:一次开启多特性(--kv/--sparse 等,与 LoadFlags 对齐)
PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py <yaml> --kv --memory-offload-size-mode 64 --sparse

# 全量扫描(vllm + vllm-ascend 所有模型)/ 路径覆盖检查 / 样本存档
PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py --scan-all
PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py --coverage --feature offload
PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py --save-samples tests/wings_accel/samples

# JSON 输出(适合 golden/diff)
PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py <yaml> --matrix --json > out.json

# 仅打印输入(loader 调试)
PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py <yaml> --print input
```

> **decoding 验证**:`--matrix` / `--scan` 直接驱动 `decoding_enabled`(逐 method 隔离;`requires_model_path` 的方案自动注入 stub 草稿路径)。legacy 组合态(`--kv` 等)沿用 `_flags_from_args`,不映射 `decoding_enabled`(默认 `False`);且 fixture 同时含 native cpu + mooncake + memcache(均 `name=cpu`)时组合态选首个 `AscendStoreConnector`(mooncake)——要逐个验证这三类内存后端,用 `--matrix`(`offload` 文件落盘重定向到临时卷,不污染 `/shared-volume`,并做 JSON/YAML/bash 语义校验)。要直接构造意图,用 `test_demo_all_on.py` 或 Python 里建 `LoadFlags`。

### 16.3 全开 demo 期望(`test_demo_all_on.py`)

| 模型 | decoding | kv_cache | sparse |
|---|---|---|---|
| DeepSeek-V4-Flash(v0.22.0) | mtp | — | performance_first |
| MiniMax-M2.7(v0.23.0) | — | — | — |
| Qwen3.5-397B-A17B(v0.23.0) | mtp | cpu | — |

**守卫**:全关(裸 `LoadFlags()`)三模型全空 no-op(argv / audit / install 段全无)。

---

## 17. 接手清单(给新维护者)

入口边界先记住:生产集成用 `resolve_smart_accel_from_config(...)` 或 `func_smart_accel(SmartAccelInput)`;`smart_accel_io.py` 只是快速构造输入、验证输出的辅助脚本,两者都要支持。

1. **跑测试**:`PYTHONPATH=src python3 -m pytest tests/wings_accel -q`(全绿即通过)。
2. **看一个真实端到端**:
   ```bash
   PYTHONPATH=src python3 tests/wings_accel/smart_accel_io.py tests/wings_accel/fixtures/smart_accel_all_features.yaml --matrix
   ```
3. **改 expander 时先看**:
   - `smart_decoding_expander`(decoders.py):仅消费声明方案——draft_arch 专用匹配 → 专用错配守卫 → 通用草稿;有草稿未命中/非本地目录 → 告警关闭,无草稿 → no_model 首序
   - `offload.py:82-105`(三选一 + fallback)+ `117-128`(QAT 门控 + files 计划)
   - `custom.py:35-64`(always-on 深合并)
4. **改占位符时**:**只改 `render._resolve_token` 一处**(单一判定点),勿在 expander 另写填充逻辑。带换算的公式就地写死 + 注释。同步更新本文 §6.2 总表。
5. **改 YAML 格式时**:同时改对应 expander(读)+ fixture(参照)+ 跑生产 YAML 验证不破坏。
6. **新增特性时**:`schemas.py` 加字段 → `validators.py` 加规则 → 新 expander 加路径 → `core` 接入 → `conflict.py` 评估冲突。同步更新本文。

---

## 18. 变更记录(相对 28W 走读的演进)

| 日期 | 摘要 |
|---|---|
| 2026-06-23 | 初版上线:`media`/`ladder` 双格式 KV 卸载 + status 码分类 + 10 文件 |
| 2026-07-04 (`docs/48`) | 收口:MaaS 单一驱动(删 `no_auto`)/ priority 按需 / QAT 三门门控 + 模板化 |
| 2026-07-10 (`docs/54`) | 通用 `files:` 配置文件渲染(lmcache 迁移,删专属代码);`LMCACHE_CONFIG_FILE` 移入 yaml `envs:`,仅 `LMCACHE_QAT_ENABLED` 代码注入 |
| 2026-07-10 (`docs/55`) | YAML 作者指南成文(字段 / 占位符 / async_scheduling 规则) |
| 2026-07-14 (`f6643d9`) | 当前状态:13 文件;KV 卸载简化为 cpu/disk/cpu_disk 三 scheme;status 码移除为 None/`_FeatureOutput`;新增 `api.py` / `custom.py` / `render.py` / `memory_estimator.py`;`conflict.py` 降为 no-op |
