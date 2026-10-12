# Wings YAML v2 — 设计

> 状态：已实现（v2 能力就绪 + 双轨路由接入主流程；存量迁移进行中）
> 范围：v2 资产体系（单文件合一 + profile 索引 + 偏序裁决 + 双轨路由）的权威设计。
> 实现细节以源码、测试和实际产物为准；正式文档入口见 `wings_control/docs/README.md`。
> 合法硬件与别名清单以 `config/v2/hardware_table.yaml` 为准；硬件匹配与归一化见 §5.5。

## 1. 背景与目标

现有 yaml 系统存在三个问题，v2 重构分步解决：

1. **基线拉起配置与加速配置分离**：基线在 `config/engines/`，加速在 `src/wings_accel/smart-accel/`；两套目录、两套加载器、两套匹配规则，同一模型需在两处重复维护，engine/version/hardware 三键易不一致。
2. **vllm 不支持多引擎版本**：vllm 无版本层，无法区分不同 vllm 引擎版本的参数差异（vllm-ascend 已支持版本层）。
3. **索引 key 单一**：仅 engine+version+hardware+model 四要素索引，无法表达更丰富的查找条件。

**目标**：升级为 v2 资产体系——单文件合一、vllm 多版本目录、以 profile 为索引 key。

## 2. 核心概念

### 2.1 v1 与 v2

- **v1**：现有资产（`config/engines/` 基线 + `smart-accel/` 加速），索引基于目录结构 + 模型名正则匹配。
- **v2**：单文件合一 + 版本目录 + profile 索引。

### 2.2 profile

- v2 yaml 内声明的**扁平 key-value 字典**，作为查找 key。
- 可含超出 engine/version/hardware/model 四要素的其他 key，甚至声明式判断条件。
- 匹配为**声明式比较**（`>=`、`<=`、`in`、精确等），**无表达式求值、无 eval/exec**（符合 AGENTS.md 红线）。
- 新增 key 需**通过代码显式注册**，不提供无限制条件能力。

### 2.3 目录的作用

目录**仅作物理组织**，不参与匹配。匹配完全由 profile 承担，扫描器递归遍历 v2 资产树。组织形式约定为 `v2/{engine}/{version}/{hardware}/{model}/{variant}.yaml`，但仅为约定。

## 3. 资产格式（v2 单文件合一）

**V2 YAML = V1 基线 YAML + V1 加速 YAML 完整合并，格式不变，顶部新增 `profile` 块用于索引。** `profile` 是唯一新增的顶层块，其余块原样搬入。

```yaml
schema: v2
profile:                       # 唯一新增：索引 key（扁平 key-value，声明式条件）
  engine: vllm-ascend
  version: "v0.23.0"
  hardware: {Ascend910C_64G}   # raw string 集合（YAML 流映射，无原生 set）
  model: DeepSeek-V4-Flash-w8a8-mtp
  # context_length: { ">=": 131072 }   # 可选 key（首版仅此一个）

# ── 以下为 V1 基线 YAML 原样搬入 ──
upstream_sources: ...
model:
  name: DeepSeek-V4-Flash
  variant_name: DeepSeek-V4-Flash-w8a8-mtp
  match: [...]
hardware_profile: ...          # 原样（仅作 accel 输入，不参与匹配）
features: ...
scenarios:                     # standalone / pd_disaggregation / multi_node 分场景
  standalone:
    strategies:
      single_node:
        engine_config: ...
        env: ...

# ── 以下为 V1 加速 YAML 的 smart_accel 块原样搬入 ──
smart_accel:
  standalone:
    strategies:
      single_node:
        decoding: ...
```

要点：

- `engine_config`（即 `scenarios.{topology}.strategies.{name}.engine_config`）沿用 V1 基线结构，现有 `_select_scenario` / `normalize_nodes` / `_resolve_multi_node` 策略层可直接复用。
- `smart_accel` 块沿用 V1 加速 YAML 结构，`func_smart_accel` 消费逻辑可直接复用。
- `profile.hardware` / `profile.model` 用**下发原值**；V1 的 `hardware_profile` 不参与匹配。

## 4. 目录布局

```
config_root/
  engines/            # v1 存量，原地不动（零迁移、零风险）
  v2/                 # v2 独立顶层目录，强制三层 {engine}/{version}/{hardware}
    vllm-ascend/
      v0.23.0/
        ascend-a3/
          DeepSeek-V4-Flash/
            DeepSeek-V4-Flash-w8a8-mtp.yaml
    hardware_table.yaml   # 合法硬件表（保留名，扫描时跳过，见 §5.3）
```

- v2 目录重新设计，不沿用 v1 的 `engines/`、`models/` 冗余层。
- v2 下**强制带版本层**（`{engine}/{version}/{hardware}`），目录形态即 v1/v2 天然分界。
- 目录仅作物理组织，不参与匹配。

## 5. profile key 注册表

### 5.1 key 清单

**必填四要素**（缺任一 → 资产无效/跳过）：

| key | 类型 | 比较语义 |
| --- | --- | --- |
| `engine` | str | 精确（`_`→`-` 归一 + casefold） |
| `version` | str | 前缀匹配（对齐 v1 目录层，MaaS 版本常带构建元数据） |
| `hardware` | set[str] | 集合包含（raw string 集合，casefold） |
| `model` | str | 精确（`_`→`-` 归一 + casefold；上层保证下发完整 variant 名） |

**注册制可选 key**（走注册，未命中即拒绝）：

| key | 类型 | 比较语义 |
| --- | --- | --- |
| `context_length` | int | 不等式（`>=`/`<=`/`>`/`<`/`==`/`in`） |

所有 key（必填与可选）都是**未命中即拒绝**：任一 key 未命中 → 该 yaml 不成为候选。

### 5.2 硬件 raw string 集合

`hardware` 值类型为 `set[str]`，声明该资产支持的所有 raw string（casefold 存储/比较）。与 v1 的归一化链（精确→别名→剥后缀）不同，v2 **不做后缀剥离**；匹配前仅按 `config/v2/hardware_table.yaml` 的 `aliases` 块对 ctx hardware 做一次别名归一化，随后与 `profile.hardware` 做 raw string 集合成员匹配（`_`→`-` + casefold）。泛化/特化由集合包含判定：`hardware_A` 比 `hardware_B` 更特化 ⟺ `A ⊆ B`（如 `{h20_141G}` ⊆ `{h20_96G, h20_141G}`）。YAML 流映射 `{b200, B200}` 解析为 dict，`_norm_set` 取键为成员。下发值形态与硬件匹配见 §5.5。

### 5.3 合法硬件表

合法硬件表单独文件维护（`config/v2/hardware_table.yaml`，含 `hardware` 清单与 `aliases` 别名块）。离线校验脚本检查 yaml 的 `hardware` 集合是否在合法表内（不在表内 → warning，不阻断）。`scan_v2_assets` 按保留文件名跳过该表（`v2_loader.HARDWARE_TABLE_NAME`），不当作模型资产。

### 5.4 声明式比较

profile 值可为标量（精确）或带算子的字典（`>=`/`<=`/`>`/`<`/`in`/`==`）。算子为**封闭集合**，注册表内硬编码，不解析任意表达式；`!=` 不提供。

### 5.5 硬件匹配与归一化

**v1 目录定位**（`locator.resolve_family_dir`，分支顺序即优先级）：精确命中 →（x86_64 平台且存在 `ascend910b-x86_64/` 时对 `ascend910b` 特判）→ 别名 `_ALIAS`（芯片名→架构代目录）→ 去 `_<N>G` 后缀 → `_generic` 保底（`allow_generic` 且引擎级 `_generic/models/default_model.yaml` 存在）。config 硬件目录清单以 `config/engines/{engine}/.../` 实际目录为准。

**v2 `profile.hardware` 匹配**：不做后缀剥离；匹配前仅按 `config/v2/hardware_table.yaml` 的 `aliases` 块对 ctx hardware 做一次别名归一化，随后与 `profile.hardware` 做 raw string 集合成员匹配（`_`→`-` + casefold）。合法硬件与别名清单以 `config/v2/hardware_table.yaml` 为准（增量维护；未登记不报错 → 走 V1 回退）。

## 6. 匹配与冲突裁决（偏序引擎）

### 6.1 匹配流程

```
locate(engine, version, hardware, model, profile_ctx):
    # 1. 递归遍历 v2 资产树（目录仅物理组织，不参与匹配）
    # 2. 对每个 yaml：逐 key 用 profile_ctx 求值
    #    - 必填 key 全部命中（缺失 → 静默跳过）
    #    - 可选 key 未命中（含 ctx 缺值）→ 拒绝该 yaml
    # 3. 候选集合按 §6.2 裁决取最优
    # 4. v2 命中且 v1 命中 → v2 优先 + 告警；v2 未命中 → 整体回退 v1（过渡期）
```

### 6.2 偏序裁决（对齐 C++ 模板偏序）

只有所有 key 全部命中的 yaml 才进入候选集合。候选 A 比 B 更特化 ⟺ **A 的匹配集合 ⊆ B 的匹配集合**。profile 是多 key 合取（AND），故逐 key 组合偏序：

```
profile_A ⊆ profile_B  ⟺  对每个参与偏序的 key k：A.k ⊆ B.k，且至少一个严格包含
```

**参与偏序的 key**：仅 `partial_order=True` 的 key（首版 `hardware` 集合包含、`context_length` 区间包含）。

- `version` 不参与：合法版本集合难定义，前缀匹配的"虚假特化"会误报歧义。
- `engine`/`model` 不参与：精确匹配，is_subset 退化为 A==B。

```
resolve(candidates, ctx):
    # 1. 过滤：match 全命中
    # 2. 两两 is_subset（仅 partial_order=True 的 key）
    #    A ⊆ B 且 B ⊄ A → A 更特化，淘汰 B
    #    A ⊆ B 且 B ⊆ A → 等价
    #    A ⊄ B 且 B ⊄ A → 互不偏序
    # 3. 唯一最特化 → 选中；否则（等价 / 互不偏序）→ raise ProfileAmbiguityError
```

**无需全局优先级表**：特化程度由匹配集合包含关系（结构性）决定，可预测、可维护。`resolve` 只做裁决，遇到歧义 **raise `ProfileAmbiguityError`**（fail-fast）；由上层 `locate_v2` 捕获该异常后打 warning + 按资产路径排序确定性选第一个，避免运行时因数据歧义阻断启动。歧义应在离线校验阶段由资产作者解决。

## 7. 注册表代码形态

```python
@dataclass(frozen=True)
class ProfileKey:
    name: str
    required: bool = False          # 必填：yaml 必须声明，缺失 → 资产无效/跳过
    partial_order: bool = False     # 是否参与偏序判断
    value_type: type = str          # str / int / set
    match: Callable[[Any, Any], bool] = None        # (declared, ctx) -> bool 单请求命中
    is_subset: Callable[[Any, Any], bool] = None    # (declared_a, declared_b) -> bool 匹配集合包含

PROFILE_KEYS: Dict[str, ProfileKey] = {
    "engine":         ProfileKey("engine", required=True, value_type=str, match=_eq_str),
    "model":          ProfileKey("model",  required=True, value_type=str, match=_eq_str),
    "version":        ProfileKey("version", required=True, value_type=str, match=_prefix_cmp),
    "hardware":       ProfileKey("hardware", required=True, partial_order=True, value_type=set, match=_set_mem, is_subset=_set_subset),
    "context_length": ProfileKey("context_length", required=False, partial_order=True, value_type=int, match=_num_cmp, is_subset=_range_subset),
}
```

各 key 类型操作语义（仅 `partial_order=True` 的 key 需要 `is_subset`）：

| key 类型 | `match` | `is_subset` |
| --- | --- | --- |
| 精确 str（engine/model） | casefold 相等 | — |
| 前缀（version） | 前缀匹配 | — |
| 集合 set[str]（hardware） | ctx raw ∈ 集合（casefold） | 集合包含（A ⊆ B） |
| 范围 int（context_length） | 数值比较 | 区间包含（`>=141` ⊆ `>=80`） |
| 精确 int（`==`） | 数值相等 | A==B |
| 列表（`in`） | 值∈列表 | 元素子集 |

实现见 `wings_ctl/loaders/profile_registry.py`。

**新增 key 流程**：在 `PROFILE_KEYS` 加一行（指定 value_type/required/partial_order，实现 `match`；若 `partial_order=True` 再实现 `is_subset`）→ 若需新比较语义，新增 `_xxx_cmp`/`_xxx_subset` 纯函数 → 在 profile_ctx 构造处补充取值来源 → 补测试。

## 8. 离线校验

**匹配期间不允许报错**（资产合法性错误不中断运行时匹配）。资产合法性由离线校验脚本 `wings_ctl/loaders/profile_validator.py` + `scripts/validate_v2_assets.py` 在开发阶段检查，匹配期内的跳过一律静默（不报错、不记录）。

**检查项**：必填四要素缺失、未注册 key（报可定位错误，提示注册；运行时宽容）、必填 key 值非法、可选 key 多值/多算子叠加、`hardware` 值 ∉ 合法硬件表（warning）。

**运行时保留的报错**：0 候选（回退 v1；PD/SGLang 严格场景才 fail-fast，属遗留项）。偏序歧义：`resolve` 抛 `ProfileAmbiguityError`，由 `locate_v2` 捕获后告警 + 按路径排序确定性选第一个（不在运行时 fail-fast）。

**接入**：纳入 `scripts/check.sh`，人 / CI / pre-commit 共用。

## 9. 双轨路由与加载/合并

- **双轨路由**：在 `core/config_resolver.py::resolve_config` 中，先尝试 v2 定位。v2 命中 → 用 v2 资产；v2 未命中 → 整体回退 v1（过渡期）；v2 与 v1 同时命中 → v2 优先 + 告警。
- **加载与合并**：`engine_config`（scenarios 块）走现有 trace-first 合并 → `audit.json`；`smart_accel` 块仅在 MaaS 加速开关开启时解析，关闭时整块忽略（no-op）。
- **加速块复用**：`smart_accel` 块解析复用 `wings_accel` 的 `func_smart_accel`，输入改为从合一文件构造 `SmartAccelInput`（`apply_smart_accel_v2`），不再走 `find_smart_accel_yaml_path` 独立扫描。`smart_accel` 语义仍受 `wings-accel-interface.md` 约束。

## 10. 过渡节奏与责任边界

**过渡节奏**：① 能力就绪（v1 行为不变 + v2 解析就绪）→ ② 增量灰度（新模型/硬件用 v2，v1 存量不动）→ ③ 存量迁移（按模型/硬件逐步迁移，每批独立验证）→ ④ 收尾（v1 清零后移除 v1 加载器与旧目录）。

**责任边界**：加速与基线拉起责任方统一（合一文件由同一团队维护）。`smart_accel` 块语义仍受 `wings-accel-interface.md` 约束。

## 11. 已确认决策汇总

| # | 决策 |
|---|---|
| A1 | 单文件合一（V1 基线 + V1 加速完整合并，格式不变，加 `profile`） |
| A2 | 加速仍需 MaaS 门控 |
| A3 | 双轨过渡，粒度到模型/资产层 |
| A4 | 加速与基线责任方统一 |
| profile | profile 为扁平 key-value；声明式条件，无 eval/exec，新 key 走代码注册 |
| 目录 | 仅作物理组织，不参与匹配；v2 目录重新设计，保留三层 `{engine}/{version}/{hardware}` + 模型子目录 |
| 裁决 | 偏序引擎（最特化优先），无优先级表；互不偏序/等价 → 告警 + 确定性选第一个（不再 fail-fast） |
| 隔离 | v1/v2 完全隔离目录 |
| 路由 | v2 优先 + 告警，v2 未命中整体回退 v1 |
| 可选 key | 首版仅 `context_length`；`!=` 算子和 dtype/gpu_count/topology/pd_role 后续增量 |
| 合法硬件表 | 放 `config/v2/hardware_table.yaml`（保留名，扫描跳过）；增量维护，未登记 → warning 不报错 → 走 V1 回退 |
| config_root | 维持同根不同子目录（`config_root/v2/`），不新增独立加速根 |

## 12. 当前实现状态

| 模块 | 说明 |
|---|---|
| `loaders/profile_registry.py` | `ProfileKey` 注册表 + 声明式比较 + 偏序裁决引擎 |
| `loaders/profile_validator.py` | 资产合法性离线校验 |
| `loaders/v2_loader.py` | v2 资产扫描 + 合一文件解析 + profile 匹配（`locate_v2`） |
| `accel/smart_accel_v2.py` | 加速块复用 `func_smart_accel` |
| `accel/smart_accel.py` | 提取 `build_load_flags`（v1/v2 共用） |
| `core/config_resolver.py` | 双轨路由接入（v2 优先 + 告警 + 回退 v1） |
| `config/v2/hardware_table.yaml` | 合法硬件表（最小集） |
| `config/v2/.../DeepSeek-V4-Flash-w8a8-mtp.yaml` | 首批迁移的 v2 合一资产 |
| `scripts/validate_v2_assets.py` / `scripts/check.sh` | 离线校验接入 |

单测：`tests/unit/test_profile_registry.py` / `test_profile_validator.py` / `test_v2_loader.py`；集成：`tests/integration/test_v2_dual_track.py`（仅 Linux）。能力示例见 `wings_control/docs/capabilities/yaml-v2-profile-demo.md`。

## 13. 遗留问题与未验证项

- **v2 收尾阶段 fallback 机制**（开放）：v1 全量迁移后需为 v2 补 fallback（版本→latest、硬件→`_generic`、模型→`default_model`，对齐 v1 语义）；严格场景 fail-fast。过渡期由 v1 fallback 天然兜底，不阻塞。
- **vllm 版本目录未命中策略**（开放）：回退 latest 还是严格 fail-fast，或按场景区分（普通回退 latest、PD/严格 fail-fast），倾向后者。v1 清零后实现。
- **`ascend-a2` / `ascend-a3` 是否真实 MaaS 下发原值**（开放）：需与 MaaS 确认实际下发形态，决定 v2 资产 `profile.hardware` 声明目录名还是芯片名。
- **`smart_accel_v2` 与 `test_v2_dual_track`**：依赖完整流水线（fcntl），仅 Linux 可运行验证。
- **`wings_accel.yaml_loader` 文件编码**：`load_smart_accel_from_yaml` 默认编码读文件，Windows 默认 GBK 因中文注释报错；生产 Linux（UTF-8）无此问题；如需 Windows 开发可显式 `encoding="utf-8"`（属 wings_accel 责任方范围）。
