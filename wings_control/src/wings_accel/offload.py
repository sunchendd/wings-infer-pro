"""
KVOffload Expander — 智能 KV 卸载方案选择与渲染。

重要关键点:
- name = **介质**,三 scheme(cpu / disk / cpu_disk)三选一,按 (memory_offload_enabled, disk_offload_enabled)
  组合:(T,F)→cpu;(F,T)→disk;(T,T)→cpu_disk;(F,F)→None。不再深合并 cpu+disk。
- KV 存储后端(memcache/mooncake)是 **cpu 介质**下的内存卸载工具实现(scheme 的 ``name`` 仍为 ``cpu``,
  非第四类介质):工具由 yaml 声明、按 ``kv_connector`` 内容路由(connector==AscendStoreConnector 的 cpu
  scheme 即后端工具,具体 backend 由 ``kv_connector_extra_config.backend`` 定),memory_on 时用该
  backend scheme(走 ``_render_kv_store_scheme``);与 disk 的组合由 YAML 负责。
- fallback:目标 scheme 缺失时,cpu_disk 缺 → 退化 disk > cpu > None;cpu/disk 缺 → None。
- cpu = vllm 原生 OffloadingConnector(无 lmcache 包 / 不落盘配置文件)。
- disk / cpu_disk = lmcache(LMCacheConnectorV1):需 lmcache 包 + lmcache_config.yaml
  (yaml 为容量真相源;env/cli 为补充)。cpu_disk 比 disk 多 local_cpu:true + max_local_cpu_size。
- 容量类占位符({mem_gb_to_blocks} 等)由 PlaceholderContext 解析;容量值由 yaml_loader 决定。
- 配置文件落盘:disk/cpu_disk 命中且有 files: 块时,由通用 render.write_scheme_files
  渲染(占位符 {qat_*} 经 ctx 填充;qat_enabled 用 effective = vllm 且 cfg.qat_enabled)写到
  SHARED_VOLUME_PATH/<name>。指向文件的 env(如 LMCACHE_CONFIG_FILE)由 scheme 的 envs: 字面量
  声明,不再代码注入。LMCACHE_QAT_ENABLED 是派生 env(随 qat 开关,仅 vllm effective-on),
  仍代码注入。非 disk 命中 / 无 files 块 → 跳过(仅 WARN,不阻塞启动)。

方案结构:
    - name:       介质 cpu / disk / cpu_disk(后端工具 mooncake/memcache 也用 cpu,由 connector 区分)
    - packages:   pip 依赖(name:version);disk/cpu_disk 带 lmcache:v0.3.15
    - cli_params: 任意键值对(典型 kv_transfer_config: {...}),由 render 渲染
    - envs:       环境变量(支持 {memory_capacity_gb} / {mem_gb_to_blocks} 等占位符);
                  指向落盘文件的 env(如 LMCACHE_CONFIG_FILE)在此字面量声明
    - files:      要落盘的配置文件列表([{name, content}],通用语法;disk/cpu_disk 放 lmcache_config.yaml)
"""

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_accel.render import (
    PlaceholderContext,
    extract_packages,
    fill_envs,
    render_engine_config,
    render_pre_serve,
    write_scheme_files,
)
from wings_accel.schemas import EngineParams, SmartKVCacheConfig, _FeatureOutput

logger = logging.getLogger(__name__)

# KV 存储后端 daemon 脚本名(mooncake/memcache 统一):仅 master 执行
# ``bash <path> &``。脚本内容/落盘仍由 scheme 的 ``files:`` 声明(内联 content);框架只硬编码
# 「master 跑这个脚本」一条,不识别后端、不监听端口(避免 vllm 抢跑靠部署侧重试/保证)。
_KV_DAEMON_SCRIPT = "start_kv_serve.sh"


def _find_backend_scheme(block: List[Any]) -> Optional[Dict[str, Any]]:
    """在 kv_offload block 中找后端 scheme(``kv_connector`` 为 ``AscendStoreConnector``[mooncake/memcache]
    或 ``LMCacheAscendConnectorV1Dynamic``[ascend lmcache,方法三])。

    工具选择按 connector 内容路由(不再靠 ``KV_STORE_BACKEND`` env)。一份 yaml 至多声明一个
    后端 scheme;命中多个取首个。
    """
    for s in block or []:
        if not isinstance(s, dict):
            continue
        kt = (s.get("cli_params") or {}).get("kv_transfer_config") or {}
        if (kt.get("kv_connector") or "") in ("AscendStoreConnector", "LMCacheAscendConnectorV1Dynamic"):
            return s
    return None


def smart_kv_offload_expander(
    cfg: SmartKVCacheConfig,
    block: Any,
    ctx: PlaceholderContext,
    engine_name: str = "vllm",
) -> Optional[_FeatureOutput]:
    """智能 KV 卸载方案选择与渲染。

    KV 存储后端(memcache/mooncake)是 **cpu 介质**下的内存卸载工具实现(scheme 的 name 仍为 cpu,
    非 cpu/disk 之外的第四类介质)。命中 backend scheme(connector==AscendStoreConnector)→ 内存方法
    走 ``_render_kv_store_scheme``,backend 命中即蕴含 memory_on;否则回落下面的 cpu/disk/cpu_disk 三选一。

    选择(由 cfg.memory_offload_enabled / disk_offload_enabled 组合):
      (mem, disk) = (T,F) → cpu;(F,T) → disk;(T,T) → cpu_disk;(F,F) → None。
    fallback:目标 scheme 缺失时,cpu_disk 缺 → 退化 disk > cpu > None;cpu/disk 缺 → None。

    cpu = vllm 原生 OffloadingConnector(无 lmcache 包 / 不落盘配置文件)。
    disk / cpu_disk = lmcache(LMCacheConnectorV1):需 lmcache 包 + lmcache_config.yaml
    (yaml 为容量真相源;env/cli 为补充)。cpu_disk 比 disk 多 local_cpu:true + max_local_cpu_size。
    QAT 正交:disk/cpu_disk 命中且有 files: 块 → 通用 write_scheme_files 落盘配置文件(如
    lmcache_config.yaml)+ 注入派生 env LMCACHE_QAT_ENABLED(随 qat 开关,effective = vllm 且
    cfg.qat_enabled);指向文件的 env(如 LMCACHE_CONFIG_FILE)由 scheme 的 envs: 声明。

    Args:
        cfg: KV cache 配置(memory_offload_enabled / disk_offload_enabled / qat_*)。
        block: kv_offload scheme 列表(cpu/disk/cpu_disk 各最多一项)。
        ctx: 占位符上下文。
        engine_name: 引擎名;仅 vllm 启用 QAT。

    Returns:
        _FeatureOutput(选中 scheme + 渲染后 EngineParams + packages);无可选 → None。
    """
    # 主开关关 / 未配置 / 非 list → None
    if not cfg.enabled or not isinstance(block, list) or not block:
        return None

    # name → scheme(cpu/disk/cpu_disk 各最多一项;重名取后者,与历史 last-write-wins 一致)
    schemes: Dict[str, Dict[str, Any]] = {
        str(s.get("name")): s
        for s in block
        if isinstance(s, dict) and s.get("name")
    }

    # KV 存储后端(memcache/mooncake)是 **cpu 介质**下的内存卸载工具实现(scheme 的 name 仍为 cpu,
    # 非 cpu/disk 之外的第四类介质)。工具由 yaml 声明、按 connector 内容路由:扫 block 找
    # connector==AscendStoreConnector 的 backend_scheme;命中且 memory_on → 用它(走 _render_kv_store_scheme),
    # 否则回落 cpu/disk/cpu_disk 三选一。与 disk 的组合由 YAML scheme 负责(框架不合并)。不再有 KV_STORE_BACKEND env。
    backend_scheme = _find_backend_scheme(block)

    memory_on = bool(cfg.memory_offload_enabled)
    disk_on = bool(cfg.disk_offload_enabled)
    if not memory_on and not disk_on:
        return None

    # backend scheme 命中 + memory_on → 内存方法用 backend scheme;disk 若也开,其配置由 YAML scheme 负责。
    if memory_on and backend_scheme is not None:
        if disk_on:
            logger.info(
                "kv_offload: backend scheme %r 命中且 disk_offload 也开;disk 部分由 YAML scheme 负责(框架不合并)",
                backend_scheme.get("name"),
            )
        return _render_kv_store_scheme(backend_scheme, cfg, ctx)

    # 三选一
    if memory_on and disk_on:
        target = "cpu_disk"
    elif disk_on:
        target = "disk"
    else:
        target = "cpu"

    # fallback:cpu_disk 缺 → disk > cpu > None;cpu/disk 缺 → None
    if target not in schemes:
        if target == "cpu_disk" and ("disk" in schemes or "cpu" in schemes):
            target = "disk" if "disk" in schemes else "cpu"
            logger.warning(
                "kv_offload: cpu_disk scheme 缺失,退化到 %r(yaml 需显式声明 cpu_disk 才能用组合)",
                target,
            )
        else:
            logger.warning("kv_offload: 目标 scheme %r 缺失,关闭 KV 卸载", target)
            return None

    selected = schemes[target]

    # 渲染选中 scheme 的 cli_params / envs(单 scheme,无需合并);envs 拷贝避免污染 yaml dict
    cli_params: Dict[str, Any] = selected.get("cli_params") or {}
    envs: Dict[str, Any] = dict(selected.get("envs") or {})
    packages: List[str] = extract_packages(selected)

    # disk/cpu_disk(lmcache)命中:scheme 的 files: 块统一落盘(lmcache_config.yaml 等),
    # 并注入派生 env LMCACHE_QAT_ENABLED(随 qat 开关;仅 vllm 视为 effective-on)。
    # LMCACHE_CONFIG_FILE 等指向文件的 env 由 scheme 的 envs: 字面量声明,不再代码注入。
    if target in ("disk", "cpu_disk"):
        files = selected.get("files") or []
        if files:
            effective_qat = bool(cfg.qat_enabled) and (engine_name or "").lower() == "vllm"
            render_ctx = replace(ctx, qat_enabled=effective_qat)
            write_scheme_files(files, render_ctx)
            envs["LMCACHE_QAT_ENABLED"] = "True" if effective_qat else "False"
        else:
            logger.warning(
                "kv_offload: disk 命中但 scheme 缺 files 块;跳过配置文件落盘"
                "(LMCACHE_QAT_ENABLED 不注入,容量参数可能不被 lmcache 识别)。"
            )

    engine_params = EngineParams(
        env=fill_envs(envs, ctx),
        engine_config=render_engine_config(cli_params, ctx),
    )
    return _FeatureOutput(
        scheme=str(selected.get("name", "")),
        engine_params=engine_params,
        packages=packages,
    )


def _synthesize_file_pre_serve(
    file_infos: List[Dict[str, Any]],
) -> tuple:
    """扫描 write_scheme_files 返回的文件信息,合成 pre_serve / pre_serve_master / pre_serve_client 命令。

    files 自描述 → 框架自动生成运行时步骤(资产作者无需写 shell):
    - mkdir:每个文件父目录(放 pre_serve,所有节点含 master;去重保序)。
    - envsubst:写盘内容含 runtime_vars(``${VAR}``)→ ``export VAR="${VAR:-127.0.0.1}"`` 设默认 +
      ``envsubst '<vars>' < path > path.tmp && mv`` 原地展开。按 ``scope`` 分流:
      all → pre_serve(所有节点);master → pre_serve_master(仅 master);
      client → pre_serve_client(仅 client/非 master 节点)。
    - daemon:名为 ``_KV_DAEMON_SCRIPT``(``start_kv_serve.sh``)的脚本 → ``bash <path> &``
      (仅 master 后台执行;**不监听端口**)。

    Args:
        file_infos: write_scheme_files 返回的 ``[{path, scope, mode, runtime_vars}]``。

    Returns:
        (pre_serve, pre_serve_master, pre_serve_client) 命令列表。
    """
    pre_serve: List[str] = []
    pre_serve_master: List[str] = []
    pre_serve_client: List[str] = []
    made_dirs: set = set()
    for fi in file_infos:
        path = fi["path"]
        scope = fi.get("scope") or "all"
        parent = str(Path(path).parent)
        if parent and parent not in made_dirs:
            pre_serve.append(f"mkdir -p {parent}")
            made_dirs.add(parent)
        # envsubst:runtime 变量(${RANK_IP}/${MASTER_IP})原地展开,按 scope 分流到 all/master/client 桶
        runtime_vars = fi.get("runtime_vars") or []
        if runtime_vars:
            exports = " ".join(f'{v}="${{{v}:-127.0.0.1}}"' for v in runtime_vars)
            var_list = " ".join(f"${{{v}}}" for v in runtime_vars)
            tmp = f"{path}.tmp"
            cmds = [
                f"export {exports}",
                f"envsubst '{var_list}' < {path} > {tmp} && mv {tmp} {path}",
            ]
            {"all": pre_serve, "master": pre_serve_master, "client": pre_serve_client}.get(
                scope, pre_serve
            ).extend(cmds)
        # daemon:名为 _KV_DAEMON_SCRIPT 的脚本,仅 master 后台执行(不监听端口)。
        if Path(path).name == _KV_DAEMON_SCRIPT:
            pre_serve_master.append(f"bash {path} &")
    return pre_serve, pre_serve_master, pre_serve_client


def _render_kv_store_scheme(
    scheme: Dict[str, Any],
    cfg: SmartKVCacheConfig,
    ctx: PlaceholderContext,
) -> _FeatureOutput:
    """渲染内存卸载 backend scheme(cpu 介质下的 mooncake/memcache 工具)—— files 自描述 + 框架自动生成 pre_serve。

    backend 是 cpu 介质下的工具选择(scheme 的 name=cpu,工具由 connector+backend 区分);
    选中后直接渲染该 scheme。与 disk 的组合(如 cpu_disk 形态)由 YAML scheme 自身负责连接器细节,框架不合并、不拦截。
    - files: 自描述条目(path/src/scope/mode)→ write_scheme_files 落盘 + 返回运行时信息;
      本函数据之合成 mkdir/envsubst/daemon(资产作者不在 YAML 写 shell)。daemon 脚本统一名
      start_kv_serve.sh,仅 master ``bash <path> &``(不监听端口)。
    - 显式 pre_serve/pre_serve_master/pre_serve_client 作逃生口,追加在自动生成之后(特殊步骤)。
    """
    cli_params: Dict[str, Any] = scheme.get("cli_params") or {}
    envs: Dict[str, Any] = dict(scheme.get("envs") or {})
    packages: List[str] = extract_packages(scheme)
    # 配置文件/脚本落盘 + 收集运行时信息(runtime_vars/scope)
    file_infos = write_scheme_files(scheme.get("files") or [], ctx)
    # 框架自动合成 pre_serve(mkdir/envsubst 按 scope 分流;daemon 仅 master bash &,不监听端口)
    pre_serve, pre_serve_master, pre_serve_client = _synthesize_file_pre_serve(file_infos)
    # 逃生口:YAML 显式 pre_serve 追加(向后兼容)
    pre_serve.extend(render_pre_serve(scheme.get("pre_serve"), ctx))
    pre_serve_master.extend(render_pre_serve(scheme.get("pre_serve_master"), ctx))
    pre_serve_client.extend(render_pre_serve(scheme.get("pre_serve_client"), ctx))
    return _FeatureOutput(
        scheme=str(scheme.get("name", "")),
        engine_params=EngineParams(
            env=fill_envs(envs, ctx),
            engine_config=render_engine_config(cli_params, ctx),
        ),
        packages=packages,
        pre_serve=pre_serve,
        pre_serve_master=pre_serve_master,
        pre_serve_client=pre_serve_client,
    )
