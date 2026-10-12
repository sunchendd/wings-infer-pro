# YAML V2 profile 泛化/特化能力示例

本文通过 `config/v2/vllm-ascend/v0.99.0/_demo/` 下的演示资产，举例介绍 Wings YAML v2 的 profile 泛化/特化（偏序裁决）能力。这些 demo 资产使用 `v0.99.0` 版本和 `TestModel` / `HardwareDemo` / `AmbiguityDemo` / `IncomparableDemo` 等演示专用模型名，**不会与生产资产（v0.23.0）误匹配**。

> 说明：`_demo` 目录下的资产会被 v2 扫描器递归遍历，但目录仅作物理组织，不参与匹配。匹配完全由 `profile` 块承担。模型名均为演示专用，如需真实使用，请按 `config/v2/{engine}/{version}/{hardware}/{model}/{variant}.yaml` 约定组织并补充 `hardware_table.yaml` 登记。

## 背景：profile 与偏序裁决

v2 以 **profile**（yaml 内声明的扁平 key-value 字典）作为查找 key。匹配为声明式比较，无表达式求值。核心机制：

- **候选资格**（`evaluate_profile`）：逐 key 用 ctx 求值，所有 key 命中才进入候选集合。必填四要素（`engine`/`version`/`hardware`/`model`）必须全部命中；可选 key（`context_length`）未命中（含 ctx 缺值）→ 拒绝。
- **偏序裁决**（`resolve`）：从候选集合中选**最特化**者。A 比 B 更特化 ⟺ A 的匹配集合 ⊆ B 的匹配集合（且至少一个参与偏序的 key 为严格包含）。仅 `partial_order=True` 的 key（`hardware` 集合包含、`context_length` 区间包含）参与偏序。
- **歧义处理**：多个候选等价（重复资产）或互不偏序 → 告警 + 确定性选第一个（按资产路径排序），不再 fail-fast。

## 1. context_length 泛化/特化

`context_length` 是可选索引 key，支持区间算子（`>=`/`<=`/`>`/`<`/`==`/`in`）。泛化/特化由**区间包含**判定：`>=131072` 的匹配集合 ⊆ `>=0` 的匹配集合，故 `>=131072` 更特化。

### 1.1 泛化资产（`TestModel-generic.yaml`）

```yaml
profile:
  engine: vllm-ascend
  version: "v0.99.0"
  hardware: {Ascend910C_64G}
  model: TestModel
  context_length: { ">=": 0 }   # 覆盖所有上下文长度
```

使用通用启动参数（`max_num_batched_tokens: 1024`、`gpu_memory_utilization: 0.8`、`max_num_seqs: 32`）。

### 1.2 特化资产（`TestModel-longctx.yaml`）

```yaml
profile:
  engine: vllm-ascend
  version: "v0.99.0"
  hardware: {Ascend910C_64G}
  model: TestModel
  context_length: { ">=": 131072 }   # 只匹配长上下文
```

使用长上下文专用参数（`max_num_batched_tokens: 8192`、`gpu_memory_utilization: 0.9`、`max_num_seqs: 64`）。

### 1.3 兜底资产（`TestModel-fallback.yaml`）

```yaml
profile:
  engine: vllm-ascend
  version: "v0.99.0"
  hardware: {Ascend910C_64G}
  model: TestModel
  # 不写 context_length → 视为最泛化（全集）
```

**不写 `context_length` 视为最泛化（全集）**：任何写了 `context_length` 的资产都比它更特化。当 ctx 未下发 `context_length` 时，只有不写的资产命中（写了 `context_length` 的资产因 ctx 缺值不命中），作为兜底。

### 1.4 匹配结果

| 下发 context_length | 命中资产 | 说明 |
| --- | --- | --- |
| 未传 | `TestModel-fallback.yaml` | 只有不写 context_length 的兜底命中 |
| 4096 | `TestModel-generic.yaml` | 泛化（`>=0`）胜出，特化（`>=131072`）不命中 |
| 131072 | `TestModel-longctx.yaml` | 特化（`>=` 含等号） |
| 200000 | `TestModel-longctx.yaml` | 特化（`>=131072`）胜出 |

偏序链：**不写（最泛化） < `>=0` < `>=131072`（最特化）**。

## 2. hardware 集合偏序

`hardware` 是必填 key，值类型为 `set[str]`。泛化/特化由**集合包含**判定：`{Ascend910C_64G}` ⊆ `{Ascend910C_64G, Ascend910B_64G}`，故单硬件资产更特化。

### 2.1 多硬件泛化资产（`HardwareDemo-generic.yaml`）

```yaml
profile:
  engine: vllm-ascend
  version: "v0.99.0"
  hardware: {Ascend910C_64G, Ascend910B_64G}   # 大集合，匹配两种硬件
  model: HardwareDemo
```

### 2.2 单硬件特化资产（`HardwareDemo-a3.yaml`）

```yaml
profile:
  engine: vllm-ascend
  version: "v0.99.0"
  hardware: {Ascend910C_64G}   # 小集合，只匹配 Ascend910C_64G
  model: HardwareDemo
```

### 2.3 匹配结果

| 下发 hardware | 命中资产 | 说明 |
| --- | --- | --- |
| `Ascend910C_64G` | `HardwareDemo-a3.yaml` | 单硬件特化胜出（`{A3}` ⊆ `{A3, B}`） |
| `Ascend910B_64G` | `HardwareDemo-generic.yaml` | 只有多硬件泛化命中 |

## 3. 歧义处理

当多个候选**等价**（重复资产）或**互不偏序**时，偏序引擎无法选出唯一最特化者 → `resolve` 抛出 `ProfileAmbiguityError` → `locate_v2` 捕获后告警 + 确定性选第一个（按资产路径排序，可复现）。歧义需资产作者**人工比对** profile 是否等价/互不偏序并解决（离线校验脚本只做单资产合法性检查，不检测跨资产歧义）。

### 3.1 等价重复资产（`AmbiguityDemo.yaml` + `AmbiguityDemo-dup.yaml`）

两个资产 profile 完全相同（`context_length: {">=": 0}`），匹配集合相同 → 等价 → 歧义。

```yaml
# AmbiguityDemo.yaml 与 AmbiguityDemo-dup.yaml 的 profile 完全相同
profile:
  engine: vllm-ascend
  version: "v0.99.0"
  hardware: {Ascend910C_64G}
  model: AmbiguityDemo
  context_length: { ">=": 0 }
```

匹配时告警并选第一个（按路径排序，`-dup` 在前）：

```
WARNING v2 asset ambiguity; picking the first matched asset: ambiguous profile resolution:
2 candidates are equally specific (duplicate assets or incomparable profiles)
```

（上面为节选；实际告警末尾还包含候选 profile key 列表，如 `: [['context_length', ...], [...]]`。）

### 3.2 互不偏序（`IncomparableDemo-a.yaml` + `IncomparableDemo-b.yaml`）

`>=100` 与 `<=200` 谁都不比对方更特化（互不严格包含）→ 互不偏序 → 歧义。

```yaml
# IncomparableDemo-a.yaml
context_length: { ">=": 100 }

# IncomparableDemo-b.yaml
context_length: { "<=": 200 }
```

匹配时告警并选第一个（按路径排序，`-a` 在前）。

## 4. 生产隔离

所有 demo 资产使用 `v0.99.0` 版本，与生产资产（`v0.23.0`）隔离。验证：

| 模型 | v0.23.0 下是否匹配 |
| --- | --- |
| `DeepSeek-V4-Flash-w8a8-mtp`（生产） | ✅ 正常匹配 |
| `TestModel` / `HardwareDemo` / `AmbiguityDemo` / `IncomparableDemo`（demo） | ❌ 不匹配 |

## 5. 用 dry-run 验证

可用 dry-run 验证 demo 资产的匹配与参数合并。以 `TestModel` 为例。demo 资产版本为 `v0.99.0`（仅存在于 `config/v2/`，`config/engines/` 下没有 `v0.99.0` 目录），需显式 `ENGINE_VERSION=v0.99.0`：此时 v2 匹配用**请求版本** `v0.99.0` 命中 demo 资产，而 v1 目录解析因 engines 下无该版本而回退 latest（如 `v0.26.0rc1`），两者解析版本不一致。若不设置 `ENGINE_VERSION`，ctx 版本回退为 latest，demo 资产不会命中：

```bash
# 短上下文 → 命中泛化资产（TestModel-generic.yaml）
ENGINE_VERSION=v0.99.0 python -m wings_ctl --model-name TestModel \
  --hardware-info hardware_info.json --config-root <config_root> \
  --engine vllm-ascend --dry-run --input-length 4096 --output-length 0

# 长上下文 → 命中特化资产（TestModel-longctx.yaml）
ENGINE_VERSION=v0.99.0 python -m wings_ctl --model-name TestModel \
  --hardware-info hardware_info.json --config-root <config_root> \
  --engine vllm-ascend --dry-run --input-length 200000 --output-length 0
```

dry-run 只做启动前推演，不写文件、不启动 engine。它验证配置能否解析，并打印本次将使用的环境变量和 engine 命令。dry-run 成功只说明输入能通过当前解析和渲染路径，不能证明目标镜像、硬件、网络或性能已验收（见 [支持边界](support-boundaries.md) 的 dry-run 边界）。

## 6. 相关文档

- [支持边界](support-boundaries.md)：已支持能力、限制和验证边界。
- 设计文档（`docs/design/wings-yaml-v2.md`）：v2 资产体系设计（profile key 注册表与偏序引擎）。
- [解析流程可视化](yaml-v2-resolution-flow.html)：从 CLI 下发到偏序裁决的分步图解。