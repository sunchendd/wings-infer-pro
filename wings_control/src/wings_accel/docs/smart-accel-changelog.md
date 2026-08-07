# smart-accel 变更记录 — `764a54c` → HEAD(11 提交)

> 归类:🟩 稳态核心 / 参考文档。本文整理 `764a54c` 到当前 HEAD(共 **11 个提交**)的全部改动,方便快速回溯「smart-accel 这一轮做了什么、动过哪些代码/资产/文档」。
> 规模:2268 文件、+61724 / -8265。其中绝大部分是模型 YAML 资产批量补全;**真正的代码逻辑改动集中在 6 个 Python 文件**。
> 真件口径:commit hash / file:line 均回真实 git 历史核对,代码与本文冲突时以代码为准。

---

## 总览

| 维度 | 内容 |
|---|---|
| 提交数 | 11(`764a54c` → HEAD) |
| 代码文件 | 6 个:`smart_accel.py` / `decoders.py` / `yaml_loader.py` / `offload.py` / `schemas.py` / `core.py` |
| 文档 | `smart-yaml.md`(+570)、`lmcache-yaml.md`(+94) |
| 资产 | 约 2000+ 文件(批量补全 + scenario 迁移) |
| 测试 | 全套 **694 passed / 1 skipped** |
| 主线 | smart-accel 结构升级:scenario 拆块对齐 wings_control + decoding 走草稿 architectures 智能匹配 + backend 判定改为纯形态驱动 + 2 个真实环境 bug 修复 |

---

## 一、核心代码改动(6 文件,按主题)

### 1. smart_accel 按 scenario 重构(最大改动 · `6a9bbc7`)

`smart_accel` 从**扁平结构**改为 **scenario 嵌套结构**,对齐 `wings_control` 的 scenarios 格式:

```yaml
smart_accel:
  standalone:
    source_ref: "..."
    match: { distributed: false, pd_role: null }
    strategies:
      single_node: { default_strategy: true, decoding / sparse / kv_offload ... }
  multi_node:
    strategies:
      multi_node_dp: { ... }
  pd_disaggregation:
    source_ref: "..."
    match: { distributed: true, pd_role: null }
    strategies:
      pd_cluster:
        default_strategy: true
        nodes:
          - role: prefill        # P 节点:仅 sparse
            sparse: [...]
          - role: decode         # D 节点:decoding + sparse
            decoding: [...]
            sparse: [...]
```

- **PD 规则**(用户明确,缺键即不产出):
  - P 节点(prefill):仅 sparse(不支持投机推理 / 不支持卸载)
  - D 节点(decode):decoding + sparse(支持投机推理 / 不支持卸载)
  - standalone / multi_node:三特性全支持
- **路由下沉到 loader**:`yaml_loader._route_smart_accel_block` 按 topology 路由出扁平子块,塞进 `SmartAccelInput.smart_accel`;**expander 不再感知 scenario / topology / role**。
- 新增 `_select_default_strategy` / `_extract_strategy_features`(对齐 wings_control `_select_scenario` 语义:取 `default_strategy: true` 首个,无则取首个)。
- `core.py` 移除 `pd_role` 透传;`decoders.py` / `offload.py` 移除 topology 过滤。
- `match` 字段**仅作者自检**(loader 不消费,同 wings_control 自身也不读 match)。

### 2. topology 推导(`069ac8a`)

`smart_accel.py` 新增 3 个归一 / 推导函数:

- `_normalize_pd_role` — `P/D` → `prefill/decode`(修了 env 下发 `P` 但代码查 `prefill` 的不匹配 bug);其它(含空 / 非法)→ `None`(非 PD 分离)。
- `_resolve_topology` — `PD_ROLE + DISTRIBUTED + NODE_IPS` → `standalone / multi_node / pd_prefill / pd_decode`(对齐 wings-control `Topology` 枚举)。优先级:PD_ROLE > distributed > standalone。
- `DeploymentMode` 加 `topology` 字段;`LoadFlags` 透传 `topology`;`collect_accel_switches` 返回 `topology`。

### 3. decoding draft_arch 匹配 + 无草稿兜底(`2cf6f56`)

`decoders.py` 增强投机解码方案选择,支持同一 yaml 声明多种草稿方案 + 至多一种无草稿方案:

- 新增 `_read_draft_architectures` — 读草稿模型 `config.json` 的 `architectures`(小写归一;非本地 / 无文件 / 解析失败 → `[]`)。
- 新增 `_match_draft_method` — 按 scheme 声明的 `draft_arch`(list,小写关键字)做**子串匹配**,任一关键字命中任一 architecture 即选定。
- 选择流程:
  1. 有草稿路径 → 读 architectures → 按 `draft_arch` 匹配 eagle3 / dflash / dspark / draft
  2. 未匹配 `draft_arch` → 降级通用 draft(未声明 `draft_arch` 的 model_based)
  3. 无通用 draft → 降级 no_model(mtp / suffix)
  4. 无草稿路径 → no_model 分支(至多一个,取首序)
  5. 都没有 → `None`(不开投机)
- 向后兼容:现有 yaml(单 eagle3 无 `draft_arch`)→ 走通用 draft 路径,行为不变。

### 4. dspark 双形态(`e0bf6cb`)

dspark 有两种形态,decoders 逻辑天然支持共存(无需改代码):

- **有草稿**:Kimi K3 等单独发草稿模型(`requires_model_path: true` + `draft_arch`)。
- **无草稿**:DeepSeek V4 Pro / Flash 0731 等,dspark 权重内嵌主模型 checkpoint,不需要草稿路径(`requires_model_path` 不设 → 进 no_model 分支)。
- DeepSeek-V4-Pro 7 个硬件的 dspark 资产:移除 `requires_model_path: true` 与 `model: $path`,改进 no_model 分支(此前错误带 `model:$path` → vllm 找不到草稿路径致启动失败)。

### 5. 移除 priority 排序(`ebb9ec0`)

设计简化:有草稿投机靠 `draft_arch` 自动识别,无草稿投机至多一个,不需要 priority 排序。

- `decoders.py` 删 `_pick_priority`,no_model 分支改取首序;多声明时 warning「no_model 应至多一个」。
- 9 个 yaml 资产移除 decoding 方案的 `priority` 字段(DeepSeek-V4-Pro dspark ×7 + DeepSeek-V4-Flash mtp ×2)。
- **sparse 的 priority 保留**(sparse 按 mode 名匹配,不读 priority,无影响)。

### 6. envsubst sed 兜底(`db95d44`)

真实环境反馈:`mmc_local.conf` / `mmc_meta.conf` 里 `${MASTER_IP}` / `${RANK_IP}` 占位符未展开,且 `.tmp` 文件为空 —— 根因是**容器缺 gettext(envsubst 不存在)**,envsubst 重定向产生空 `.tmp`,`mv` 后 conf 被清空,占位符残留。

`offload._synthesize_file_pre_serve` 的 envsubst 命令改为 if/else:

- 优先 `envsubst`(`command -v` 检测 + 正常执行)
- envsubst 不存在或失败 → **sed 兜底**(`s/${VAR}/$VAR/g`,双引号让 shell 展开已 export 的变量值),无外部依赖
- 结果都写 `.tmp` 再 `mv`,避免空文件覆盖

### 7. SPECULATIVE_DECODE_MODEL_PATH 归一(`2060b5f`)

问题:MaaS 下发 `SPECULATIVE_DECODE_MODEL_PATH="none"` / `"null"`(大小写不敏感)时,原样透传给 eagle3 等 `requires_model_path` 方案,产出 `--speculative-config '{"method":"eagle3","model":"none",...}'`,导致 vllm serve 启动失败(找不到名为 none 的草稿模型)。

修复:`smart_accel._normalize_optional_path` —— 空 / `none` / `null`(大小写不敏感)统一归为 `""`。单一真相源,下游 `_eligible` 的 `not cfg.model_path` 判定即可正确识别。

### 8. backend 判定改为 daemon 形态驱动(`c639653`)

`offload.py` 彻底取消 connector 白名单:

| | 旧 | 新 |
|---|---|---|
| 信号 | `kv_connector ∈ {AscendStoreConnector, LMCacheAscendConnectorV1Dynamic, ...}` | scheme 的 `files` 含 `start_kv_serve.sh` |
| 含义 | 按 connector 名字白名单 | **「要不要起独立服务」纯形态判定** |

- 新增 `_scheme_has_daemon`;删 `_NATIVE_CONNECTORS` / `_is_native_offload_scheme`;`_find_backend_scheme` 改 daemon 判定。
- `_has_backend_scheme`(yaml_loader)同步改。
- **加新 backend connector 无需改代码**:yaml files 写 daemon 脚本即识别为 backend;纯内嵌新 connector 不写 daemon 自动走三选一。
- 修正 DeepSeek-V4-Flash 的 `name: lmcache → name: cpu`(历史遗留命名错误,它是 cpu 介质内嵌 connector 不起服务)。改名后「有 daemon ⟺ backend」对所有现存形态自洽(0 孤儿)。

### 9. LMCacheMPConnector 支持(`c639653`)

vllm lmcache MP 分离部署(方法四):独立 lmcache server + vllm 连过去,形态同 mooncake / memcache。

- 字段归属:`connector / lmcache.mp.{port, mq_timeout}` 放 `cli_params`(进 `--kv-transfer-config`);server flag(`--l1-size-gb` 等)放 `files.start_kv_serve.sh` 的 `content`(不进 cli_params / envs)。
- daemon 脚本用占位符(MaaS KV 容量驱动):`--l1-size-gb {memory_capacity_gb}`、`--l1-init-size-gb {= memory_capacity_gb // 5}`(派生算术占位符)。
- 测试 lmcache 命中建议关 prefix caching(`no_enable_prefix_caching: true`)。

---

## 二、模型资产(约 2000+ 文件,批量)

| commit | 内容 |
|---|---|
| `069ac8a` | vllm-ascend v0.21.0rc 补 60 资产(5 decoding + 55 占位);vllm v0.23.0 补 **1273 个** `smart_accel: {}` 占位;923 个现有 scheme 加 `deploy_modes` |
| `6a9bbc7` | **925 个生产资产**批量迁移:扁平 → scenario 嵌套(wings_control 风格) |
| `e0bf6cb` | DeepSeek-V4-Pro 7 硬件 dspark 改无草稿形态 |
| `09be7be` | 补齐 3 个遗漏 decoding 资产(Qwen3.5 系列 bf16 variant) |
| `7bb48d0` | 全量模板 fixture `smart_accel_all_features.yaml` 补 `draft_arch` / 移除 no_model priority / 全 scheme 加 `deploy_modes` |

> `variant_name` 严格取自 config 的 `model.variant_name`(精确匹配),消除多 variant 裸名 Ambiguous + 同族 `name_pattern` 误匹配风险。

---

## 三、文档

- **`smart-yaml.md`**(+570):§0 / §1.1 / §2 / §3.0 / §4.1 / §4.2 / §7 / §8 / §10 全改新结构示例 —— scenario 结构、`draft_arch` 匹配示例(4 方案: eagle3 + dflash + 通用 draft + mtp 兜底)、`deploy_modes`、LMCacheMPConnector 章节、daemon 判定说明、占位符说明。
- **`lmcache-yaml.md`**(+94):§1 方法四列 + §4.4 完整示例 + §5.3 / §5.4 归一注意。

---

## 四、测试(全套 694 passed / 1 skipped)

新增大量用例:

- `draft_arch` 匹配(eagle3 / dflash)、unknown 降级 draft、无 config.json 降级、无草稿兜底(6 例)
- dspark 双形态:无草稿 dspark + 有草稿 dspark + 双形态共存(3 例)
- 3 个 scenario 端到端(DeepSeek-V4-Flash 4 拓扑全过:standalone / multi_node 全特性;pd_prefill 仅 sparse;pd_decode 有 decoding + sparse 无 kv_offload)
- SPECULATIVE path 归一(10 组参数化)
- envsubst sed 兜底断言(`test_kv_store_backend.py`)
- 10 种形态 backend 测试矩阵(原生 ×2 / 现存 backend ×4 / 未来新增 connector ×2 / disk, cpu_disk ×2)

---

## 五、提交清单(按时间顺序)

| commit | type | 摘要 |
|---|---|---|
| `069ac8a` | feat | 补全缺失模型资产 + deploy_modes 部署拓扑能力声明 |
| `2060b5f` | fix | SPECULATIVE_DECODE_MODEL_PATH=none 归一为空,防止 model:"none" 致 vllm 启动失败 |
| `db95d44` | fix | envsubst 占位符未展开时加 sed 兜底,防止 conf 空文件 |
| `2cf6f56` | feat | decoding 多草稿方案 draft_arch 匹配 + 无草稿兜底 |
| `e0bf6cb` | fix | dspark 支持无草稿形态(V4 主模型自带权重)+ 双形态共存 |
| `ebb9ec0` | refactor | 移除 decoding priority 字段(无草稿投机至多一个,无需排序) |
| `09be7be` | fix | 补齐 3 个遗漏的 decoding 资产(系统检查发现) |
| `bced8ce` | test | 移除 test_core.py decoding 方案的 priority 字段 |
| `7bb48d0` | docs | 全量模板 fixture + 文档补 draft_arch / deploy_modes 示例 |
| `6a9bbc7` | refactor | smart_accel 按 scenario 拆块,对齐 wings_control scenarios 结构 |
| `c639653` | feat | 支持 LMCacheMPConnector + backend 判定改为 daemon 形态驱动 |

---

## 一句话总结

这 11 个提交围绕 **smart-accel 完成了一次结构升级** —— smart_accel 按 scenario 拆块对齐 wings_control、decoding 走草稿 architectures 智能匹配、backend 判定改为纯形态驱动,并修了两个真实环境 bug(envsubst 空文件、none 路径),同时补全了约 2000 个模型资产。
