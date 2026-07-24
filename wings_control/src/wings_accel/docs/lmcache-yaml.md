# LMCache 三种用法归一到「方法一」(渲染态统一参考)

> 归类:🟩 参考文档。回答一个问题:上游/vllm-ascend recipe 里的 LMCache 各种启动写法(下称方法二、方法三),能不能都用 smart-accel 渲染出来的「方法一」格式(`kv_transfer_config` + `envs` + `files` 三段)表达?
> 缘起:有人在落 lmcache 资产时,面对三套来源不同的写法(平台 disk scheme / vllm upstream recipe / vllm-ascend upstream recipe)不确定它们是不是「同一种东西」。本文给出归一结论 + 字段映射 + 三个完整示例 + 归一时必须注意的坑。
> 真件口径:方法一 = `smart-yaml.md` §8.2 的 `disk`/`cpu_disk` scheme 渲染态(`offload.py::smart_kv_offload_expander` 产出)。本文与 `smart-yaml.md` 冲突时,以 `smart-yaml.md` 为准。

---

## 0. 一句话结论

**是。** 方法一 / 方法二 / 方法三在「渲染态」三段模板(`kv_transfer_config` + `envs` + `files`)上**完全统一**,差异只在**字段取值**(connector、介质、`extra_config` 内容、是否带 `files`)。

- **方法一 ≡ 方法二**:两者都是 vllm 侧 `LMCacheConnectorV1` + disk,只是 `extra_config` 不同(qat vs `use_odirect`)。方法二就是方法一换掉 qat 那段、再补几个 env。**100% 同形**。
- **方法三同形但异质**:仍是同一三段模板,但 ① connector 换成 vllm-ascend 的 `LMCacheAscendConnectorV1Dynamic`,② 多一个 `kv_connector_module_path`,③ 纯 cpu(无 disk),④ 原始写法是纯 env(无 `files`)。

> 分层提醒(重要):本文说的「归一」指**渲染态**(`--kv-transfer-config` 展开后的 YAML)。在 **smart-accel scheme 层**,当前 `disk`/`cpu_disk` expander 硬编码产出 `kv_connector: LMCacheConnectorV1`(`smart-yaml.md` §4);方法三的 ascend 动态 connector 在 scheme 层**需要平台支持**(渲染态能表达,scheme 层待确认,见 §5.3)。

---

## 1. 三种用法对照(来自哪、是什么)

| 维度 | 方法一 | 方法二 | 方法三 |
|---|---|---|---|
| 来源 | smart-accel `disk` scheme(`smart-yaml.md` §8.2) | vllm upstream recipe | vllm-ascend upstream recipe |
| 引擎 | vllm | vllm | **vllm-ascend** |
| `kv_connector` | `LMCacheConnectorV1` | `LMCacheConnectorV1` | **`LMCacheAscendConnectorV1Dynamic`** |
| `kv_connector_module_path` | — | — | **`lmcache_ascend.integration.vllm.lmcache_ascend_connector_v1`** |
| `kv_role` | `kv_both` | `kv_both` | `kv_both` |
| 其它 kv_transfer 字段 | — | `kv_load_failure_policy: recompute` | — |
| 介质 | disk(+qat) | disk | **cpu**(无 disk) |
| `extra_config` 内容 | `wings.qat` | `use_odirect: true` | `save_only_first_rank: false` |
| 配置方式 | `files`(配置文件) | env(可转 `files`) | env |
| 需要 `files` 块 | 是(disk) | 可选 | 否(cpu) |

---

## 2. 统一模板(方法一的三段骨架)

```yaml
kv_transfer_config:          # ← 来自 --kv-transfer-config '{...}' JSON,展开成嵌套 YAML
  kv_connector: <connector>            # LMCacheConnectorV1 | LMCacheAscendConnectorV1Dynamic | ...
  kv_role: kv_both
  kv_connector_module_path: <path>     # 仅外部 connector 需要(方法三)
  kv_connector_extra_config:           # 可选:connector 自身参数(disk 路径/容量等)
    local_disk: "{disk_path}"
    max_local_disk_size: "{disk_capacity_gb}"
envs:                        # ← 来自 export LMCACHE_xxx=...
  LMCACHE_CONFIG_FILE: /shared-volume/lmcache_config.yaml   # 仅「文件方式」才写(指向 files 写出的文件)
  LMCACHE_LOCAL_DISK: "{disk_path}"
  LMCACHE_MAX_LOCAL_DISK_SIZE: "{disk_capacity_gb}"
  # ...其余 LMCACHE_* 逐条搬
files:                       # ← 方法一独有:写配置文件;env 方式可省略
  - name: lmcache_config.yaml
    content: |
      chunk_size: 256
      local_disk: {disk_path}
      max_local_disk_size: {disk_capacity_gb}
      extra_config:
        <方法特有的 extra 段>
```

三段对应关系:`--kv-transfer-config` JSON → `kv_transfer_config`;`export LMCACHE_*` → `envs`;配置文件 → `files`(用 `LMCACHE_CONFIG_FILE` 指向)。

---

## 3. 字段级归一映射(方法二、三 → 方法一)

| 原始写法 | 落到方法一哪里 |
|---|---|
| `--kv-transfer-config '{"kv_connector": X, "kv_role": Y, ...}'` | `kv_transfer_config:` 下逐键展开 |
| `export LMCACHE_XXX=YYY` | `envs:` 下 `LMCACHE_XXX: YYY`(占位符整值匹配,`smart-yaml.md` §6.2) |
| `LMCACHE_EXTRA_CONFIG='{"k": v}'` 的 JSON | 既可保留为 env(`LMCACHE_EXTRA_CONFIG`),也可展开进 `files` 的 `extra_config:` 段 |
| 配置文件内容(chunk_size / local_disk / extra_config …) | `files[].content`(子串占位符,`smart-yaml.md` §6.2②) |
| 磁盘路径/容量 | 三处对齐用同一占位符:`kv_connector_extra_config` + `envs` + `files` content 都写 `{disk_path}` / `{disk_capacity_gb}` |

> 占位符(`{disk_path}` 等)只在对应开关启用时渲染;未启用/未识别的原样保留字面量(`smart-yaml.md` §6)。纯 cpu 的方法三不要写 disk 占位符。

---

## 4. 三个完整示例(渲染态)

### 4.1 方法一:disk + qat(= smart-accel disk scheme)

即 `smart-yaml.md` §8.2,文件方式:

```yaml
kv_transfer_config:
  kv_connector: LMCacheConnectorV1
  kv_role: kv_both
  kv_connector_extra_config:
    local_disk: "{disk_path}"
    max_local_disk_size: "{disk_capacity_gb}"
envs:
  LMCACHE_CONFIG_FILE: /shared-volume/lmcache_config.yaml
  LMCACHE_LOCAL_DISK: "{disk_path}"
  LMCACHE_MAX_LOCAL_DISK_SIZE: "{disk_capacity_gb}"
files:
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
```

### 4.2 方法二:disk + use_odirect(vllm upstream recipe)

与方法一同形,只换 `extra_config` + 补 `kv_load_failure_policy`。**推荐 env 方式**(原始 recipe 即 env,最忠实、零 schema 猜测):

```yaml
kv_transfer_config:
  kv_connector: LMCacheConnectorV1
  kv_role: kv_both
  kv_load_failure_policy: recompute
envs:
  LMCACHE_MAX_LOCAL_CPU_SIZE: "15"
  LMCACHE_LOCAL_CPU: "True"
  LMCACHE_CHUNK_SIZE: "256"
  LMCACHE_EXTRA_CONFIG: '{"use_odirect": true}'
  LMCACHE_PRE_CACHING_HASH_ALGORITHM: sha256_cbor_64bit
  LMCACHE_LOCAL_DISK: "{disk_path}"
  LMCACHE_MAX_LOCAL_DISK_SIZE: "600.0"
```

若平台要求三段齐全(要 `files`),转文件方式(注意 §5.1 优先级):

```yaml
kv_transfer_config:
  kv_connector: LMCacheConnectorV1
  kv_role: kv_both
  kv_load_failure_policy: recompute
  kv_connector_extra_config:
    local_disk: "{disk_path}"
    max_local_disk_size: "{disk_capacity_gb}"
envs:
  LMCACHE_CONFIG_FILE: /shared-volume/lmcache_config.yaml
  LMCACHE_LOCAL_DISK: "{disk_path}"
  LMCACHE_MAX_LOCAL_DISK_SIZE: "{disk_capacity_gb}"
files:
  - name: lmcache_config.yaml
    content: |
      chunk_size: 256
      local_cpu: true
      max_local_cpu_size: 15
      local_disk: {disk_path}
      max_local_disk_size: 600.0
      pre_caching_hash_algorithm: sha256_cbor_64bit
      extra_config:
        use_odirect: true
```

> `LMCACHE_PRE_CACHING_HASH_ALGORITHM` 有对应 yaml 键 `pre_caching_hash_algorithm`(str,`config.py:131`);`use_odirect` 是 `extra_config` 子键(自由 dict)。二者文件方式都能写——而且 env 会**覆盖**文件(§5.1),不会被忽略。

### 4.3 方法三:cpu + save_only_first_rank(vllm-ascend upstream recipe)

ascend 动态 connector,**纯 cpu、无 disk、原始即 env**:

```yaml
kv_transfer_config:
  kv_connector: LMCacheAscendConnectorV1Dynamic
  kv_role: kv_both
  kv_connector_module_path: lmcache_ascend.integration.vllm.lmcache_ascend_connector_v1
envs:
  LMCACHE_TRACK_USAGE: "false"
  LMCACHE_MAX_LOCAL_CPU_SIZE: "40"
  LMCACHE_LOCAL_CPU: "True"
  LMCACHE_LOG_LEVEL: INFO
  LMCACHE_USE_LAYERWISE: "False"
  LMCACHE_NUMA_MODE: auto
  LMCACHE_CHUNK_SIZE: "1024"
  LMCACHE_EXTRA_CONFIG: '{"save_only_first_rank": false}'
  LMCACHE_LOOKUP_SERVER_WORKER_IDS: "0,1,2,3"
# files: 无(纯 env,无 disk,不需要配置文件)
```

若转文件方式,对应 yaml 键均已核实(`config.py`):`chunk_size` / `local_cpu` / `max_local_cpu_size` / `use_layerwise`(bool,L121) / `numa_mode`(str,L402) / `lookup_server_worker_ids`(list[int],L474) / `extra_config.save_only_first_rank`。仅 `LMCACHE_TRACK_USAGE`、`LMCACHE_LOG_LEVEL` 无 yaml 键(见 §5.1 末),仍放 `envs`:

```yaml
files:
  - name: lmcache_config.yaml
    content: |
      chunk_size: 1024
      local_cpu: true
      max_local_cpu_size: 40
      use_layerwise: false
      numa_mode: auto
      lookup_server_worker_ids: [0, 1, 2, 3]
      extra_config:
        save_only_first_rank: false
```

---

## 5. 归一时必须注意的四件事

### 5.1 env 与配置文件的优先级(已核对 `/root/LMCache` 源码)

**结论:env 覆盖文件,不是二选一。** 入口 `lmcache/v1/config_base.py::load_config_with_overrides`(L564-573):

1. 设了 `LMCACHE_CONFIG_FILE` → 先 `from_file()` 加载文件作**基线**;
2. 再调 `update_config_from_env()`,遍历所有配置键,凡 env 里设了的**无条件 `setattr` 覆盖**文件值(`config.py::_update_config_from_env` L987-1031);
3. 没设 `LMCACHE_CONFIG_FILE` → `from_env()` 纯 env。

含义:

- **env 与文件可共存,env 赢**。方法一在 `envs` 与 `files` 里写同一个 `{disk_path}` 占位符正合此理:文件给可读的结构/默认,env 兜底覆盖,同值无冲突。
- 方法二/三可**既保留 env、又加 files**,env 仍生效(覆盖文件)——**不必二选一**。这恰好让 env 写法(方法二/三)与 files 写法(方法一)天然兼容,归一更顺。
- 「文件做默认基线 + env 做部署级覆盖」是官方支持的用法。

> 非引擎配置类的 env 不走上面流程:`LMCACHE_TRACK_USAGE` 由 telemetry 直读(`usage_telemetry/identity.py:38` `os.getenv`),`LMCACHE_LOG_LEVEL` 由日志模块读取——二者只放 `envs`,不进 yaml。

### 5.2 方法三是 ascend 侧,与方法一/二异质

- connector 不同(`LMCacheAscendConnectorV1Dynamic` vs `LMCacheConnectorV1`),且**必须带 `kv_connector_module_path`**(外部 connector,来自 `lmcache_ascend` 包)。
- 纯 cpu:**没有 disk**,不要写 `{disk_path}` / `{disk_capacity_gb}` / `LMCACHE_LOCAL_DISK` 等。
- 包依赖是 `lmcache_ascend`(非裸 `lmcache`),见 `docs/.../lmcache_ascend_deployment.md`。

### 5.3 scheme 层 ≠ 渲染层(平台落地注意)

本文「归一」指**渲染态**(展开后的 YAML)。落到 smart-accel yaml 资产时:

- 方法一/二 → 现有 `disk`/`cpu_disk` scheme;`kv_connector: LMCacheConnectorV1` 由资产 `cli_params` 声明、`offload.py` 透传渲染(`smart-yaml.md` §4/§8.2),**非 expander 硬编码**。
- 方法三 → ascend 动态 connector。`offload.py::_find_backend_scheme` 已识别 `LMCacheAscendConnectorV1Dynamic`(与 `AscendStoreConnector` 同列),scheme 层**已支持**:在 yaml `kv_offload:` 声明 `name: lmcache` + cli_params(`kv_connector`/`kv_connector_module_path`)+ envs(方法三 `LMCACHE_*`),`ENABLE_KV_MEM_OFFLOAD` 时即路由命中(`_render_kv_store_scheme`)。connector/module_path 由 `cli_params` 透传,非硬编码;纯 cpu、无 `files`。

### 5.4 写死注入项别写进 yaml

`LMCACHE_QAT_ENABLED` 仍由代码注入(值随 qat 自动 True/False),**不要**写进 `envs`(`smart-yaml.md` §5)。其余 `LMCACHE_*` 一律走 `envs:`。

---

## 6. 交叉引用

- `smart-yaml.md` §4(kv_offload 三 scheme)/ §5(写死注入项)/ §6(占位符)/ §8.2(disk scheme 蓝本,= 本文方法一)。
- `docs/.../lmcache_ascend_deployment.md`(vllm-ascend 侧 LMCache-Ascend 部署与 `LMCacheAscendConnectorV1Dynamic`)。
- 上游:`LMCache/LMCache-Ascend` README(connector 与 `kv_connector_module_path` 来源)。
