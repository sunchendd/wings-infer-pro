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
- cpu = vllm 原生 OffloadingConnector(无 lmcache 包 / 无配置文件计划)。
- disk / cpu_disk = lmcache(LMCacheConnectorV1):需 lmcache 包 + lmcache_config.yaml
  (yaml 为容量真相源;env/cli 为补充)。cpu_disk 比 disk 多 local_cpu:true + max_local_cpu_size。
- 容量类占位符({mem_gb_to_blocks} 等)由 PlaceholderContext 解析;容量值由 yaml_loader 决定。
- 配置文件计划:disk/cpu_disk 命中且有 files: 块时,由通用 render.plan_scheme_files
    渲染(占位符 {qat_*} 经 ctx 填充;qat_enabled 用 effective = vllm 且 cfg.qat_enabled)并交由
    wings-control 在产物阶段写入。指向文件的 env(如 LMCACHE_CONFIG_FILE)由 scheme 的 envs: 字面量
  声明,不再代码注入。LMCACHE_QAT_ENABLED 是派生 env(随 qat 开关,仅 vllm effective-on),
  仍代码注入。非 disk 命中 / 无 files 块 → 跳过(仅 WARN,不阻塞启动)。

方案结构:
    - name:       介质 cpu / disk / cpu_disk(后端工具 mooncake/memcache 也用 cpu,由 connector 区分)
    - packages:   pip 依赖(name:version);disk/cpu_disk 带 lmcache:v0.3.15
    - cli_params: 任意键值对(典型 kv_transfer_config: {...}),由 render 渲染
    - envs:       环境变量(支持 {memory_capacity_gb} / {mem_gb_to_blocks} 等占位符);
                  指向计划文件的 env(如 LMCACHE_CONFIG_FILE)在此字面量声明
    - files:      待生成的配置文件列表([{name, content}],通用语法;disk/cpu_disk 放 lmcache_config.yaml)
"""

import logging
import shlex
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_accel.render import (
    PlaceholderContext,
    extract_package_requirements,
    fill_envs,
    plan_scheme_files,
    render_engine_config,
)
from wings_accel.schemas import (
    EngineParams,
    GeneratedFile,
    SmartAccelConfigurationError,
    SmartKVCacheConfig,
    _FeatureOutput,
)

logger = logging.getLogger(__name__)

# KV 存储后端 daemon 脚本名(mooncake/memcache/lmcache_mp 统一):仅 master 执行
# ``bash <path> &``。脚本内容和交付文件计划仍由 scheme 的 ``files:`` 声明(内联 content);框架只硬编码
# 「master 跑这个脚本」一条,不识别后端、不监听端口(避免 vllm 抢跑靠部署侧重试/保证)。
_KV_DAEMON_SCRIPT = "start_kv_serve.sh"


def _scheme_has_daemon(scheme: Dict[str, Any]) -> bool:
    """判断 scheme 是否声明了 daemon 脚本(``files`` 含名为 ``_KV_DAEMON_SCRIPT`` 的条目)。

    有 daemon → 该 scheme 是「独立 server」形态(mooncake/memcache/lmcache_mp),需要起卸载服务,
    走 ``_render_kv_store_scheme``(backend 路径,合成 daemon pre_serve)。
    无 daemon → 走 cpu/disk/cpu_disk 三选一(原生 OffloadingConnector / lmcache disk/cpu_disk /
    lmcache-ascend 内嵌 connector 等,纯 cli_params + envs 渲染,不起服务)。

    设计(2026-08-06):**完全形态驱动,无 connector 白名单/黑名单**。判定信号 = scheme 的 files 里
    有没有 daemon 脚本,与 connector 名字、name 取值无关。加新 backend connector(未来的 XXXConnector)
    只要在 yaml 的 files 里声明 ``start_kv_serve.sh`` 即被识别为 backend,**无需改代码**;纯内嵌的新
    connector(不起服务)不写 daemon 脚本,自动走三选一,也无需改代码。
    """
    files = scheme.get("files") or []
    if not isinstance(files, list):
        return False
    for f in files:
        if not isinstance(f, dict):
            continue
        path = f.get("path") or f.get("name") or ""
        if Path(path).name == _KV_DAEMON_SCRIPT:
            return True
    return False


def _find_backend_scheme(block: List[Any]) -> Optional[Dict[str, Any]]:
    """在 kv_offload block 中找后端 scheme(声明了 daemon 脚本 ``start_kv_serve.sh`` 的 scheme)。

    后端 scheme = 有 daemon 脚本的 scheme → 走 ``_render_kv_store_scheme``(合成 daemon pre_serve +
    生成配置文件计划)。涵盖当前所有「独立 server」backend:AscendStoreConnector(mooncake/memcache)、
    LMCacheMPConnector(lmcache MP 分离部署),以及未来任何声明了 daemon 脚本的新 connector。

    无 daemon 的 scheme(原生 OffloadingConnector / lmcache disk/cpu_disk / lmcache-ascend 内嵌
    connector 等)不走 backend,落回 cpu/disk/cpu_disk 三选一。

    一份 yaml 至多声明一个后端 scheme;命中多个取首个。
    """
    for s in block or []:
        if not isinstance(s, dict):
            continue
        if _scheme_has_daemon(s):
            return s
    return None



def _scheme_source_path(
    block: Any,
    selected: Dict[str, Any],
    ctx: PlaceholderContext,
) -> str:
    """Return the original YAML path of the selected kv_offload scheme."""
    if not ctx.source_path:
        return ""
    if isinstance(block, list):
        for index, candidate in enumerate(block):
            if candidate is selected:
                return f"{ctx.source_path}.kv_offload[{index}]"
    return f"{ctx.source_path}.kv_offload"


def _reject_explicit_pre_serve(
    scheme: Dict[str, Any],
    ctx: PlaceholderContext,
    source_path: str,
) -> None:
    """拒绝 YAML 直接提供的启动前 Shell 命令。

    Args:
        scheme: 当前选中的 KV offload scheme。
        ctx: 占位符上下文，提供来源文件。
        source_path: 当前 scheme 的 YAML 路径。

    Raises:
        SmartAccelConfigurationError: scheme 声明任一 raw pre-serve 字段时抛出。
    """
    for key in ("pre_serve", "pre_serve_master", "pre_serve_client"):
        if key in scheme:
            file_name = ctx.source_file or "<unknown>"
            field_path = f"{source_path}.{key}" if source_path else key
            raise SmartAccelConfigurationError(
                f"Unsupported SmartAccel field '{key}' at {file_name}:{field_path}; "
                "use structured files instead"
            )


def smart_kv_offload_expander(
    cfg: SmartKVCacheConfig,
    block: Any,
    ctx: PlaceholderContext,
    engine_name: str = "vllm",
    topology: Optional[str] = None,
) -> Optional[_FeatureOutput]:
    """智能 KV 卸载方案选择与渲染。

    KV 存储后端(memcache/mooncake)是 **cpu 介质**下的内存卸载工具实现(scheme 的 name 仍为 cpu,
    非 cpu/disk 之外的第四类介质)。命中 backend scheme(connector==AscendStoreConnector)→ 内存方法
    走 ``_render_kv_store_scheme``,backend 命中即蕴含 memory_on;否则回落下面的 cpu/disk/cpu_disk 三选一。

    选择(由 cfg.memory_offload_enabled / disk_offload_enabled 组合):
      (mem, disk) = (T,F) → cpu;(F,T) → disk;(T,T) → cpu_disk;(F,F) → None。
    fallback:目标 scheme 缺失时,cpu_disk 缺 → 退化 disk > cpu > None;cpu/disk 缺 → None。

    cpu = vllm 原生 OffloadingConnector(无 lmcache 包 / 无配置文件计划)。
    disk / cpu_disk = lmcache(LMCacheConnectorV1):需 lmcache 包 + lmcache_config.yaml
    (yaml 为容量真相源;env/cli 为补充)。cpu_disk 比 disk 多 local_cpu:true + max_local_cpu_size。
    QAT 正交:disk/cpu_disk 命中且有 files: 块 → 通用 plan_scheme_files 生成文件计划(如
    lmcache_config.yaml)+ 注入派生 env LMCACHE_QAT_ENABLED(随 qat 开关,effective = vllm 且
    cfg.qat_enabled);指向文件的 env(如 LMCACHE_CONFIG_FILE)由 scheme 的 envs: 声明。

    scenario 隔离由 yaml_loader 完成(按 topology 路由出对应 scenario 子块),本函数只消费扁平
    kv_offload 列表,不感知 topology。PD 场景下 P/D 节点路由到的子块不含 kv_offload 键 →
    expander 拿到 None → 不产出(PD 的 KV 流转由 config 侧 ``kv_transfer_config`` 的
    kv_producer/kv_consumer 独立处理,与 smart-accel 的 kv_offload 正交)。``topology`` 参数仅作
    向后兼容保留(旧调用约定),不再参与过滤。

    Args:
        cfg: KV cache 配置(memory_offload_enabled / disk_offload_enabled / qat_*)。
        block: kv_offload scheme 列表(cpu/disk/cpu_disk 各最多一项;已路由到当前 scenario 子块)。
        ctx: 占位符上下文。
        engine_name: 引擎名;仅 vllm 启用 QAT。
        topology: **已废弃**(scenario 路由在 loader 完成);保留参数向后兼容。

    Returns:
        _FeatureOutput(选中 scheme + 渲染后 EngineParams + packages);无可选 → None。
    """
    # 主开关关 / 未配置 / 非 list → None(scenario 子块缺 kv_offload 键时也走这条)
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
                "kv_offload: backend scheme %r selected while disk offload is also enabled; "
                "the YAML scheme defines the disk portion.",
                backend_scheme.get("name"),
            )
        source_path = _scheme_source_path(block, backend_scheme, ctx)
        _reject_explicit_pre_serve(backend_scheme, ctx, source_path)
        return _render_kv_store_scheme(
            backend_scheme,
            cfg,
            ctx,
            source_path_prefix=source_path,
        )

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
                "kv_offload: cpu_disk scheme is missing; falling back to %r "
                "(YAML must explicitly declare cpu_disk for the combined mode)",
                target,
            )
        else:
            logger.warning("kv_offload: requested scheme %r is missing; disabling KV offload", target)
            return None

    selected = schemes[target]
    selected_source_path = _scheme_source_path(block, selected, ctx)
    _reject_explicit_pre_serve(selected, ctx, selected_source_path)

    # 渲染选中 scheme 的 cli_params / envs(单 scheme,无需合并);envs 拷贝避免污染 yaml dict
    cli_params: Dict[str, Any] = selected.get("cli_params") or {}
    envs: Dict[str, Any] = dict(selected.get("envs") or {})
    packages = extract_package_requirements(selected)
    generated_files: List[GeneratedFile] = []

    # disk/cpu_disk(lmcache)命中:scheme 的 files: 块统一生成计划(lmcache_config.yaml 等),
    # 并注入派生 env LMCACHE_QAT_ENABLED(随 qat 开关;仅 vllm 视为 effective-on)。
    # LMCACHE_CONFIG_FILE 等指向文件的 env 由 scheme 的 envs: 字面量声明,不再代码注入。
    if target in ("disk", "cpu_disk"):
        files = selected.get("files") or []
        if files:
            effective_qat = bool(cfg.qat_enabled) and (engine_name or "").lower() == "vllm"
            render_ctx = replace(ctx, qat_enabled=effective_qat)
            generated_files = plan_scheme_files(
                files,
                render_ctx,
                source_path_prefix=selected_source_path,
            )
            envs["LMCACHE_QAT_ENABLED"] = "True" if effective_qat else "False"
        else:
            logger.warning(
                "kv_offload: disk scheme has no files block; skipping generated file plan "
                "and LMCACHE_QAT_ENABLED injection; LMCache capacity settings may not take effect."
            )

    engine_params = EngineParams(
        env=fill_envs(envs, ctx),
        engine_config=render_engine_config(cli_params, ctx),
    )
    return _FeatureOutput(
        scheme=str(selected.get("name", "")),
        engine_params=engine_params,
        packages=packages,
        generated_files=generated_files,
    )


def _synthesize_file_pre_serve(
    file_infos: List[GeneratedFile],
) -> tuple:
    """扫描文件计划,合成 pre_serve / pre_serve_master / pre_serve_client 命令。

    files 自描述 → 框架自动生成运行时步骤(资产作者无需写 shell):
    - mkdir:每个文件父目录(放 pre_serve,所有节点含 master;去重保序)。
    - envsubst:计划文件内容含 runtime_vars(``${VAR}``)→ ``export VAR="${VAR:-127.0.0.1}"`` 设默认 +
      优先 ``envsubst`` 原地展开;容器缺 gettext(envsubst 不存在)时用 ``sed`` 兜底
      (避免空 .tmp 覆盖原文件 + 占位符残留)。按 ``scope`` 分流:
      all → pre_serve(所有节点);master → pre_serve_master(仅 master);
      client → pre_serve_client(仅 client/非 master 节点)。
    - daemon:名为 ``_KV_DAEMON_SCRIPT``(``start_kv_serve.sh``)的脚本 → ``bash <path> &``
      (仅 master 后台执行;**不监听端口**)。

    Args:
        file_infos: plan_scheme_files 返回的 ``GeneratedFile`` 列表。

    Returns:
        (pre_serve, pre_serve_master, pre_serve_client) 命令列表。
    """
    pre_serve: List[str] = []
    pre_serve_master: List[str] = []
    pre_serve_client: List[str] = []
    made_dirs: set = set()
    for fi in file_infos:
        path = fi.path
        scope = fi.scope or "all"
        parent = str(Path(path).parent)
        if parent and parent not in made_dirs:
            pre_serve.append(f"mkdir -p {shlex.quote(parent)}")
            made_dirs.add(parent)
        # envsubst:runtime 变量(${RANK_IP}/${MASTER_IP})原地展开,按 scope 分流到 all/master/client 桶。
        # 优先 envsubst;容器缺 gettext(envsubst 不存在)时用 sed 兜底,避免 .tmp 空文件覆盖原文件
        # (真实环境反馈:容器无 envsubst → envsubst 重定向产生空 .tmp → mv 后 conf 被清空,
        #  且 ${MASTER_IP} 占位符残留未展开)。sed fallback 无外部依赖,把已 export 的变量值
        # 注入替换串(双引号 shell 展开)。
        runtime_vars = fi.runtime_vars or []
        if runtime_vars:
            quoted_path = shlex.quote(path)
            quoted_tmp_path = shlex.quote(f"{path}.tmp")
            exports = " ".join(f'{v}="${{{v}:-127.0.0.1}}"' for v in runtime_vars)
            var_list = " ".join(f"${{{v}}}" for v in runtime_vars)
            # sed 兜底:逐变量 sed "s|\${VAR}|$VAR|g"(双引号 → $VAR 由 shell 展开为已 export 的值)。
            # 用 | 分隔避免路径 / 干扰;${VAR} 的 $ 需转义为 \$ 防止 shell 把 ${VAR} 当展开。
            sed_chain = ";".join(f's|\\${{{v}}}|${v}|g' for v in runtime_vars)
            cmds = [
                f"export {exports}",
                # 优先 envsubst;命令不存在或非零退出 → sed 兜底;结果都写 .tmp 再 mv
                f"if command -v envsubst >/dev/null 2>&1 && envsubst '{var_list}' < {quoted_path} "
                f"> {quoted_tmp_path} 2>/dev/null; then :; "
                f"else sed \"{sed_chain}\" {quoted_path} > {quoted_tmp_path}; fi",
                f"mv {quoted_tmp_path} {quoted_path}",
            ]
            {"all": pre_serve, "master": pre_serve_master, "client": pre_serve_client}.get(
                scope, pre_serve
            ).extend(cmds)
        # daemon:名为 _KV_DAEMON_SCRIPT 的脚本,仅 master 后台执行(不监听端口)。
        if Path(path).name == _KV_DAEMON_SCRIPT:
            pre_serve_master.append(f"bash {shlex.quote(path)} &")
    return pre_serve, pre_serve_master, pre_serve_client


def _render_kv_store_scheme(
    scheme: Dict[str, Any],
    cfg: SmartKVCacheConfig,
    ctx: PlaceholderContext,
    source_path_prefix: str = "",
) -> _FeatureOutput:
    """渲染内存卸载 backend scheme(cpu 介质下的 mooncake/memcache 工具)—— files 自描述 + 框架自动生成 pre_serve。

    backend 是 cpu 介质下的工具选择(scheme 的 name=cpu,工具由 connector+backend 区分);
    选中后直接渲染该 scheme。与 disk 的组合(如 cpu_disk 形态)由 YAML scheme 自身负责连接器细节,框架不合并、不拦截。
    - files: 自描述条目(path/src/scope/mode)→ plan_scheme_files 生成文件计划 + 返回运行时信息;
      本函数据之合成 mkdir/envsubst/daemon(资产作者不在 YAML 写 shell)。daemon 脚本统一名
      start_kv_serve.sh,仅 master ``bash <path> &``(不监听端口)。
    - YAML 不允许显式 pre_serve/pre_serve_master/pre_serve_client；启动前命令只能由 files 自动合成。
    """
    cli_params: Dict[str, Any] = scheme.get("cli_params") or {}
    envs: Dict[str, Any] = dict(scheme.get("envs") or {})
    packages = extract_package_requirements(scheme)
    # Build file plans and collect runtime metadata without writing to the filesystem.
    file_infos = plan_scheme_files(
        scheme.get("files") or [],
        ctx,
        source_path_prefix=source_path_prefix,
    )
    # 框架自动合成 pre_serve(mkdir/envsubst 按 scope 分流;daemon 仅 master bash &,不监听端口)
    pre_serve, pre_serve_master, pre_serve_client = _synthesize_file_pre_serve(file_infos)
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
        generated_files=file_infos,
    )
