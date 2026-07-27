# docs/55 — smart-accel YAML 作者指南(agent / 维护同学写新资产必读)

> 归类:🟩 稳态核心 / 参考文档。给「写 smart-accel YAML 的 AI agent / 人」看的单一参考:字段怎么填、哪些东西是代码写死注入的(别写进 yaml)、占位符有哪些、以及一条硬性作者规则。
> 缘起:有人疑问「smart-accel 的 yaml 里为什么没有 `LMCACHE_CONFIG_FILE`?」——**2026-07-10 重构(docs/54)后它已移入 yaml `envs:`**(经通用 `files:` 语法落盘);重构前确为代码注入。这类「写死的环境变量/参数 / 占位符」此前散落在代码注释里,作者无单一参考,容易写错。本文一次讲清。
> 真件口径:所有断言回 `src/wings_accel/{schemas.py,decoders.py,offload.py,render.py}` 与 `config/engines/` 真实资产核对(标注 file:line)。代码与本文冲突时,以代码为准。

---

## ★ 作者决策规则(写新 smart-accel 资产先读,逐条对照)

> 两类事实来源:① **开源 recipe**——vLLM / vllm-ascend 官方示例与最佳实践 recipe;② **加速工作台 0day 测试结果**——开发验证实测。下列规则说明每个特性「以谁为准、何时写进 yaml」。字段 / 占位符 / files 语法的机械写法见后文 §1–§10,本节只讲**决策**。

### 总规则

1. **以开源 recipe 为基线**。smart-accel YAML 的特性方案默认照搬开源 recipe:recipe 有哪些特性、用什么参数,就照填进 yaml 的对应块(decoding / kv_offload / sparse)。
2. **以加速工作台 0day 测试结果做补充与覆盖**。recipe 未覆盖、但 0day 测试验证有效的特性 → 补充进 yaml;recipe 已有、但 0day 测试证明应开 / 应关 → 以测试结果覆盖 recipe。即:先按规则 1 抄 recipe,再按规则 2 以测试结果增删。
3. **版本归一**(适用于全部特性,非仅投机):旧版本资产一律归一到 **vllm v0.23.0** 与 **vllm-ascend v0.21.0rc1**(资产目录 `vllm-ascend/v0.21.0rc`);新写 / 迁移资产只落到这两个版本目录,不再维护旧版本。

### 投机(speculative decoding · 详见 §3、§7)

1. **版本归一**:投机方案以 vllm v0.23.0 / vllm-ascend v0.21.0rc1 为准(同总规则 3)。
2. **recipe 有投机 → 写进 yaml**:若开源 recipe 的 feature 含投机解码(mtp / suffix / eagle3 / ngram …),则在 `decoding` 块声明对应方案,方案与参数对齐 recipe;额外参数(`moe_backend` / `speculative_token_range` / `enforce_eager` 等)直接写进该方案的 `cli_params`(§3)。
3. **async_scheduling → 不加 suffix**:若该模型设了 `async_scheduling: true`,则 `decoding` 块**不得声明 `suffix`**(可写 `mtp` 等其它方案)。判断看 `async_scheduling` 的**值**,与引擎名无关;出处 / 自查见 §7。

### 稀疏(sparse · 详见 §3.1)

**`kv_cache_dtype: fp8` 默认不加**,按下表决定:

| 开源 recipe 的 fp8 | 0day 测试结果 | 是否在 yaml 写 fp8 |
|---|---|---|
| recipe 已开 | — | **不写**(recipe 已覆盖,避免重复 / 冲突) |
| recipe 关 | 测试证明可开 | **写**(补充) |
| recipe 关 | 测试未验证 | **不写**(保持默认) |

> 是否同时加 index cache(indexcache 形态)由 yaml 是否写 `hf_overrides: { use_index_cache, index_topk_freq }` 决定,与 fp8 开关相互独立(§3.1)。

### kv 卸载(kv_offload · 详见 §4、§10)

按「引擎 × 卸载介质」选可声明 scheme:

| 卸载介质 | vllm-ascend 可选 | vllm 可选 |
|---|---|---|
| **内存** | native、mooncake、memcache、lmcache | native、lmcache |
| **硬盘** | lmcache | lmcache |

> native / lmcache 对应 §4 的 cpu / disk / cpu_disk scheme;mooncake / memcache 仅 ascend 的 `AscendStoreConnector` 后端(§10)。具体选中哪个 scheme 由 env 开关(`ENABLE_KV_MEM_OFFLOAD` / `ENABLE_KV_DISK_OFFLOAD`)+ yaml 声明的工具(按 connector 内容路由)共同决定(见 §2 表)。

---

## 0. 一句话结论

- smart-accel YAML 只写**模板**(方案 + cli_params + envs + `files:` 配置文件内容 + `pre_serve` daemon 命令 + 占位符);
- 配置文件用**通用 `files:` 语法**落盘(docs/54);**`LMCACHE_CONFIG_FILE` 在 yaml `envs:` 声明**(指向 `files:` 写出的文件),**仅 `LMCACHE_QAT_ENABLED` 一项仍代码写死注入**(§5);
- 占位符 `{xxx}` / `$path` 在 cli_params/envs(整值)与 files content / pre_serve(子串)三处生效,见 §6;
- **KV 存储后端(memcache/mooncake)** 是 KV 内存卸载的一种方法(与 cpu 同级,非第四类介质),带 `pre_serve`/`pre_serve_master` daemon 通道(§10);
- 若该模型的 engine_config 设了 `async_scheduling: true`,**`decoding` 块不得声明 `suffix`**(§7)。
- **动态投机解码**:`speculative_config.num_speculative_tokens_per_batch_size` 按 batch size 分档动态选投机 token 数(字段须写在 `speculative_config` 内,见 §3)。

---

## 1. 文件布局与定位键

目录(出处 `schemas.py:38` SystemConfig 注释):

```
src/wings_accel/smart-accel/{engine}/v{version}/{hardware_family}/models/{model}/*.yaml
```

定位键(四元组,引擎 + 版本 + 硬件 + 模型名):**engine + version + hardware_family + model_name**。
解析入口 `resolve_smart_accel_from_config` 只吃这四元组 + 特性开关,**不依赖外部解析状态、看不到 resolved engine_config**(出处 `api.py:18-51`)——这是 §5/§7 结论的根因。

**变体匹配**:`variant_name` 精确匹配优先,`name_pattern` 正则模糊兜底 → 详见 **docs/48**。
- `model.variant_name` = MaaS 下发的精确 `--model-name`(每个文件必填,根治多变体歧义)。
- `model.match[].name_pattern` = 家族级正则,仅兜底。

---

## 2. 顶层字段总览

```yaml
model:
  name: <家族名>                 # 必填
  variant_name: "<精确 --model-name>"  # 必填(docs/48)
  match:
    - name_pattern: "<家族正则>"   # 兜底匹配

smart_accel:
  decoding:    [ <方案>, ... ]   # 投机解码方案(mtp/suffix/...),见 §3
  kv_offload:  [ <scheme>, ... ] # KV 卸载(cpu/disk/cpu_disk + memcache/mooncake 后端),见 §4、§10
  sparse:      [ <scheme>, ... ] # KV 稀疏(可选;支持 indexcache / fp8-only 两形态,见 §3 末)
  custom_features: [ ... ]       # 自定义特性(可选;仅当前三者至少一项产出时才合入)
```

每个方案/scheme 的通用字段:`name` / `priority`(int)/ `packages`(name:version)/ `cli_params`(结构化引擎参数)/ `envs`(K=V,支持占位符)。decoding 还有 `requires_model_path`(bool)。kv_offload 的 memcache/mooncake scheme 额外有 `pre_serve` / `pre_serve_master`(shell 命令,§10)。出处:`schemas.py:_FeatureOutput`、各 expander。

**特性开关走 env,不写进 yaml**(对齐护栏 §2.6):

| 特性 | 一级开关 | 关键二级开关 |
|---|---|---|
| 投机解码 | `ENABLE_SPECULATIVE_DECODE` | `SPECULATIVE_DECODE_MODEL_PATH` |
| KV 卸载 | `ENABLE_KV_OFFLOAD` | `ENABLE_KV_MEM_OFFLOAD` / `KV_MEM_OFFLOAD_SIZE` / `ENABLE_KV_DISK_OFFLOAD` / `KV_DISK_OFFLOAD_PATH` / `KV_DISK_OFFLOAD_SIZE` / `ENABLE_KV_QAT` / `KV_QAT_*` |
| KV 稀疏 | `ENABLE_SPARSE` | `SPARSE_LEVEL`(accuracy_first/performance_first) |
| **KV 存储后端**(ascend) | `ENABLE_KV_OFFLOAD` + `ENABLE_KV_MEM_OFFLOAD` | 工具由 yaml 声明、按 `kv_connector` 内容路由(AscendStoreConnector=mooncake/memcache);**不再有 `KV_STORE_BACKEND`/`KV_STORE_DEPLOY_MODE`/`KV_STORE_MASTER_ADDR`/`KV_WORLD_SIZE` env**(MaaS 不下发)。master pod 内起 daemon。 |

> yaml 的块「存在」不等于「启用」——是否产出由上面这些 env 开关决定(`smart_accel.py:215`:块存在不再自动启用任何特性)。

---

## 3. decoding 方案

出处:`decoders.py`(整文件)+ 真实资产。

**字段**:`name` / `priority` / `packages` / `cli_params` / `envs` / `requires_model_path`。

**选择规则**(`decoders.py:30-71`):
1. `ENABLE_SPECULATIVE_DECODE` 关 / PD `prefill` 节点 → 不产出(None);
2. 有草稿路径(`SPECULATIVE_DECODE_MODEL_PATH` 非空)→ **model_based 分支**:`requires_model_path=true` 且 eligible 的方案,取**首序**(无需 priority);
3. model_based 未命中 → 降级到 **no_model**(`requires_model_path=false`)中 priority 最高者(标 degraded);
4. 无草稿路径 → 直接 no_model 分支,priority 最高者。

**已知方案**(以资产实际声明为准):`mtp`、`suffix`、`ngram`、以及性能/精度优先变体等。⚠️ `suffix` 受 §7 规则约束。

`cli_params` 典型形态:`speculative_config: { method: <mtp|suffix|...>, num_speculative_tokens: N }`。

**额外参数走 `cli_params`(无需专用字段)**:模型若需 `moe_backend`(如 Qwen3.6-35B → triton)、`speculative_token_range`(如 glm-4.7-floatmtp → "256,512")、`enforce_eager` 等,直接在 `cli_params` 里写即可(`cli_params` 是自由结构化 dict,见 §8)。eagle3/dflash/dspark 这类需草稿路径的方法:加 `requires_model_path: true`,草稿路径在 `speculative_config.model` 用 `$path` 令牌。

**动态投机解码(按 batch size 分档)**:`speculative_config` 还可声明 `num_speculative_tokens_per_batch_size`(上游 vLLM `SpeculativeConfig` 字段),按当前 batch size 闭区间动态选投机 token 数;`num_speculative_tokens` 保留作兜底(调度表未命中 / 动态 SD 被 DP 禁用时用)。紧凑型 flow 写法:

```yaml
decoding:
  - name: eagle3
    requires_model_path: true
    cli_params:
      speculative_config:
        method: eagle3
        model: $path
        num_speculative_tokens: 3            # 兜底(调度表未命中 / 动态 SD 被 DP 禁用时用)
        num_speculative_tokens_per_batch_size: [[1, 64, 3], [65, 128, 1], [129, 512, 0]]  # 动态调度(batch 1-64→3 / 65-128→1 / 129-512→0)
    envs: {}
```

渲染:作为 `speculative_config` 的一个字段,随 `--speculative-config` 一起序列化成**紧凑 JSON**(嵌套 list 原样保留,渲染层无需特殊处理,见 `serializer.py`):

```
--speculative-config {"method":"eagle3","model":"/draft","num_speculative_tokens":3,"num_speculative_tokens_per_batch_size":[[1,64,3],[65,128,1],[129,512,0]]}
```

⚠️ **位置规则**:该字段是 `SpeculativeConfig` 字段,**必须写在 `speculative_config` 内**——不能提到 `cli_params` 顶层(否则渲染成 `--num-speculative-tokens-per-batch-size`,vLLM 无此顶层 flag → `unrecognized arguments`)。

⚠️ **格式规则**:每条 `[range_start, range_end, num_speculative_tokens]`(闭区间)。文档示例统一用紧凑型 flow 写法 `[[1,64,3],[65,128,1],[129,512,0]]`(block `- [1,64,3]` 语法也合法,但不采用)。

⚠️ **vLLM 限制**:开 data parallel 时该字段被 vLLM 置 None(动态 SD 不支持 DP),退回 `num_speculative_tokens` 静态值。

### 3.1 sparse 方案(两形态)

`sparse` scheme 的 `name` 即模式门键(`performance_first` / `accuracy_first`),由 `SPARSE_LEVEL` 选。两种写法(对齐 Wings-infer sparse 表的 indexcache / fp8 两 strategy):

- **indexcache 形态**(带 index cache):`cli_params` 含 `hf_overrides: {use_index_cache: true, index_topk_freq: N}` + `kv_cache_dtype: fp8`(performance_first freq 小、accuracy_first freq 大)。
- **fp8-only 形态**(无 index cache,仅量化):`cli_params` **只写 `kv_cache_dtype: fp8`,不写 `hf_overrides`**(对应 Wings-infer `strategy: fp8`,如 glm-4.7-fp8 / qwen3.6-27b)。

> 即:要不要开 index cache 完全由 yaml 是否写 `hf_overrides` 决定——sparse expander 只做模式匹配 + 原样渲染,不解释参数语义。

---

## 4. kv_offload 方案

出处:`offload.py`。

三 scheme 三选一(`offload.py:86-91`),由 `ENABLE_KV_MEM_OFFLOAD`(mem)/ `ENABLE_KV_DISK_OFFLOAD`(disk)组合决定:

| (mem, disk) | 选中 scheme | 说明 |
|---|---|---|
| (T, F) | `cpu` | vLLM 原生 `OffloadingConnector`,**无 lmcache 包、无 lmcache_config** |
| (F, T) | `disk` | lmcache(`LMCacheConnectorV1`),需 `lmcache` 包 + `lmcache_config.yaml` |
| (T, T) | `cpu_disk` | lmcache 同时管 cpu+disk(比 disk 多 `local_cpu` + `max_local_cpu_size`) |
| (F, F) | — | 不卸载(None) |

fallback:目标 scheme 缺失时,`cpu_disk` 缺 → 退化 `disk > cpu > None`;`cpu/disk` 缺 → None(`offload.py:93-103`)。

- `cpu`:`kv_transfer_config.kv_connector = OffloadingConnector`;CUDA 原生 vLLM(≥v0.14)读 `cpu_bytes_to_use`(字节),用 `{mem_gb_to_bytes}`(见真实资产 Qwen3.5-397B-A17B)。
- `disk` / `cpu_disk`:`kv_connector = LMCacheConnectorV1`;`packages` 带 `lmcache: v0.3.15`;**用 `files:` 字段提供配置文件内容模板**(`lmcache_config.yaml` 等),见 §5、§8 示例。

---

## 5. 🔧 写死的注入项 vs yaml 可配项(直接回答「LMCACHE_CONFIG_FILE 在哪」)

**2026-07-10 重构(docs/54)后**:配置文件落盘改为通用 `files:` 语法,`LMCACHE_CONFIG_FILE` 已**移入 yaml `envs:`**(作者写,指向 `files:` 写出的文件);**仅剩 `LMCACHE_QAT_ENABLED` 一项仍代码注入**(它是派生 env,值依赖 engine∧qat,无法静态写死)。

| 名称 | 现状 | 触发条件 | 作者该怎么做 |
|---|---|---|---|
| `LMCACHE_CONFIG_FILE` | **yaml `envs:` 声明**(字面量指向 `files:` 写出的文件) | disk/cpu_disk scheme 有 `files:` 块 | 在 scheme 的 `envs:` 写 `LMCACHE_CONFIG_FILE: /shared-volume/lmcache_config.yaml`(路径与 `files[].name` 对齐);用 `files:` 提供配置**内容** |
| `LMCACHE_QAT_ENABLED` | **代码注入**(唯一写死项) | 同上 | **不要**写进 `envs:`;值随 qat 自动 `True`/`False`(effective = vllm 且 `ENABLE_KV_QAT`) |

机制(`offload.py::smart_kv_offload_expander` + `render.py::write_scheme_files`):disk/cpu_disk 命中且有 `files:` 块时,`write_scheme_files` 把每个文件 `content` 填占位符(§6)后写到 `SHARED_VOLUME_PATH/<name>`,并注入 `LMCACHE_QAT_ENABLED`。**disk 命中但缺 `files:` 块** → 仅 WARN,不写盘、不注入。

> 除 `LMCACHE_QAT_ENABLED` 外,**其余 env 一律走 scheme 的 `envs:` 块**(可带占位符,见 §6)。例:`LMCACHE_LOCAL_DISK`、`LMCACHE_MAX_LOCAL_DISK_SIZE`、`LMCACHE_CONFIG_FILE` 都是作者在 `envs:` 里写的(见 §8 disk 示例)。通用 `files:` 机制完整设计见 **docs/54**。

---

## 6. 占位符参考(总表 + 用法 + 公式 + 如何新增)

出处:`render.py`(`PlaceholderContext` L43-57 + `_resolve_token` L64)。`_resolve_token` 是占位符解析的**单一判定点**:cli_params/envs(整值匹配)与 files content(子串匹配)都走它。占位符在对应开关**启用**时渲染成真值;**未启用 / 未识别的原样残留字面量**(不报错),故只在对应开关下使用。

### 6.1 占位符总表(含义 + MaaS 来源 + 公式)

| 占位符 | 渲染为 | MaaS 来源(经 `LoadFlags` → `PlaceholderContext`) | 启用条件 | 公式 / 换算 | 出处 |
|---|---|---|---|---|---|
| `{memory_capacity_gb}` | CPU 卸载容量(GB,int) | `KV_MEM_OFFLOAD_SIZE`("auto" 估算 / 数值 GB) | `ENABLE_KV_MEM_OFFLOAD` | — | `render.py:83` |
| `{disk_capacity_gb}` | 磁盘容量(GB,int) | `KV_DISK_OFFLOAD_SIZE`(int GB) | `ENABLE_KV_DISK_OFFLOAD` | — | `render.py:85` |
| `{disk_path}` | 磁盘路径(str) | `KV_DISK_OFFLOAD_PATH` | 同上 | — | `render.py:87` |
| `{mem_gb_to_bytes}` | CPU 卸载容量(**字节**) | 同 `{memory_capacity_gb}` | `ENABLE_KV_MEM_OFFLOAD` | `GiB→字节`:`int(cap)*1024**3`(见 §6.3) | `render.py:94` |
| `{mem_gb_to_blocks}` | CPU 卸载容量(**块数**) | 同 `{memory_capacity_gb}` | 同上 | `GiB→块`:`int(cap*1024)//16`(每块 16 KiB) | `render.py:89` |
| `{cpu_swap_space_gb}` | 恒 `0`(offload 时 swap_space=0 策略) | — | `ENABLE_KV_MEM_OFFLOAD` | 策略常量 `0` | `render.py:100` |
| `{qat_enabled}` | `true` / `false`(effective = vllm ∧ `ENABLE_KV_QAT`) | `ENABLE_KV_QAT` | 随 qat | — | `render.py:103` |
| `{qat_device_count}` | QAT 实例数(int) | `KV_QAT_INSTANCE_NUM` | 随 qat | — | `render.py:105` |
| `{qat_compression_level}` | QAT 压缩级(int) | `KV_QAT_COMPRESS_LEVEL` | 随 qat | — | `render.py:107` |
| `$path` / `$draft_model_path` | 草稿模型路径(str) | `SPECULATIVE_DECODE_MODEL_PATH` | decoding | — | `render.py::_fill_str` |
| `{rank_ip}` | per-node 本机 IP(运行时 envsubst 展开) | `RANK_IP`(拓扑注入) | KV 后端 | resolve 期→`${RANK_IP}`,运行时 envsubst 展开 | 同上 |
| `{master_ip}` | master IP(运行时 envsubst 展开) | `MASTER_IP` | KV 后端 | resolve 期→`${MASTER_IP}`,运行时 envsubst 展开 | 同上 |
| `{lookup_server_worker_ids}` | lmcache lookup server worker ids `"0,1,…,N-1"` | `tensor_parallel_size`(yaml)→ `tp_size` | lmcache(disk/cpu_disk) | `",".join(range(tp_size))` | `render.py::_resolve_token` |

> **端口 / 协议不再有占位符**(v2):mooncake `50088`、memcache `15000/16000`、协议 `device_rdma/device_sdma` 等全由 YAML 资产 / backend 共享模板(`kv_backends/<backend>/`)明文声明,代码不写死。IP 用 `{rank_ip}`/`{master_ip}`,运行时 envsubst 展开;`{kv_master_endpoint}`/`{kv_world_size}`/`{kv_master_port}`/`{kv_protocol}` 已移除。memcache `world_size` 为 conf 字面量(作者手填,不经占位符)。

> 「MaaS 来源」= 该值最终来自的产品侧 env/CLI,经 `yaml_loader.LoadFlags` → `SmartXxxConfig` → `core._build_placeholder_context` 派生进 `PlaceholderContext`。`{qat_*}` 在 offload expander 里会被 effective 闸改写(仅 vllm 视为 qat-on)后再喂给 files content。

### 6.2 yaml 里怎么用(两种用法)

同一判定点 `_resolve_token`,两种填充入口:

**① cli_params / envs —— 整值匹配**:占位符必须是**整个值**(YAML 字符串)。用 `_fill_str`(整值精确命中)。
```yaml
cli_params:
  kv_transfer_config:
    kv_connector_extra_config:
      cpu_bytes_to_use: "{mem_gb_to_bytes}"   # 整值 = 占位符 → 替换
envs:
  LMCACHE_MAX_LOCAL_CPU_SIZE: "{memory_capacity_gb}"
```

**② files: content —— 子串匹配**:占位符嵌在**多行文本**里任意位置(配置文件内容)。用 `_fill_str_substr`(正则逐个替换)。
```yaml
files:
  - name: lmcache_config.yaml
    content: |
      chunk_size: 256
      local_disk: {disk_path}                 # 子串 → 替换
      extra_config:
        wings:
          qat:
            enabled: {qat_enabled}            # 子串 → 替换
            instance_num: {qat_device_count}
```

> 未识别 / 条件未满足的占位符(如 disk 关闭时的 `{disk_path}`)**原样保留字面量**,不报错——故占位符只在对应开关启用时才该出现在模板里。

### 6.3 公式换算占位符(怎么体现公式)

`{mem_gb_to_bytes}` / `{mem_gb_to_blocks}` 这类**带换算**的占位符:公式**就地写死在 `_resolve_token` 里,是显式 Python 表达式**——**不是**字符串公式、**禁止** eval/exec(护栏 §2.5:不造公式 DSL)。改公式 = 改这一处代码 + 注释。

| 占位符 | 公式(`cap` = `memory_capacity_gb`,单位 GiB) | 含义 / 用在哪 |
|---|---|---|
| `{mem_gb_to_bytes}` | `str(int(cap) * 1024 * 1024 * 1024)` | GiB → 字节;原生 vLLM(CUDA)≥v0.14 的 `cpu_bytes_to_use` 读字节(全 TP 合计) |
| `{mem_gb_to_blocks}` | `str(int((cap * 1024) // 16))` | GiB → KiB(×1024)→ 块(÷16 KiB/块);vllm-ascend(NPU)`num_cpu_blocks` 读块数 |
| `{cpu_swap_space_gb}` | `"0"`(常量) | M_swap=0 策略:offload 时 swap_space=0,不再吃 offload 容量 |

> 加新换算占位符:在 `_resolve_token` 加 `if token == "{xxx}": return <显式表达式>` 分支,公式写死 + 注释;**不要**引入求值器或把公式放进 yaml。

### 6.4 怎么加一个新占位符

1. **`render.py::PlaceholderContext`** 加字段(带 docstring 注明 MaaS 来源 + 默认值)。
2. **`core.py::_build_placeholder_context`** 从 `SmartXxxConfig` / `LoadFlags` 派生该字段;若值来自**新** env/CLI,先在 `yaml_loader.py::LoadFlags` + 对应 env/CLI 映射补来源(并回贴 `SmartXxxConfig` 的 MaaS 对齐注释)。
3. **`render.py::_resolve_token`**(单一判定点)加分支:返回解析值,条件未满足返回 `None`(→ 原样保留)。带换算的公式就地写死(§6.3)。
4. **测试**:`tests/wings_accel/test_render.py` 加用例(整值 + 子串各一条,含「条件未满足→保留字面量」)。
5. **本文 §6.1 总表** 补一行(占位符 / 含义 / MaaS 来源 / 公式 / 出处)。

> 占位符解析**只在 `_resolve_token` 一处判定**;新增时改这一处即可,**勿在 expander 里另写填充逻辑**(会破坏单一判定点)。

---

## 7. ⚠️ 作者规则:async_scheduling × suffix

**规则**:若该模型在 `config/engines/{vllm|vllm-ascend}/...` 的 engine_config 里设了 `async_scheduling: true`,则其 smart-accel yaml 的 `decoding` 块**不得声明 `suffix`**(写 `mtp` 等其它方案即可)。

**判断口径**:看 `async_scheduling` 的**值**(是否 `true`),与引擎名无关——**不是** `if engine == "vllm"`(对齐红线 §3,控制流不按引擎分支)。`vllm` 和 `vllm-ascend` 只是两个会用到该参数的引擎目录。

**怎么自查**:对该模型对应的 version/hardware 目录 grep——
```bash
grep -rn "async_scheduling: true" \
  config/engines/{vllm,vllm-ascend}/<version>/<hardware>/models/<model>/
```
命中即代表该模型不能在 smart-accel yaml 里写 `suffix`。

**存量违例(已修复)**:`DeepSeek-V4-Flash` 的 48G 与 72G engine_config 均设了 `async_scheduling: true`(`config/engines/vllm/rtx_pro_5000_{48G,72G}/.../DeepSeek-V4-Flash-fp8.yaml:74`),其 smart-accel 资产(v0.22.0,48G/72G)原声明了 `suffix` → 已按本规则从两份资产移除 `suffix` 条目(仅保留 `mtp`)。`Qwen3.5-397B-A17B` 的 engine_config 无 `async_scheduling`,其 smart-accel 资产可保留 `suffix`,未动。

> 说明:当前 `async_scheduling` 由 `config/engines/` 配置树持有,smart-accel 解析时**看不到**它(`api.py:18-51` 只吃四元组 + 开关)。故本规则目前是**作者侧约定**(写新 yaml 时自查),不靠运行时代码强制。是否要加运行时闸/lint,另案讨论。

---

## 8. 完整示例

### 8.1 cpu scheme(真实资产,可直接引)

`smart-accel/vllm/v0.23.0/rtx_pro_5000_72G/models/Qwen3.5-397B-A17B/Qwen3.5-397B-A17B-nvfp4.yaml`:

```yaml
model:
  name: Qwen3.5-397B-A17B
  variant_name: "Qwen3.5-397B-A17B-nvfp4"
  match:
    - name_pattern: "(?i)qwen3[-.]?5[-.]?397b[-.]?a17b"
smart_accel:
  decoding:
    - name: mtp
      priority: 2
      cli_params:
        speculative_config: { method: mtp, num_speculative_tokens: 3 }
      envs: {}
    - name: suffix          # ⚠️ 受 §7 约束:若该模型 engine_config 有 async_scheduling:true 则删此条;arctic-inference 默认已预装,不声明 packages
      priority: 1
      cli_params:
        speculative_config: { method: suffix, num_speculative_tokens: 16 }
      envs: {}
  kv_offload:
    - name: cpu
      cli_params:
        kv_transfer_config:
          kv_connector: OffloadingConnector
          kv_role: kv_both
          kv_connector_extra_config:
            # 原生 vLLM(CUDA)≥v0.14 读 cpu_bytes_to_use(字节),用 {mem_gb_to_bytes}
            cpu_bytes_to_use: "{mem_gb_to_bytes}"
      envs: {}
```

### 8.2 disk / cpu_disk scheme(+ `files:` 配置文件)

蓝本取自 `tests/wings_accel/test_offload.py`(`make_block` / `_lmcache_files`)。disk 命中时,`write_scheme_files` 把 `files:` 的 content 填占位符(§6)后写到 `/shared-volume/lmcache_config.yaml`;`LMCACHE_CONFIG_FILE` 在 `envs:` 指过去(§5);`LMCACHE_QAT_ENABLED` 代码注入。

```yaml
smart_accel:
  kv_offload:
    - name: disk
      packages:
        lmcache: v0.3.15
      cli_params:
        kv_transfer_config:
          kv_connector: LMCacheConnectorV1
          kv_role: kv_both
          kv_connector_extra_config:
            local_disk: "{disk_path}"            # 整值占位符(cli_params)
            max_local_disk_size: "{disk_capacity_gb}"
      envs:                            # 「普通」env,作者写;LMCACHE_CONFIG_FILE 在此声明(非写死注入)
        LMCACHE_CONFIG_FILE: /shared-volume/lmcache_config.yaml
        LMCACHE_LOCAL_DISK: "{disk_path}"
        LMCACHE_MAX_LOCAL_DISK_SIZE: "{disk_capacity_gb}"
      files:                           # ↓ 通用写文件:content 填占位符(子串)后落 /shared-volume/<name>
        - name: lmcache_config.yaml
          content: |
            chunk_size: 256
            local_disk: {disk_path}
            max_local_disk_size: {disk_capacity_gb}
            extra_config:
              wings:
                qat:
                  enabled: {qat_enabled}
                  module_name: kv_agent
                  instance_num: {qat_device_count}
                  loss_level: {qat_compression_level}
                  log_enabled: 1
    # cpu_disk:比 disk 多 local_cpu:true + max_local_cpu_size:{memory_capacity_gb},
    #          envs 多 LMCACHE_LOCAL_CPU / LMCACHE_MAX_LOCAL_CPU_SIZE(见 test_offload.py::_lmcache_files)
```

---

## 9. 交叉引用

- **docs/48** — 模型多变体选择契约(`variant_name` 精确 + `name_pattern` 兜底)。
- **docs/54** — 通用 `files:` 配置文件渲染设计(lmcache/mooncake 统一落盘;§5 机制的权威来源)。
- **docs/40** — wings-accel 集成;**docs/45** — 引擎参数互操作(含 install 段)。
- 真码:`src/wings_accel/schemas.py`(数据契约)、`decoders.py`(decoding 选择)、`offload.py`(kv 卸载 + `LMCACHE_QAT_ENABLED` 写死注入 + memcache/mooncake 后端选择)、`render.py`(`write_scheme_files` + 占位符 `_resolve_token` + `render_pre_serve`)、`yaml_loader.py`(yaml 装载)。
- 护栏:`CLAUDE.md` §2.5(占位符公式写死、禁 DSL/eval)、§2.6(env 特性开关不进 user_cli)、§3(不 if-engine)。

---

## 10. KV 存储后端(memcache / mooncake)

> 出处:`offload.py::_render_kv_offload_expander`(后端分支)+ `_render_kv_store_scheme`。
> 适用:ascend 模型的 `AscendStoreConnector` + `backend: memcache|mooncake`(KV 内存卸载/memcache 用法,**不是** PD 传输)。

### 10.1 选中条件与后端选择

`kv_offload` 里声明 **`cpu` 介质 scheme**(scheme 的 `name` 始终是 `cpu`,**不是**与 cpu/disk/cpu_disk 并列的 `mooncake`/`memcache` 名)。它是**KV 内存卸载的方法**(与 cpu 同级),**工具由 yaml 声明、按 `kv_connector` 内容路由**——`kv_connector == AscendStoreConnector` 的 scheme 即后端工具(`offload._find_backend_scheme` 扫块找首个);`memory_on`(`ENABLE_KV_MEM_OFFLOAD`)时用它(走 `_render_kv_store_scheme`),否则落回 cpu/disk/cpu_disk 三选一。**一份 yaml 至多声明一个后端工具**(memcache 或 mooncake,或都不声明)。memcache 纯内存,mooncake 可内存+磁盘;与 disk 组合由 YAML 负责。**不再有 `KV_STORE_BACKEND` env**——不写 `if engine ==`,只在 ascend 模型 YAML 里声明,靠资产分布分流。

```yaml
kv_offload:
  - name: cpu         # scheme name = 介质 cpu;connector=AscendStoreConnector + backend:mooncake → 工具是 mooncake
    ...
  # memcache 同构:name 也是 cpu(backend:memcache);一份 yaml 至多声明一个后端工具(或不声明,走 cpu/disk/cpu_disk)
```

### 10.2 `files:` 自描述 + 框架自动生成 pre_serve(v2)

vllm serve 前要起 KV 协调服务(`mooncake_master` / memcache `MetaService`)并生成 per-node 配置文件。v2 用**自描述 `files:`** 表达,框架自动合成运行时步骤——**资产作者不在 YAML 写任何 shell**(无 pre_serve / envsubst / nc / for 循环)。

**files 条目字段:**

| 字段 | 必填 | 含义 |
|---|---|---|
| `path` | ✅ | 落盘路径(容器内;相对 `SHARED_VOLUME_PATH` 或绝对 `/...`) |
| `content` / `src` | 二选一 | `content`=**首选**,明文内联(`content: \|` 块标量,任意 JSON/conf/sh);`src`=外置模板相对 `config_root`(`kv_backends/<backend>/...`),仅超长/缩进敏感内容兜底 |
| `scope` | ❌ | `all`(默认,所有节点)/ `master`(仅 master)/ `client`(仅 client/非 master) |
| `mode` | ❌ | 权限,如 `"0755"`(脚本执行位) |

**content 文本里的占位符与算术:** 除 `{name}` 字面占位符(如 `{rank_ip}`、`{master_ip}`)外,content / cli_params / envs 的字符串还支持 **`{= expr}` 算术求值**——把派生值在 YAML 里直接算出来。白名单运算符 `+ - * / // % **` 与括号,基于 `ast` 安全求值(**不含 `eval`**;函数调用 / 属性访问 / 未知变量一律拒,原样保留 `{= ...}` 字面量)。可用变量:

| 变量 | 含义 |
|---|---|
| `memory_capacity_gb` / `disk_capacity_gb` | KV 内存/磁盘容量(GiB) |
| `gpu_count` | 卡数(= device_count) |
| `tp_size` | 张量并行度(`tensor_parallel_size`) |
| `qat_device_count` / `qat_compression_level` | QAT 卡数 / 压缩级别 |

例:`dram.size = {= memory_capacity_gb // gpu_count}GB`(8 GiB / 4 卡 → `2GB`)。

**框架自动行为(用户无感,`offload._synthesize_file_pre_serve`):** 任何文件 → `mkdir -p`;写盘内容含 `{rank_ip}`/`{master_ip}`(渲染为 `${VAR}`)→ 运行时 `envsubst` 原地展开(per-node IP);按 `scope` 分流到三个桶:all → 所有节点 / master → 仅 master(包运行时 `RANK_IP==MASTER_IP`)/ client → 仅 client/非 master(包 `RANK_IP!=MASTER_IP`,单机不跑)。**daemon**:名为 **`start_kv_serve.sh`** 的脚本(mooncake/memcache 统一)→ 仅 master 执行 `bash <path> &`(**不监听端口**,避免 vllm 抢跑靠部署侧重试/保证)。脚本内容仍由 `files:` 的 `content`/`src` 声明,框架只按文件名识别「master 跑这个脚本」。

> master pod 内 master 也跑 vllm,故常见配置多为 `all`(master 与 worker 都需)或 `master`(仅 daemon 侧);`client` 供「master 专用、仅 worker 需某配置」的拓扑(如 dedicated master pod)。

> 旧 `pre_serve` / `pre_serve_master` 仍作**逃生口**保留(YAML 显式声明时追加在自动生成之后),常规后端无需写。master 判定 `if [ -z "${MASTER_IP:-}" ] || [ "${RANK_IP:-}" = "${MASTER_IP:-}" ]; then ... fi` 由 `script_builder._render_accel_pre_serve_section` 自动包裹。

### 10.3 关键写法要点(对照 Wings-infer)

- **`global_segment_size` / `dram.size` 用 `{= memory_capacity_gb // gpu_count}GB`**(per-card `"<N>GB"` 就地算,= `KV_MEM_OFFLOAD_SIZE` // device_count;**不是字节**)。
- **`master_server_address` / `meta_service_url` 用 `{master_ip}:<port>`**(`{master_ip}` 只给 host;端口字面量拼;渲染为 `${MASTER_IP}`,运行时 envsubst 展开)。**per-node 字段(`local_hostname`/`config_store_url`)用 `{rank_ip}`**。
- **per-node `local_hostname` 用 `{rank_ip}`**(渲染为 `${RANK_IP}`,运行时 envsubst 展开)。
- **mooncake 必加 `LD_LIBRARY_PATH: "/usr/local/lib:${LD_LIBRARY_PATH:-}"`**(加载 ascend_transport.so;memcache 不加——install.py 已注入)。
- **端口 / 协议 / daemon 参数全字面量**(mooncake 50088、memcache 15000/16000、`device_rdma`/`device_sdma`);`lookup_rpc_port` 固定(mooncake="1" / memcache="0")。**不再有 `{kv_master_port}`/`{kv_protocol}` 占位符**。
- **内联 `content:` 首选**:脚本 / conf / json 直接内联进 YAML(`content: |` 块标量);超长或缩进敏感内容可 `src` 外置模板(`kv_backends/<backend>/`)兜底。
- **算术派生值用 `{= expr}`**:`{= memory_capacity_gb // gpu_count}GB` 在 YAML 里就地算(变量见 §10.2),免新增 Python 占位符 token。
- **memcache `world_size` 是手填字面量**:`ock.mmc.local_service.world_size` = KV 卸载协调的 worker 总数(随部署节点数 × TP/DP 变),不经占位符 / `{= expr}`(无单一变量可表达);当前 ascend-a3 的 memcache 资产统一填 `256`,**换部署规模 / 拓扑时作者必须同步手改**,否则 KV 协调方数会错。mooncake 用 `P2PHANDSHAKE`,无此字段。

### 10.4 mooncake scheme 示例(ascend-a2 / MiniMax-M2.7-w8a8)

```yaml
kv_offload:
  - name: cpu           # scheme name = 介质 cpu(工具 mooncake 由 connector+backend 区分)
    cli_params:
      kv_transfer_config:
        kv_connector: AscendStoreConnector
        kv_role: kv_both
        kv_load_failure_policy: recompute
        kv_connector_extra_config: {lookup_rpc_port: "1", backend: mooncake}
    envs:
      MOONCAKE_CONFIG_PATH: /shared-volume/mooncake.json
      LD_LIBRARY_PATH: "/usr/local/lib:${LD_LIBRARY_PATH:-}"   # mooncake 必加(memcache 不加)
    files:                                  # 自描述:内联 content + daemon 脚本,框架自动生成 pre_serve
      - path: mooncake.json
        scope: all
        content: |
          {
            "local_hostname": "{rank_ip}",
            "metadata_server": "P2PHANDSHAKE",
            "protocol": "ascend",
            "device_name": "",
            "master_server_address": "{master_ip}:50088",
            "global_segment_size": "{= memory_capacity_gb // gpu_count}GB",
            "preferred_segment": false,
            "prefer_alloc_in_same_node": true
          }
      - path: start_kv_serve.sh
        mode: "0755"
        content: |
          #!/usr/bin/env bash
          mooncake_master --port 50088 \
              --eviction_high_watermark_ratio 0.9 \
              --eviction_ratio 0.1 \
              --default_kv_lease_ttl 11000
```

content 用 `{rank_ip}`/`{master_ip}` 占位符 + `{= memory_capacity_gb // gpu_count}GB` 算术派生 per-card 大小,端口 `50088`/协议 `ascend` 字面量(见 §10.2)。memcache 同构:`backend: memcache` / `lookup_rpc_port: "0"`、`envs` 带 `MMC_META_CONFIG_PATH`+`MMC_LOCAL_CONFIG_PATH`、3 个 files(`mmc_local.conf` scope=all / `mmc_meta.conf` scope=master / `start_kv_serve.sh` daemon);**`mmc_local.conf` 的 `world_size` 为字面量(作者手填,不经占位符)**。lmcache(disk/cpu_disk)想给 lookup server worker ids:envs 写 `LMCACHE_LOOKUP_SERVER_WORKER_IDS: "{lookup_server_worker_ids}"`(tp_size=N → `0,1,…,N-1`)。完整资产见 `smart-accel/vllm-ascend/v0.21.0rc/ascend-a2/models/MiniMax-M2.7/MiniMax-M2.7-w8a8.yaml`;超长/缩进敏感内容可改用 `src` 外置模板(`smart-accel/kv_backends/<backend>/`)。
