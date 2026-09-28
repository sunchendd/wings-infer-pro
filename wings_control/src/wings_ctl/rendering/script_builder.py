"""ScriptBuilder — 从 ResolvedConfig 产出 start_command.sh 和 repro.sh。

输入: ResolvedConfig, output_dir (Path)
输出: 写入 start_command.sh + repro.sh 到 output_dir

区别:
- start_command.sh: 本次实际执行脚本,简洁。
- repro.sh: 可移植复现脚本,包含完整 env 设置 + 每个引擎参数的来源注释(取自 trace)。

⚠️ env 渲染与 system_setup 渲染为安全敏感代码,需人工 review。
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wings_ctl.accel.smart_accel import AccelResult, GeneratedFileSpec
from wings_ctl.common.settings import settings
from wings_ctl.core.models import EngineProcessPlan, ResolvedConfig, SystemSetup, TracedValue
from wings_ctl.core.system_setup import render_source_command_blocks
from wings_ctl.core.topology import Topology
from wings_ctl.engines.registry import build_launch_plan
from wings_ctl.engines.vllm_adapter import (
    MODEL_KEYS,
    build_argv,
    build_command_head,
    build_system_setup_source_commands,
    render_param_tokens,
    resolve_model_traced,
)
from wings_ctl.rendering.env_renderer import render_env_export
from wings_ctl.utils.env_utils import is_mooncake_master_pod

logger = logging.getLogger(__name__)


def _render_env_section(env_traces: Dict[str, TracedValue]) -> List[str]:
    """渲染 env export 段。

    逐项读 ``TracedValue.allow_unsafe``:config_file env 层(allow_unsafe=True)跳过
    _validate_dollar_value 安全校验,双引号放行 ``$(hostname)`` 等命令替换
    (用户对自己的输入负责,见 resolve_custom_config)。
    """
    lines: List[str] = []
    for env_key, traced in env_traces.items():
        if traced.final_value is not None:
            lines.append(
                render_env_export(env_key, traced.final_value, allow_unsafe=traced.allow_unsafe)
            )
    return lines


def _render_system_setup_comments(
    system_setup: Optional[SystemSetup],
    rendered_source_commands: Optional[List[str]] = None,
) -> List[str]:
    """渲染 system_setup 为注释形式(不生成可执行行)。

    安全敏感:特权 sysctls / sysfs_writes **恒注释**(维持单机「注释不执行」
    安全立场,留运维/容器 init)。只有引擎启动计划已明确给出的 source 初始化命令
    会在 engine argv 前执行，其余 commands 仍只保留为注释信息。

    Args:
        system_setup: 系统级设置(None 返回空)。
        rendered_source_commands: 已由引擎命令规格校验、将要执行的 source 命令。
    """
    if system_setup is None:
        return []
    lines: List[str] = []

    has_any = system_setup.sysctls or system_setup.sysfs_writes or system_setup.commands
    if has_any:
        lines.append(f"# ─── System Setup (source: {system_setup.source_file} @ {system_setup.source_path}) ───")

    if system_setup.sysctls:
        lines.append("# sysctls:")
        for key, value in system_setup.sysctls.items():
            lines.append(f"#   sysctl -w {key}={value}")

    if system_setup.sysfs_writes:
        lines.append("# sysfs_writes:")
        for entry in system_setup.sysfs_writes:
            path = entry.get("path", "")
            value = entry.get("value", "")
            lines.append(f"#   echo {value!r} > {path}")

    if system_setup.commands:
        rendered_count = len(rendered_source_commands or [])
        not_rendered_count = len(system_setup.commands) - rendered_count
        if rendered_count:
            lines.append(
                "# commands "
                f"({rendered_count} source entries rendered before engine; "
                f"{not_rendered_count} entries not rendered)"
            )
        else:
            lines.append(f"# commands ({len(system_setup.commands)} entries, not rendered)")

    if lines:
        lines.append("")

    return lines


def _render_system_setup_source_section(source_commands: Optional[List[str]]) -> List[str]:
    """渲染已校验的 source 环境初始化命令段（带 nounset 关闭 + ``-f`` 守卫）。

    见 ``render_source_command_blocks``：避免厂商 set_env.sh 因未定义变量
    （如 ``ZSH_VERSION``）或路径缺失而中断整个启动脚本。
    """
    if not source_commands:
        return []
    return [
        "# ─── System Setup source commands ───",
        *render_source_command_blocks(source_commands),
        "",
    ]


def _render_accel_install_preamble(engine: str, engine_version: str, packages: List[str]) -> List[str]:
    """渲染 wings-accel runtime patch 安装段(``--config`` JSON 形式)。

    2026-07-06 更新:从 3 个位置参数改为 ``--config '{json}'``;JSON 含
    ``engine{name,version}`` + ``packages``(各选中 scheme 声明的 pip 依赖,name:version 字符串)。
    ``hardware_family`` 不再传入(新契约;若 install.py 仍需,加 ``"hardware"`` 字段即可)。

    ⚠️ 安全敏感:本行 exec,**改命令形态须 A5 人工 review**(对齐 §2.8 / docs/45 §5.3)。
    JSON 用 ``json.dumps`` 生成(无单引号)再 ``shlex.quote`` 整体包住,杜绝注入。

    Args:
        engine: 引擎名(如 ``vllm``)。
        engine_version: 引擎版本(可带或不带 ``v`` 前缀;此处统一补 ``v`` 前缀)。
        packages: 选中 scheme 声明的依赖包列表(``name:version`` 字符串);空 → ``"packages": []``。

    Returns:
        单行 install 命令(JSON 已 ``shlex.quote``)+ 收尾空行。
    """
    version = engine_version if not engine_version or engine_version.startswith("v") else f"v{engine_version}"
    config = {
        "engine": {"name": engine, "version": version},
        "packages": list(packages),
    }
    config_json = json.dumps(config)
    return [
        f"python3 /accel-volume/install.py --config {shlex.quote(config_json)}",
        "",
    ]


def _validate_accel_packages(packages: List[str]) -> None:
    """生成期预检:请求的每个 accel 包必须存在于 wings-accel 工件中。

    install.py 按 manifest 键**精确匹配**(键 = packages/<name>/<version> 目录名),
    缺包会在运行期 exit 1 → start_command.sh set -e → 容器 CrashLoopBackOff。
    本函数把该失败提前到脚本生成期:镜像与代码版本漂移时,启动瞬间报可操作的
    错误而非反复崩溃。与 wings_accel.distributed_offload 共用 ACCEL_VOLUME_PATH
    环境变量约定;目录不存在(测试/CI 无工件)时仅告警跳过,不阻断。

    Raises:
        ValueError: 工件存在但请求的 name:version 目录缺失。
    """
    volume = Path(os.environ.get("ACCEL_VOLUME_PATH", "/accel-volume"))
    packages_root = volume / "packages"
    if not packages_root.is_dir():
        logger.warning(
            "wings-accel artifact packages directory not found (%s); skip install preflight",
            packages_root,
        )
        return
    for item in packages:
        name, _, version = item.partition(":")
        if not (packages_root / name / version).is_dir():
            raise ValueError(
                f"wings-accel artifact does not contain package {item!r} "
                f"(expected directory {packages_root / name / version}); rebuild the "
                f"wings-accel image or pin an available version in the smart-accel YAML"
            )


def _write_advanced_features_json(resolved: ResolvedConfig) -> None:
    """写 advanced_features.json(加速特性使能状态,页面回显的单一真相源)。

    对齐老仓库 wings_entry._write_advanced_features_json:在脚本生成阶段写入共享卷,
    health 接口 ``/v1/startup/accel``(读 ``settings.ADVANCED_FEATURES_FILE``)透出给页面。
    字段语义(接口文档):
      - features:各特性最终使能布尔(页面开关唯一回显依据);
      - features.kv_distributed_offload:分布式 KV 卸载(Mooncake)显式生效标志
        (与 MaaS 前端约定的消费字段;kv_offload 是本地/分布式合一口径,二者可同时
        为 true 仅当分布式生效);
      - variants:实际策略字符串(features[x]=false 时为 null,仅诊断用);
      - others.kv_mem_offload_size:智能推荐容量(auto 估算的最终推荐值,GB;0=低于下限,
        null=无有效容量),来自 ``accel.kv_mem_offload_size_gb``;
      - others.speculative_decode:投机推理详情(method/num_speculative_tokens 等),未产出 → null。
    写失败只 WARN 不抛(状态文件缺失时 health 接口按空对象兜底)。

    Args:
        resolved: 配置解析最终产物(``resolved.accel`` 承载 wings-accel 产出)。
    """
    accel = resolved.accel
    # features:有选中 scheme 即该特性最终生效(scheme 名即 variants 策略);
    # sparse_kv 只按 MaaS 开关开且 smart 命中 sparse scheme 回显(recipe 基线 fp8 不算)
    # kv_offload 含本地卸载与分布式(Mooncake)两形态:互斥,任一命中即回显生效。
    decoding_scheme = accel.audit.get("smart_decoding_scheme") if accel.audit else None
    sparse_scheme = accel.audit.get("smart_kv_sparse_scheme") if accel.audit else None
    offload_scheme = accel.audit.get("smart_kv_cache_scheme") if accel.audit else None
    distributed_scheme = (
        accel.audit.get("smart_distributed_kv_cache_scheme") if accel.audit else None
    )
    effective_offload = offload_scheme or distributed_scheme
    rag_acc_trace = resolved.env_traces.get("RAG_ACC_ENABLED")
    rag_acc_value = rag_acc_trace.final_value if rag_acc_trace is not None else None
    rag_acc_enabled = str(rag_acc_value or "").strip().lower() in {"1", "true", "yes", "on"}

    features = {
        "speculative_decode": bool(decoding_scheme),
        "sparse_kv": bool(sparse_scheme),
        "kv_offload": bool(effective_offload),
        # 分布式显式标志(MaaS 前端消费字段):仅分布式特性真产出时为 true;
        # 降级(auto 估算不足/YAML 未声明)/未开启/仅本地卸载 → false。
        "kv_distributed_offload": bool(distributed_scheme),
        "rag_acc": rag_acc_enabled,
    }
    variants = {
        "speculative_decode": decoding_scheme or None,
        "sparse_kv": sparse_scheme or None,
        "kv_offload": effective_offload or None,
        "kv_distributed_offload": distributed_scheme or None,
    }
    spec_details = None
    if decoding_scheme:
        spec_config = (
            resolved.engine_config_traces.get("speculative_config").final_value
            if "speculative_config" in resolved.engine_config_traces
            else None
        )
        if isinstance(spec_config, dict):
            spec_details = dict(spec_config)

    data = {
        "engine": resolved.engine,
        "features": features,
        "variants": variants,
        "others": {
            "kv_mem_offload_size": accel.kv_mem_offload_size_gb,
            "speculative_decode": spec_details,
        },
    }
    path = Path(settings.ADVANCED_FEATURES_FILE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        logger.info(
            "Wrote advanced_features.json: features=%s variants=%s others=%s",
            features, variants, data["others"],
        )
    except OSError as exc:
        logger.warning("Failed to write advanced_features.json: %s", exc)


def _write_accel_generated_files(generated_files: List[GeneratedFileSpec]) -> None:
    """在产物阶段原子写入 wings-accel 生成的文件计划。

    accel 解析阶段只计算、不落盘,落盘职责迁移到本产物阶段;dry-run 不经过
    build_scripts,故不会触发本函数,天然无副作用。

    安全边界:
      - 目标路径必须落在共享卷根内,拒绝 ``..`` / 绝对路径越界;越界 fail-fast(不静默)。
      - 原子写:同目录唯一临时文件 + ``Path.replace``;``mode`` 非空时对临时文件 chmod 后再替换。
      - 写入或设置权限失败时 fail-fast，避免引擎使用缺失或旧版本的配置文件启动。

    Args:
        generated_files: accel 产出的文件计划列表;空 → no-op。

    Raises:
        ValueError: 目标路径无法解析、越出共享卷根，或文件写入/权限设置失败。

    """
    if not generated_files:
        return
    shared_root = Path(settings.SHARED_VOLUME_PATH).resolve()
    for spec in generated_files:
        target = Path(spec.path)
        try:
            resolved_target = target.resolve(strict=False)
        except OSError as exc:
            raise ValueError(f"accel generated file path unresolvable: {spec.path!r}") from exc
        if not resolved_target.is_relative_to(shared_root):
            raise ValueError(
                f"accel generated file escapes shared volume "
                f"{settings.SHARED_VOLUME_PATH!r}: {spec.path!r}"
            )
        tmp_path: Path | None = None
        try:
            resolved_target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=resolved_target.parent,
                prefix=f".{resolved_target.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp.write(spec.content)
                tmp_path = Path(tmp.name)
            if spec.mode is not None:
                try:
                    tmp_path.chmod(int(str(spec.mode), 8))
                except (ValueError, OSError) as exc:
                    raise ValueError(
                        f"failed to set mode for accel generated file {spec.path!r}: "
                        f"{spec.mode!r}"
                    ) from exc
            tmp_path.replace(resolved_target)
            tmp_path = None
            logger.info("wrote accel generated file %s (mode=%s)", spec.path, spec.mode)
        except OSError as exc:
            raise ValueError(
                f"failed to write accel generated file {spec.path!r}: {exc}"
            ) from exc
        finally:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    logger.debug("failed to clean temporary accel generated file %s", tmp_path)


# Mooncake 脚本兜底资产的镜像内安装路径。构建期由 Dockerfile 在 compile_wings.sh
# 加密(.py → .pyc 并删除 .py)之前 COPY 到 /opt/mooncake_assets:mooncake_store.py
# 是 engine 容器的运行时资产(以 `python3 xxx.py` 方式执行),跨容器跑不了
# wings-control(Python 3.10)编译的 .pyc(bad magic number),必须保持 .py 交付。
# 与 log_analyzer 同模式(见 Dockerfile / wings_start.sh)。本地/测试可用
# MOONCAKE_ASSETS_PATH 覆盖,缺省回退仓库源目录(见 _resolve_mooncake_assets_dir)。
_MOONCAKE_ASSETS_PATH_ENV = "MOONCAKE_ASSETS_PATH"
_DEFAULT_MOONCAKE_ASSETS = "/opt/mooncake_assets"


def _resolve_mooncake_assets_dir() -> Path:
    """解析 Mooncake 脚本兜底资产源目录(镜像 /opt/mooncake_assets 优先)。

    优先级:``MOONCAKE_ASSETS_PATH`` env → 镜像默认 ``/opt/mooncake_assets`` →
    仓库内 ``src/wings_accel/distributed_offload/mooncake``(仅本地/测试回退,
    回退时打 WARN)。目录里只有 ``mooncake_store.pyc`` 没有 ``mooncake_store.py``
    说明镜像用旧 Dockerfile 构建(资产被加密步骤吃掉),fail-fast 阻止 .pyc 被
    静默拷到共享卷、把故障带到引擎启动期。

    Returns:
        资产源目录(存在性由调用方校验)。

    Raises:
        ValueError: 目录内只剩 .pyc 没有 .py(旧镜像/旧构建)时。
    """
    assets_dir = Path(
        os.environ.get(_MOONCAKE_ASSETS_PATH_ENV, _DEFAULT_MOONCAKE_ASSETS)
    )
    if not assets_dir.is_dir():
        repo_dir = (
            Path(__file__).resolve().parents[2]
            / "wings_accel"
            / "distributed_offload"
            / "mooncake"
        )
        if repo_dir.is_dir():
            logger.warning(
                "Mooncake assets directory %s not found; falling back to repo source "
                "%s (dev/test only; production image must ship %s)",
                assets_dir,
                repo_dir,
                _DEFAULT_MOONCAKE_ASSETS,
            )
            assets_dir = repo_dir
    if (assets_dir / "mooncake_store.pyc").is_file() and not (
        assets_dir / "mooncake_store.py"
    ).is_file():
        raise ValueError(
            "Mooncake assets contain mooncake_store.pyc but no mooncake_store.py: the "
            "image was built without copying assets to /opt/mooncake_assets before "
            "the compile step; rebuild the wings-control image"
        )
    return assets_dir


def _install_mooncake_script_assets() -> None:
    """原子复制随包的 Mooncake 脚本兜底资产到共享卷。

    资产源为镜像内未加密副本(/opt/mooncake_assets,见 _resolve_mooncake_assets_dir)。
    脚本兜底只能使用受控的常规文件；拒绝符号链接和超出目标目录的路径，
    避免共享卷复制成为任意文件写入入口。调用方只会在分布式 KV 开关已生效且
    至少一个部件选择脚本兜底时调用本函数。复制完成后渲染 client.env
    （env.yaml 默认值 + MaaS env 覆盖 → export 行）供 pre-serve 段 source。
    """
    source_dir = _resolve_mooncake_assets_dir()
    if not source_dir.is_dir():
        raise ValueError(f"Mooncake fallback asset directory is missing: {source_dir}")
    shared_root = Path(settings.SHARED_VOLUME_PATH).resolve()
    target_dir = shared_root / "mooncake"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"failed to create Mooncake fallback asset directory {target_dir}: {exc}") from exc

    for source in sorted(source_dir.rglob("*")):
        if source.is_symlink():
            raise ValueError(f"Mooncake fallback asset must not be a symlink: {source}")
        if source.is_dir():
            continue
        if not source.is_file():
            raise ValueError(f"Mooncake fallback asset is not a regular file: {source}")
        relative = source.relative_to(source_dir)
        target = target_dir / relative
        try:
            resolved_target = target.resolve(strict=False)
        except OSError as exc:
            raise ValueError(f"Mooncake fallback asset target is unresolvable: {target}") from exc
        if not resolved_target.is_relative_to(target_dir.resolve()):
            raise ValueError(f"Mooncake fallback asset escapes target directory: {relative}")
        tmp_path: Path | None = None
        try:
            resolved_target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=resolved_target.parent,
                prefix=f".{resolved_target.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copyfile(source, tmp_path)
            tmp_path.chmod(source.stat().st_mode & 0o777)
            tmp_path.replace(resolved_target)
            tmp_path = None
        except OSError as exc:
            raise ValueError(f"failed to install Mooncake fallback asset {relative}: {exc}") from exc
        finally:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    logger.debug("failed to clean temporary Mooncake fallback asset %s", tmp_path)
    logger.info("installed Mooncake script fallback assets in %s", target_dir)


def _render_mooncake_client_env(overrides: Optional[Dict[str, str]] = None) -> List[str]:
    """渲染 Mooncake client.env（env.yaml 默认值 + MaaS env 覆盖 → export 行）。

    env.yaml 是 Mooncake client 环境变量的唯一集中定义（带默认值）；MaaS 下发的
    同名变量**原样透传**（不派生中间名）：ENABLE_KV_OFFLOAD /
    ENABLE_DISTRIBUTED_KV_OFFLOAD / ENABLE_KV_DISK_OFFLOAD / ENABLE_KV_MEM_OFFLOAD /
    KV_DISK_OFFLOAD_PATH / KV_DISK_OFFLOAD_SIZE / KV_MEM_OFFLOAD_SIZE /
    KV_PROTOCOL / SERVING_CONFIG_ID 共 9 个。engine Pod 不在 wings-control
    进程内, 所以最终值必须渲染成 export 行落到 client.env,由 engine 侧
    source 加载。

    覆盖层级：env.yaml 默认 < MaaS 原始 env(os.environ) < ``overrides``(最高)。
    ``overrides`` 承载 wings-accel 解析后的最终值——KV_MEM_OFFLOAD_SIZE=auto
    智能推荐时,MaaS 原始 "auto" 字面量不能进 client.env(脚本侧校验纯数值),
    由调用方把估算值以 overrides 传入覆盖。

    Args:
        overrides: accel 解析值覆盖层(如 ``{"KV_MEM_OFFLOAD_SIZE": "171"}``);
            None/空 = 无覆盖,行为与历史一致。

    Returns:
        ``export KEY=value`` 行列表（经 render_env_export 安全转义）。

    Raises:
        ValueError: env.yaml 缺失或结构非法（fail-fast,不让 client 带空环境启动）。
    """
    env_yaml_path = _resolve_mooncake_assets_dir() / "env.yaml"
    try:
        import yaml

        raw = yaml.safe_load(env_yaml_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Mooncake env defaults missing: {env_yaml_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Mooncake env defaults is not valid YAML: {env_yaml_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Mooncake env defaults must be a mapping: {env_yaml_path}")

    defaults = {str(k): v for k, v in raw.items()}

    # MaaS 同名下发的变量原样覆盖默认值（strip 空白,空值不覆盖）。
    for name in defaults:
        value = os.environ.get(name)
        if value is not None and value.strip():
            defaults[name] = value.strip()

    # accel 解析值最终覆盖(如 auto 估算出的 KV_MEM_OFFLOAD_SIZE 数值)。
    for name, value in (overrides or {}).items():
        if value is not None and str(value).strip():
            defaults[name] = str(value).strip()

    return [
        render_env_export(key, value, allow_unsafe=False)
        for key, value in sorted(defaults.items())
    ]


def _write_mooncake_client_env(overrides: Optional[Dict[str, str]] = None) -> None:
    """把渲染好的 client.env 原子写入共享卷（export 行,engine 侧 source 用）。

    先于 pre-serve 段执行,保证 creat_mooncake_json.sh / start_mooncake_client.sh
    读到最终环境变量。``overrides`` 语义见 :func:`_render_mooncake_client_env`。
    写入失败 fail-fast(与脚本兜底资产安装同口径)。
    """
    shared_root = Path(settings.SHARED_VOLUME_PATH).resolve()
    target_dir = shared_root / "mooncake"
    target_dir.mkdir(parents=True, exist_ok=True)
    lines = _render_mooncake_client_env(overrides)
    content = "\n".join(["# Mooncake client environment (rendered from env.yaml + MaaS env + accel resolved)", *lines, ""])
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target_dir,
            prefix=".client.env.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(content)
        tmp_path.replace(target_dir / "client.env")
        tmp_path = None
        logger.info("wrote Mooncake client.env in %s", target_dir)
    except OSError as exc:
        raise ValueError(f"failed to write Mooncake client.env in {target_dir}: {exc}") from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                logger.debug("failed to clean temporary Mooncake client.env")


def _write_mooncake_master_env(overrides: Optional[Dict[str, str]] = None) -> None:
    """把渲染好的 master.env 原子写入共享卷(export 行,engine 侧 source 用)。

    与 client.env 同链路:env.yaml 默认值 + MaaS env 覆盖 + accel 解析值覆盖 → export 行。
    master 分支段(IS_MOONCAKE_MASTER)在 pre-serve 之前 source 本文件,保证
    start_mooncake_master.sh 读到最终值。写入失败 fail-fast(与 client.env 同口径)。
    """
    shared_root = Path(settings.SHARED_VOLUME_PATH).resolve()
    target_dir = shared_root / "mooncake"
    target_dir.mkdir(parents=True, exist_ok=True)
    lines = _render_mooncake_client_env(overrides)
    content = "\n".join(["# Mooncake master environment (rendered from env.yaml + MaaS env)", *lines, ""])
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target_dir,
            prefix=".master.env.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(content)
        tmp_path.replace(target_dir / "master.env")
        tmp_path = None
        logger.info("wrote Mooncake master.env in %s", target_dir)
    except OSError as exc:
        raise ValueError(f"failed to write Mooncake master.env in {target_dir}: {exc}") from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                logger.debug("failed to clean temporary Mooncake master.env")


def _render_kv_disk_cleanup_section(kv_disk_offload_path: Optional[str]) -> List[str]:
    """渲染 KV 磁盘卸载残留清理段(vllm serve 前)。

    背景:LMCache disk 卸载的数据落盘在 ``KV_DISK_OFFLOAD_PATH`` 下,推理服务
    重启后旧数据残留,与新一轮卸载数据叠加会超出 MaaS 规划的 KV_DISK_OFFLOAD_SIZE,
    同主机上可能与其它服务争抢资源。启动前清空卸载目录,保证本次服务占用与规划一致。

    清理目标为 ``KV_DISK_OFFLOAD_PATH`` 目录下的 ``*.pt`` 文件(卸载数据落盘形态,
    不追加子目录后缀);path 为 None(无磁盘卸载)→ 空列表(非 disk 路径零影响)。

    ⚠️ rm 属安全敏感命令:路径来自 MaaS ``KV_DISK_OFFLOAD_PATH``(accel 产出已解析,
    非用户 shell 输入),且 ``shlex.quote`` 整体转义,杜绝通配/注入;改动命令形态须人工 review。
    """
    if not kv_disk_offload_path:
        return []
    target = kv_disk_offload_path.rstrip("/")
    return [
        "# ── KV 磁盘卸载残留清理:服务重启后旧 KV 落数据会超出规划容量,启动前清空 ──",
        f"mkdir -p {shlex.quote(target)}",
        f"rm -f {shlex.quote(target)}/*.pt",
        "",
    ]


def _render_accel_pre_serve_section(
    pre_serve: Optional[List[str]],
    pre_serve_master: Optional[List[str]],
    pre_serve_client: Optional[List[str]] = None,
) -> List[str]:
    """渲染 KV 存储后端(memcache/mooncake)pre-serve 段。

    三段(对齐 start_kv_serve.sh:install.py → 起 KV 服务 → vllm serve):
    - ``pre_serve``:所有节点运行(典型:heredoc 生成 mooncake.json/mmc_*.conf,引用 $local_ip/$node0_ip);
    - ``pre_serve_master``:仅 master 节点起 daemon。包运行时条件
      ``RANK_IP == MASTER_IP`` 判 master;单机(``MASTER_IP`` 未设)条件恒真 → 起 daemon。
    - ``pre_serve_client``:仅 client 节点(非 master)。包运行时条件 ``RANK_IP != MASTER_IP``
      判 client;单机(``MASTER_IP`` 未设)条件恒假 → 不跑(单机即 master)。

    Args:
        pre_serve: 所有节点命令;空 → 不渲染该段。
        pre_serve_master: 仅 master 命令;空 → 不渲染该段(external 模式或无 daemon)。
        pre_serve_client: 仅 client 命令;空 → 不渲染该段。

    Returns:
        pre-serve 段脚本行;三段皆空 → 空列表(非 KV 后端路径零影响)。
    """
    lines: List[str] = []
    if pre_serve:
        lines.append("# ─── KV store pre-serve (all nodes) ───")
        lines.extend(pre_serve)
        lines.append("")
    if pre_serve_master:
        lines.append("# ─── KV store pre-serve (master only) ───")
        lines.append('if [ -z "${MASTER_IP:-}" ] || [ "${RANK_IP:-}" = "${MASTER_IP:-}" ]; then')
        lines.extend(f"    {cmd}" for cmd in pre_serve_master)
        lines.append("fi")
        lines.append("")
    if pre_serve_client:
        lines.append("# ─── KV store pre-serve (client only) ───")
        lines.append('if [ -n "${MASTER_IP:-}" ] && [ "${RANK_IP:-}" != "${MASTER_IP:-}" ]; then')
        lines.extend(f"    {cmd}" for cmd in pre_serve_client)
        lines.append("fi")
        lines.append("")
    return lines


def _is_mooncake_master_pod() -> bool:
    """判断当前 wings-control 是否运行在 Mooncake master 专属 Pod 上。

    委托 :func:`wings_ctl.utils.env_utils.is_mooncake_master_pod`(单一判定点,
    与 CLI 入口共用);真值集合与脚本内 shell 判定保持一致(TRUE/true/1/True)。
    该身份是**部署层事实**,与分布式 KV 卸载特性是否产出无关——据此决定 master
    分支段的存在性,防止特性降级时 master Pod 落到 vllm serve 路径。
    """
    return is_mooncake_master_pod()


def _render_mooncake_master_hold_section() -> List[str]:
    """合成 Mooncake master Pod 的挂起分支段(特性未生效时的兜底形态)。

    场景:Pod 被部署为 mooncake master(``IS_MOONCAKE_MASTER=true``),但分布式
    KV 卸载特性未生效(auto 估算不足被降级 / 开关未开 / 特性异常降级)。此时
    master.env 与 mooncake 脚本资产均未安装,但 **master Pod 绝不能回退执行
    vllm serve**(无 GPU、语义错误)——正确行为是打 ERROR 日志后挂起等待,
    Pod 保持 Running、不产任何服务;原因通过日志与 advanced_features.json 回显
    (kv_offload=false / kv_mem_offload_size=0)可查。

    段结构与 :func:`wings_accel.distributed_offload._render_mooncake_master_section`
    同构(同一 shell 判定、同一插入位置:install 段之后、pre-serve 之前)。
    ``while + sleep`` 而非 ``sleep infinity``:保持 POSIX 容器(base 镜像 busybox
    场景)可移植;SIGTERM 由 bash 默认终止行为处理,pod 删除正常退出。
    """
    return [
        "# ─── Mooncake master branch (IS_MOONCAKE_MASTER, hold) ───",
        "# master Pod:分布式 KV 卸载未生效(估算不足降级/开关未开),挂起等待;",
        "# 不拉起 mooncake_master(资产未安装),更不能回退执行 vllm serve。",
        'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ] || [ "${IS_MOONCAKE_MASTER:-}" = "true" ] || \\',
        '   [ "${IS_MOONCAKE_MASTER:-}" = "1" ] || [ "${IS_MOONCAKE_MASTER:-}" = "True" ]; then',
        '    _wings_log ERROR "mooncake master pod detected but distributed KV offload is NOT effective '
        '(degraded or disabled); holding without mooncake_master or vllm serve"',
        "    while true; do sleep 3600; done",
        "fi",
        "",
    ]


def _mooncake_kv_mem_env_overrides(accel: AccelResult) -> Optional[Dict[str, str]]:
    """KV_MEM_OFFLOAD_SIZE=auto 智能推荐的解析值覆盖(client.env / master.env 共用)。

    accel 已把估算值解析进 ``kv_mem_offload_size_gb``,以其覆盖 env 文件的原始
    "auto" 字面量(脚本只见数值)。本地/分布式互斥,mooncake 资产只在分布式产出
    时装载,不会误伤本地场景。主管线与 master 交付支线共用本助手,保证两处口径一致。
    """
    resolved_size = accel.kv_mem_offload_size_gb
    if resolved_size and resolved_size > 0:
        return {"KV_MEM_OFFLOAD_SIZE": str(resolved_size)}
    return None


def _deliver_mooncake_master_pod(
    resolved: ResolvedConfig,
    start_path: Path,
    repro_path: Path,
) -> Tuple[Path, Path]:
    """Mooncake master 专属 Pod 的交付支线(不渲染引擎生命周期)。

    master Pod 与 engine Pod 走同一 CLI → resolve → accel 决策链(pre_template 对
    master Pod 推导与 engine Pod 相同的 MULTI_NODE 拓扑值,scheme 匹配/auto 降级
    判定同源),本支线只接管**交付层**:

    - advanced_features.json / accel 文件计划 / mooncake 资产与 env 文件照常落盘
      (health 回显与 engine Pod 同源同值);
    - start_command.sh 含 install 段(**仅传输引擎包**)+ master 分支段(特性生效,
      拉起 mooncake_master 并等待)或挂起兜底段(特性未生效,ERROR + hold)。
      mooncake_master 二进制随 xcache 传输引擎包交付,install.py 以包内新版覆盖镜像
      预装的旧版(旧版缺新版 flag 会被 gflags 拒启,master Pod 秒退 CrashLoop);
      master Pod 不跑引擎,不装引擎依赖包。传输引擎包未注入(ENABLE_XCACHE_INSTALL=false)
      时不渲染 install 段,由镜像预装兜底——与 engine Pod 同开关语义。**不注入**
      log_analyzer / vllm argv——master Pod 在任何情况下都不承担推理职责
      (契约见 docs/contracts/wings-accel-interface.md);
    - 防御尾:运行期 IS_MOONCAKE_MASTER 未命中时 ERROR + exit 1,绝不静默成功。

    本支线位于 multi_node 占位检查**之前**:master Pod 无运行时上下文,resolve 产出
    resolved.nodes 占位视图,若落进占位支线会得到 exit 3 的不可执行脚本,资产与
    master 分支都不会产出。log_analyzer 守卫不适用(无引擎可监控,与 worker/占位
    同类豁免)。

    Args:
        resolved: 解析结果(master Pod 上通常为 multi_node 占位视图,accel 已合并)。
        start_path: start_command.sh 落盘路径。
        repro_path: repro.sh 落盘路径。

    Returns:
        ``(start_path, repro_path)`` 元组。
    """
    # advanced_features.json(使能状态单一真相源)与 accel 文件计划照常落盘。
    _write_advanced_features_json(resolved)
    _write_accel_generated_files(resolved.accel.generated_files)
    if resolved.accel.mooncake_script_assets_required:
        _install_mooncake_script_assets()
        env_overrides = _mooncake_kv_mem_env_overrides(resolved.accel)
        _write_mooncake_client_env(env_overrides)
        _write_mooncake_master_env(env_overrides)

    # 特性生效 → 产出段;未生效(auto 降级/开关未开)→ 挂起兜底段(与主管线
    # build_scripts 的二选一同构,复用同一段源)。
    section = resolved.accel.mooncake_master_section or _render_mooncake_master_hold_section()

    # install 段(仅传输引擎包,段序与 engine Pod 一致:install 在 master 分支段之前)。
    # mooncake_master 二进制随该包交付,镜像预装的可能是旧版——不装则 start 脚本传的
    # 新版 flag 会被旧二进制 gflags 拒启。未注入(ENABLE_XCACHE_INSTALL=false)→ 不渲染。
    transfer_package = getattr(resolved.accel, "mooncake_transfer_engine_package", None)
    install_lines: List[str] = []
    if transfer_package:
        _validate_accel_packages([transfer_package])
        install_lines = _render_accel_install_preamble(
            resolved.engine,
            # 与主管线同口径:优先 requested,回退 resolved(_render 内统一补 v 前缀)。
            resolved.engine_version.requested or resolved.engine_version.resolved,
            [transfer_package],
        )

    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "set -o errexit",
        "set -o xtrace",
        "",
        *_wings_log_fn_lines(),
        "",
        *install_lines,
        *section,
        "# master 交付支线防御尾:IS_MOONCAKE_MASTER 未命中时绝不静默成功,",
        "# 也不回退执行任何引擎命令。",
        '_wings_log ERROR "mooncake master delivery reached end without IS_MOONCAKE_MASTER match"',
        "exit 1",
        "",
    ]

    start_temp = start_path.with_name(f".{start_path.name}.tmp")
    start_temp.write_text("\n".join(lines), encoding="utf-8")
    start_temp.chmod(0o755)
    os.replace(start_temp, start_path)

    # master 交付本身就是完整可复现脚本(无占位符),repro 附来源头注释。
    repro_lines = [
        "# ─── Reproducibility Script (mooncake master pod delivery) ───",
        f"# Generated from: {', '.join(resolved.source_files)}",
        f"# Hardware: {resolved.hardware.hardware_family}",
        f"# Engine: {resolved.engine} v{resolved.engine_version.resolved}",
        f"# Topology: {resolved.topology.value}",
        "",
        *lines,
    ]
    repro_temp = repro_path.with_name(f".{repro_path.name}.tmp")
    repro_temp.write_text("\n".join(repro_lines), encoding="utf-8")
    repro_temp.chmod(0o755)
    os.replace(repro_temp, repro_path)

    logger.info(
        "mooncake master pod delivery: feature_section=%s, assets=%s, transfer_package=%s",
        bool(resolved.accel.mooncake_master_section),
        resolved.accel.mooncake_script_assets_required,
        transfer_package,
    )
    return start_path, repro_path


def _build_analyzer_config(resolved: ResolvedConfig) -> dict:
    """从 ResolvedConfig 投影为 log_analyzer 实际消费的 analyzer_config dict。

    log_analyzer 在引擎容器中作为后台进程运行,通过 ``--config`` 接收 JSON 配置。
    经代码审计,log_analyzer 仅消费以下 4 个字段:
    - ``engine``: 插件选择(PatternPluginManager.PLUGIN_MAPPING 的 key)
    - ``deployment_mode``: 插件选择(同上)
    - ``hardware``: 插件选择(同上)
    - ``backend_port``: 健康探测(_probe_backend_health 的 URL 端口)

    Args:
        resolved: 配置解析最终产物。

    Returns:
        analyzer_config dict,仅含 log_analyzer 实际消费的 4 个字段。
    """
    is_multi_node = resolved.topology == Topology.MULTI_NODE

    # backend_port: 从 engine_config_traces 提取,回退默认 17000
    backend_port = 17000
    port_traced = resolved.engine_config_traces.get("port")
    if port_traced and port_traced.final_value is not None:
        try:
            backend_port = int(port_traced.final_value)
        except (TypeError, ValueError):
            pass

    return {
        "engine": resolved.engine,
        "deployment_mode": "distributed" if is_multi_node else "single",
        "hardware": resolved.hardware.device,
        "backend_port": backend_port,
    }


def _build_analyzer_config_from_plan(resolved: ResolvedConfig, backend_port: int) -> dict:
    """从 ProcessPlan 投影为 log_analyzer 消费的 analyzer_config（PD 专用）。

    PD 顶层 ``engine_config_traces`` 已被清空（见 config_resolver._resolve_pd_config
    末尾），无法复用 ``_build_analyzer_config``（其 backend_port 取自顶层 trace）；
    engine / hardware 仍在顶层可读，端口必须从 ProcessPlan 显式传入。

    deployment_mode 取 ``"single"``：PD 是"当前 Pod 内进程级并行"，不是跨机分布式；
    首期复用 single 插件的阶段映射（init→load→boot→compile→ready）即可覆盖
    部署进度语义。后续若需 PD 专属阶段，扩展 PatternPluginManager.PLUGIN_MAPPING
    新增 PD 插件即可，log_analyzer 主循环与模板均无需改动。

    Args:
        resolved: 已含 process_plan 的 PD 解析结果。
        backend_port: 健康探测端口（解析自 process.advertised_endpoint）。
    """
    return {
        "engine": resolved.engine,
        "deployment_mode": "single",
        "hardware": resolved.hardware.device,
        "backend_port": backend_port,
    }


def _endpoint_port(endpoint: Optional[str]) -> int:
    """从 PD 的 ``"host:port"`` endpoint 严格解析端口。

    ``advertised_endpoint`` 是 ProcessPlan 的显式契约。解析失败必须在生成交付件
    前暴露，不能静默回退到默认端口，否则会掩盖自定义端口和规划回归。
    """
    if not endpoint:
        raise ValueError("PD process advertised_endpoint is required")
    host, separator, raw_port = endpoint.rpartition(":")
    if not separator or not host or not raw_port or not raw_port.isdigit():
        raise ValueError(f"invalid PD advertised_endpoint {endpoint!r}; expected host:port")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f"invalid PD endpoint port in {endpoint!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"PD endpoint port out of range in {endpoint!r}: {port}")
    return port


def _build_analyzer_preamble(resolved: ResolvedConfig) -> Optional[str]:
    """生成 log_analyzer shell 片段(仅 standalone 或 multi_node master 节点)。

    log_analyzer 作为 ``start_command.sh`` 中的后台进程,在引擎启动前启动,
    通过 ``tail -F`` 跟踪引擎日志,匹配阶段模式,写入 ``progress.jsonl``。

    跳过条件:
    - multi_node 占位脚本(``resolved.nodes`` 非空)→ 不注入
    - multi_node worker 节点(node_rank > 0)→ 不注入

    运行时模块路径: log_analyzer 在构建时被单独拷贝到 ``/opt/log_analyzer``(避免 pyc 编译),
    再由 ``wings_start.sh`` 拷贝到 ``/shared-volume/log_analyzer``,因此启动命令使用
    ``cd /shared-volume && python3 -B -m log_analyzer.log_analyzer``(顶层包名,非 wings_ctl 子包)。

    Args:
        resolved: 配置解析最终产物。

    Returns:
        log_analyzer shell 片段字符串;跳过时返回 None。
    """
    # multi_node 占位脚本不注入(无运行时上下文,不可执行)
    if resolved.nodes:
        return None

    is_multi_node = resolved.topology == Topology.MULTI_NODE
    node_rank = int(resolved.resolution_notes.get("multi_node_index", 0)) if is_multi_node else 0

    # worker 节点跳过(仅 master 运行分析器)
    if is_multi_node and node_rank > 0:
        return None

    analyzer_config = _build_analyzer_config(resolved)
    config_escaped = _json_config_escaped(analyzer_config)
    return _render_analyzer_preamble_template(config_escaped)


def _json_config_escaped(analyzer_config: dict) -> str:
    """序列化 analyzer config 并做 shell 单引号安全转义。

    JSON 经 ``json.dumps`` 生成(无裸单引号)再 ``' → '\"\\''\"'`` 转义,
    保证嵌入 shell 单引号 ``ANALYZER_CONFIG=...`` 时无注入/断引风险。

    Args:
        analyzer_config: log_analyzer 消费的配置 dict。

    Returns:
        可直接嵌入 shell 单引号字符串的转义后 JSON。
    """
    config_json = json.dumps(analyzer_config)
    # shell 单引号安全转义: ' → '"'"'
    return config_json.replace("'", "'\"'\"'")


def _render_analyzer_preamble_template(config_escaped: str) -> str:
    """从模板加载并注入动态变量,渲染 analyzer shell 片段。

    模板文件有 shell 语法高亮,可独立 ``bash -n`` 验证,Python 代码更简洁。
    progress.jsonl 必须写入共享卷,与 proxy 的 settings.PROGRESS_FILE 路径一致
    (proxy 通过 settings.PROGRESS_FILE 读取进度)。

    Args:
        config_escaped: 已做单引号转义的 analyzer config JSON。

    Returns:
        注入占位符后的 log_analyzer shell 片段。
    """
    template_path = Path(__file__).parent / "templates" / "analyzer_preamble.sh.tmpl"
    template = template_path.read_text(encoding="utf-8")
    return (
        template.replace("{ANALYZER_CONFIG}", config_escaped)
        .replace("{PROGRESS_FILE}", settings.PROGRESS_FILE)
        .replace("{ENGINE_LOG}", settings.ENGINE_LOG_FILE)
        .replace("{SHARED_VOLUME}", settings.SHARED_VOLUME_PATH)
    )


def _is_pd_worker_pod(resolved: ResolvedConfig) -> bool:
    """判定当前 PD Pod 是否为跨 pod 场景的 worker 节点。

    与 multi_node 一致:一个 logical Instance 的部署进度由 member 0(head)Pod
    统一代表上报,``member_index > 0`` 的 worker Pod 不启动 analyzer、不提供
    独立进度(语义是"进度归属 head",而非"多 Pod 共用同一进度文件")。
    注意 /shared-volume 是 Pod 内独立共享卷,并不跨 Pod 共享。

    ``member_index`` 取自 ``resolved.pd_topology.placement.node_ips`` 中
    ``rank_ip`` 的下标(见 pd/planner._resolve_explicit_allocation);
    普通 1P1D(derived)每个 logical instance 单 Pod,``member_index`` 恒为 0,
    因此只有大 EP 跨 Pod 场景的 worker 才会命中。

    Returns:
        当前 Pod 为 PD worker(跨 pod,非 member 0)→ True。
    """
    topology = resolved.pd_topology
    if topology is None:
        return False
    return topology.member_index > 0


def _build_analyzer_preamble_from_plan(resolved: ResolvedConfig) -> Optional[str]:
    """按 ProcessPlan 构建 log_analyzer shell 片段（PD 专用）。

    PD 顶层 traces 已清空,端口从 ``processes[0].advertised_endpoint`` 解析
    （多进程取首条即可:进度由聚合后的 engine.log 统一反映,健康探测用首进程端口）。
    progress_file / 日志路径 / 共享卷路径均复用 ``_render_analyzer_preamble_template``
    从 settings 读取,与标准路径完全一致。

    模板的 ``$ENGINE_PID`` early-fail 分支是否触发由渲染层形状决定:
    single case 有 ``ENGINE_PID`` 可用;多进程 case 靠 terminate_children 兜底清理。

    跳过条件:跨 pod PD 的 worker Pod(``member_index > 0``)不注入,
    与 multi_node worker 节点语义一致(仅 head 运行分析器)。

    Args:
        resolved: ``process_plan`` 非空的 PD 解析结果。

    Returns:
        log_analyzer shell 片段字符串;plan 为空/无进程/worker Pod 返回 None。
    """
    plan = resolved.process_plan
    if plan is None or not plan.processes:
        return None
    # 跨 pod PD 的 worker Pod 不注入(与 multi_node worker 一致)
    if _is_pd_worker_pod(resolved):
        return None
    first = plan.processes[0]
    # analyzer 只探测首进程；ProcessPlan 要求其 endpoint 显式且合法。
    backend_port = _endpoint_port(first.advertised_endpoint)
    analyzer_config = _build_analyzer_config_from_plan(resolved, backend_port)
    config_escaped = _json_config_escaped(analyzer_config)
    return _render_analyzer_preamble_template(config_escaped)


def _wings_log_fn_lines() -> List[str]:
    """shell 日志辅助函数段(所有交付脚本通用,主渲染与 master 交付支线复用)。

    输出符合 log-format 规范的日志行: 时间 [LEVEL] WINGS-CONTROL [组件#函数:行号] 消息。
    无条件定义,使无 analyzer_preamble 的路径(worker 节点 / master Pod)也能使用。
    """
    return [
        # shell 日志辅助函数: 输出符合 log-format 规范的日志行(所有脚本通用)。
        # 格式: 时间 [LEVEL] WINGS-CONTROL [组件#函数:行号] 消息
        "_wings_log() {",
        '    local level="$1"; shift',
        '    local msg="$*"',
        "    local ts",
        '    ts=$(date "+%Y-%m-%d %H:%M:%S.%3N")',
        '    echo "$ts [$level] WINGS-CONTROL [wings-launcher#start_command:0] $msg"',
        "}",
    ]


def _render_start_command_sh(
    argv: List[str],
    env_traces: Dict[str, TracedValue],
    system_setup: Optional[SystemSetup],
    *,
    engine: str,
    engine_version: str,
    packages: List[str],
    accel_enabled: bool = False,
    accel_pre_serve: Optional[List[str]] = None,
    accel_pre_serve_master: Optional[List[str]] = None,
    accel_pre_serve_client: Optional[List[str]] = None,
    kv_disk_offload_path: Optional[str] = None,
    analyzer_preamble: Optional[str] = None,
    engine_pre_start: Optional[List[str]] = None,
    system_setup_source_commands: Optional[List[str]] = None,
    mooncake_master_section: Optional[List[str]] = None,
) -> str:
    """生成 start_command.sh 内容。简洁执行脚本。

    Args:
        argv: 引擎命令 argv(含 accel 参数——accel.engine_config 已并入 engine_config_traces)。
        env_traces: env 逐项 trace。
        system_setup: 系统级设置。
        engine: 引擎名称,传给 wings-accel install.py。
        engine_version: 引擎版本,传给 wings-accel install.py。
        packages: 选中 scheme 声明的 pip 依赖(name:version),传给 install.py ``--config``。
        accel_enabled: wings-accel 是否真启用(``AccelResult.enabled``)。仅 True 时渲染
            runtime patch 安装段;False(未开/模块缺席)→ 不加,非 accel 路径零影响。
        accel_pre_serve: KV 存储后端 pre-serve 段(所有节点);None/空 → 不渲染。
        accel_pre_serve_master: KV 存储后端 pre-serve 段(仅 master);None/空 → 不渲染。
        accel_pre_serve_client: KV 存储后端 pre-serve 段(仅 client);None/空 → 不渲染。
        kv_disk_offload_path: KV 磁盘卸载实际路径(accel 产出);None(无磁盘卸载)→ 不渲染
            残留清理段。清理 vllm serve 前的卸载目录残留,保证重启后占用不超规划容量。
        analyzer_preamble: log_analyzer 进度监控 shell 片段;None → 不注入。
            在 env export 之前插入,确保分析器在引擎启动前就开始监控日志。
            启动后台分析器进程并注册 trap 清理。
        engine_pre_start: extension 生成的引擎专属启动前片段。公共渲染层只保证
            它位于通用 env/accel 准备之后、唯一引擎生命周期之前，不解释内容。
        system_setup_source_commands: 已校验的 source 环境初始化命令；紧邻 engine
            argv 前执行。
        mooncake_master_section: Mooncake master 分支段(early-exit 块的 shell 行);
            仅 distributed KV 启用时非空,在 install 段之后、pre-serve 之前插入。
            None/空 → 不渲染(非 mooncake 路径零影响)。
    """
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "set -o errexit",
        "set -o xtrace",
        "",
        *_wings_log_fn_lines(),
        "",
    ]

    # log_analyzer 进度监控(在 env export 之前,与旧版组装顺序一致)
    if analyzer_preamble:
        lines += [
            analyzer_preamble,
            "",
            # stdout 重定向到 engine.log(供 log_analyzer tail -F 跟踪)
            # 与旧版 wings_entry.py:1899-1911 逻辑一致:
            # 1) mkdir 确保日志目录存在
            # 2) PYTHONUNBUFFERED 确保引擎 ready 消息立即到达 engine.log(不卡在 8KB 缓冲区)
# 3) 过滤健康检查和调度噪声后写入 engine.log
            f"mkdir -p {settings.ENGINE_LOG_DIR}",
            "export PYTHONUNBUFFERED=1",
            "exec > >(grep --line-buffered -vE"
            " '\"GET\\s+/(health|metrics)\\s|\\b(Prefill|Decode) batch\\b'"
            f" | tee -a {settings.ENGINE_LOG_FILE}) 2>&1",
            "",
        ]

    # recipe、特性和 wings-accel 环境变量均已由 resolver 合并进 env_traces。
    env_lines = _render_env_section(env_traces)
    if env_lines:
        lines.extend(env_lines)
        lines.append("")

    setup_lines = _render_system_setup_comments(system_setup, system_setup_source_commands)
    if setup_lines:
        lines.extend(setup_lines)

    # wings-accel runtime patch 安装段(仅 accel 真启用时)
    if accel_enabled:
        _validate_accel_packages(packages)
        lines.extend(_render_accel_install_preamble(engine, engine_version, packages))

    # Mooncake master 分支段(early-exit 块,IS_MOONCAKE_MASTER 判定):
    # master Pod 只拉起 mooncake_master、不执行 vllm serve / mooncake_client;
    # 该判别独立于下方 RANK_IP==MASTER_IP(vllm 推理侧 master/client)。空 → 零影响。
    if mooncake_master_section:
        lines.extend(mooncake_master_section)

    # KV 存储后端(memcache/mooncake)pre-serve 段:vllm serve 前生成配置 / 起 daemon。
    # 非 KV 后端路径 → 两段皆空 → _render_accel_pre_serve_section 返回 [](零影响)。
    pre_serve_lines = _render_accel_pre_serve_section(accel_pre_serve, accel_pre_serve_master, accel_pre_serve_client)
    if pre_serve_lines:
        lines.extend(pre_serve_lines)

    # KV 磁盘卸载残留清理(仅 disk 开启):vllm serve 前清空卸载目录,保证重启后占用不超规划容量
    lines.extend(_render_kv_disk_cleanup_section(kv_disk_offload_path))


    # MindIE 等结构化配置引擎在这里准备外部 config、固定 ranktable 和动态环境。
    # extension 不能自行启动后台进程；进程回收和 analyzer cleanup 仍由公共层持有。
    if engine_pre_start:
        lines.extend(engine_pre_start)
    lines.extend(_render_system_setup_source_section(system_setup_source_commands))
    # 后台化引擎进程(而非 exec 替换 shell),使 trap cleanup_analyzer 保持有效。
    # exec 会替换 shell 进程导致 trap 失效:引擎退出时 cleanup 无法触发,
    # log_analyzer 成为孤儿进程。后台化 + wait 保持 shell 存活,trap 正常工作,
    # 引擎退出后 shell 执行 cleanup → kill log_analyzer(清理分析器)。
    # 注意:引擎已启动后(ENGINE_PID 已设置)失败只终止进程,analyzer 不写失败进度,
    # 最终失败状态由 FOA 判定;early-fail(status=failed)仅在引擎启动前脚本失败时触发。
    lines += [
        shlex.join(argv) + " &",
        "ENGINE_PID=$!",
        '_wings_log INFO "engine started, PID=$ENGINE_PID"',
        'wait "$ENGINE_PID"',
        "ENGINE_EXIT_CODE=$?",
        'exit "$ENGINE_EXIT_CODE"',
        "",
    ]
    return "\n".join(lines)


def _render_plan_repro_sh(
    resolved: ResolvedConfig,
    start_content: str,
    trace_comment_lines: List[str],
) -> str:
    """为结构化启动计划在实际脚本上补充来源注释。

    不能把 MindIE 的嵌套配置反向渲染成 ``--flag``。因此直接复用已经生成的
    start 内容，只在 shebang 后插入注释，保证 pre-start、daemon argv 与公共
    后台等待生命周期完全一致。
    """
    lines = start_content.splitlines()
    header = [
        "# ─── Reproducibility Script ───",
        f"# Generated from: {', '.join(resolved.source_files)}",
        f"# Hardware: {resolved.hardware.hardware_family}",
        f"# Engine: {resolved.engine} v{resolved.engine_version.resolved}",
        f"# Topology: {resolved.topology.value}",
        "",
        *trace_comment_lines,
        "",
    ]
    if not lines:
        return "\n".join(header) + "\n"
    return "\n".join([lines[0], *header, *lines[1:]]) + "\n"


def _render_repro_sh(
    resolved: ResolvedConfig,
    system_setup_source_commands: Optional[List[str]] = None,
) -> str:
    """生成 repro.sh 内容。可移植复现脚本,含来源注释。

    直接遍历 resolved.engine_config_traces 生成带注释的参数行,
    不从 argv 字符串反推 key/结构(避免脆弱的反向映射)。
    渲染规则复用 vllm_adapter.render_param_tokens(同一套逻辑,不重复实现)。

    Args:
        resolved: 解析结果。
    """
    lines = [
        "#!/usr/bin/env bash",
        "# ─── Reproducibility Script ───",
        f"# Generated from: {', '.join(resolved.source_files)}",
        f"# Hardware: {resolved.hardware.hardware_family}",
        f"# Engine: {resolved.engine} {resolved.engine_version.resolved}",
        f"# Topology: {resolved.topology.value}",
        "",
        "set -euo pipefail",
        "",
    ]

    # env section with trace comments
    if resolved.env_traces:
        lines.append("# ─── Environment Variables ───")
        for env_key, traced in resolved.env_traces.items():
            if traced.final_value is not None:
                lines.append(f"# source: {traced.source_file} @ {traced.source_path}")
                lines.append(
                    render_env_export(env_key, traced.final_value, allow_unsafe=traced.allow_unsafe)
                )
        lines.append("")

    # Mooncake master 分支段(与 start_command.sh 同款;repro 复现须含 master 判定)。
    if getattr(resolved.accel, "mooncake_master_section", None):
        lines.extend(resolved.accel.mooncake_master_section)

    # KV 存储后端 pre-serve 段(memcache/mooncake);与 start_command.sh 同款渲染。
    pre_serve_lines = _render_accel_pre_serve_section(
        resolved.accel.pre_serve, resolved.accel.pre_serve_master, resolved.accel.pre_serve_client
    )
    if pre_serve_lines:
        lines.extend(pre_serve_lines)

    # KV 磁盘卸载残留清理(与 start_command.sh 同款;repro 复现也需干净基线)
    lines.extend(_render_kv_disk_cleanup_section(resolved.accel.kv_disk_offload_path))

    setup_lines = _render_system_setup_comments(resolved.system_setup, system_setup_source_commands)
    if setup_lines:
        lines.extend(setup_lines)

    # command section — 来源注释块 + 单行 exec(避免续行与注释交互风险)
    lines.append("# ─── Engine Command 参数来源 ───")

    # 命令头(前缀 + model):按命令规格查表分派 model 形态(vllm 位置 / sglang --model-path)
    # model 取 canonical "model" 或别名 "model_path"(sglang recipe),与 build_argv 一致。
    model_traced = resolve_model_traced(resolved.engine_config_traces)
    model_value = str(model_traced.final_value) if model_traced else ""
    command_tokens: List[str] = build_command_head(resolved.engine, model_value)

    # 来源注释: model(命令头整段作注释)
    if model_traced:
        model_file = Path(model_traced.source_file).name
        model_cmd = shlex.join(command_tokens)
        lines.append(f"#   {model_cmd}   <- {model_traced.final_layer} ({model_file})")

    # 收集参数(命令 token + 来源注释)
    for key, traced in resolved.engine_config_traces.items():
        if key in MODEL_KEYS:  # model / model_path 已由命令头渲染,跳过避免重复
            continue
        tokens = render_param_tokens(key, traced.final_value)
        if tokens is None:
            continue
        command_tokens.extend(tokens)

        if len(tokens) == 1:
            rendered_for_comment = tokens[0]
        else:
            rendered_for_comment = f"{tokens[0]} {shlex.quote(tokens[1])}"
        source_file_name = Path(traced.source_file).name
        lines.append(f"#   {rendered_for_comment}   <- {traced.final_layer} ({source_file_name})")

    # 注:accel.engine_config 已作为 strategy_accel 合并层进 engine_config_traces,
    # 上方主循环已渲染并标来源,这里无需重复追加。

    # repro.sh 使用 exec 直接替换进程(无需 trap/cleanup,repro 仅用于复现,无 log_analyzer)
    lines.extend(_render_system_setup_source_section(system_setup_source_commands))
    lines.append("exec " + shlex.join(command_tokens))

    lines.append("")
    return "\n".join(lines)


_MULTI_NODE_BANNER = [
    "# ============================================================================",
    "# MULTI-NODE — RUNTIME INJECTION PENDING (RANK_IP/NODE_IPS are unavailable)",
    "# This is a placeholder script: nodes are loaded and merged, but the current Pod is not selected.",
    "# Rerun wings-ctl in each Pod with RANK_IP/NODE_IPS/MASTER_IP to generate an executable script.",
    "# The argv/env values below contain literal unresolved placeholders and are for review only.",
    "# Do not execute this script directly.",
    "# ============================================================================",
]


def _render_multi_node_placeholder(resolved: ResolvedConfig) -> str:
    """渲染 multi_node 占位脚本(无运行时上下文):不产 ``exec``,不假装可跑。

    顶部横幅声明"未注入";每节点一段**注释化**的 env + argv(``$占位符`` 字面);
    脚本主体只 echo + 非零退出,显式阻断误执行。

    Args:
        resolved: 解析结果(``resolved.nodes`` 必须非空)。

    Returns:
        占位 start_command.sh / repro.sh 文本。
    """
    lines = ["#!/usr/bin/env bash"]
    lines.extend(_MULTI_NODE_BANNER)
    lines.append("set -euo pipefail")
    lines.append('echo "multi_node placeholder script: runtime injection is pending (missing RANK_IP/NODE_IPS); do not execute directly" >&2')
    lines.append("exit 3")
    lines.append("")

    for i, node in enumerate(resolved.nodes or []):
        idx = f" index={node.index}" if node.index is not None else ""
        lines.append(f"# ─── node[{i}] role={node.role}{idx} (source: {node.source_prefix}) ───")
        env_lines = _render_env_section(node.env_traces)
        if env_lines:
            lines.append("#   env (runtime injection pending):")
            lines.extend(f"#     {line}" for line in env_lines)
        setup_lines = _render_system_setup_comments(node.system_setup)
        lines.extend(f"# {line}" if line else "#" for line in setup_lines)
        source_commands = build_system_setup_source_commands(resolved.engine, node.system_setup)
        if source_commands:
            lines.append("#   source commands (runtime injection pending):")
            lines.extend(f"#     {command}" for command in source_commands)
        argv = build_argv(node.engine_config_traces, engine=resolved.engine)
        lines.append("#   argv (runtime injection pending; placeholders are literal):")
        lines.append(f"#     {shlex.join(argv)}")
        lines.append("")
    return "\n".join(lines)


def _pd_render_engine_line(process: EngineProcessPlan, engine_log: str) -> List[str]:
    """渲染 fail_together 单条进程启动子块（管道聚合 + env + exec）。

    ``( ) &`` 子进程的 stdout 不会继承顶层管道重定向，
    故每条进程单独接 grep + tee，聚合同一 ``engine.log`` 供 log_analyzer ``tail -F``。
    过滤模式与标准路径一致（health/metrics + Prefill/Decode batch 去噪）。
    进程级 env 在子块内 export，保持 per-process 独立。

    Args:
        process: 单条 EngineProcessPlan。
        engine_log: engine.log 路径。

    Returns:
        ``( ) &`` 子块脚本行（含 ``pids+=("$!")`` 与收尾空行）。
    """
    lines = ["("]
    lines.extend(f"  {line}" for line in _render_env_section(process.env_traces))
    lines.append(
        "  exec > >(grep --line-buffered -vE"
        " '\"GET\\s+/(health|metrics)\\s|\\b(Prefill|Decode) batch\\b'"
        f" | tee -a {engine_log}) 2>&1"
    )
    lines.append("  exec " + shlex.join(process.argv))
    lines += [
        ") &",
        'pids+=("$!")',
        "",
    ]
    return lines


def _render_pd_process_plan(
    resolved: ResolvedConfig,
    *,
    analyzer_preamble: Optional[str] = None,
    system_setup_source_commands: Optional[List[str]] = None,
) -> str:
    """从唯一 ``ProcessPlan`` 渲染 single 或 fail-together 脚本。

    与标准路径同构地注入 log_analyzer 进度监控:
    - 无条件定义 ``_wings_log()``(多进程场景也用它规范日志格式);
    - 注入 ``analyzer_preamble``(含 rm 旧日志 + 起分析器 + cleanup trap)在 env 之前;
    - single: 顶层 tee 重定向 + 后台化 + wait(保持 shell 存活使 trap cleanup 生效;
      引擎启动后失败仅终止进程,analyzer 不写失败进度,失败由 FOA 判定);
    - fail_together: 每条进程单独 tee 子块 + ``pids`` 统一清理(单一 trap 同时终止
      子进程与 log_analyzer,避免 EXIT/SIGTERM 双 trap 竞争覆盖)。

    Args:
        resolved: ``process_plan`` 非空的 PD 解析结果。
        analyzer_preamble: log_analyzer shell 片段;None → 不注入。
        system_setup_source_commands: 当前 PD Pod 在启动全部 engine 前执行一次的 source
            环境初始化命令。

    Returns:
        可执行 bash 脚本文本；每条命令来自结构化 argv 并经 ``shlex.join``。

    Raises:
        ValueError: plan 为空、layout/lifecycle 不受支持或进程集合为空。
    """
    plan = resolved.process_plan
    if plan is None or not plan.processes:
        raise ValueError("PD rendering requires a non-empty process_plan")
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        # shell 日志辅助函数: 输出符合 log-format 规范的日志行(与标准路径一致)。
        "_wings_log() {",
        '    local level="$1"; shift',
        '    local msg="$*"',
        "    local ts",
        '    ts=$(date "+%Y-%m-%d %H:%M:%S.%3N")',
        '    echo "$ts [$level] WINGS-CONTROL [wings-launcher#start_command:0] $msg"',
        "}",
        "",
    ]

    # log_analyzer 进度监控(在 env export 之前,与标准路径组装顺序一致)。
    # 多进程下不放顶层 exec tee(无效),改由每条进程的 tee 子块接管;此处仅 mkdir + unbuffer。
    if analyzer_preamble:
        lines += [
            analyzer_preamble,
            "",
            f"mkdir -p {settings.ENGINE_LOG_DIR}",
            "export PYTHONUNBUFFERED=1",
            "",
        ]

    if system_setup_source_commands:
        setup_lines = _render_system_setup_comments(resolved.system_setup, system_setup_source_commands)
        if setup_lines:
            lines.extend(setup_lines)
    lines.extend(_render_system_setup_source_section(system_setup_source_commands))

    if plan.lifecycle == "single":
        process = plan.processes[0]
        # 顶层 tee 重定向 + 后台化 + wait:与标准路径同构,ENGINE_PID 供 cleanup
        # 定位引擎进程。exec 会替换 shell 使 trap 失效,故改为后台化 + wait。
        # 引擎启动后失败只终止进程,analyzer 不写失败进度,失败状态由 FOA 判定。
        lines.append(
            "exec > >(grep --line-buffered -vE"
            " '\"GET\\s+/(health|metrics)\\s|\\b(Prefill|Decode) batch\\b'"
            f" | tee -a {settings.ENGINE_LOG_FILE}) 2>&1"
        )
        lines.append("")
        env_lines = _render_env_section(process.env_traces)
        if env_lines:
            lines.extend(env_lines)
            lines.append("")
        lines += [
            shlex.join(process.argv) + " &",
            "ENGINE_PID=$!",
            '_wings_log INFO "engine started, PID=$ENGINE_PID"',
            'wait "$ENGINE_PID"',
            "ENGINE_EXIT_CODE=$?",
            'exit "$ENGINE_EXIT_CODE"',
            "",
        ]
        return "\n".join(lines)

    if plan.lifecycle != "fail_together":
        raise ValueError(f"Unknown PD lifecycle: {plan.lifecycle!r}")

    # 统一清理函数: 同时终止子进程与 log_analyzer。
    # 注册单一 trap(EXIT TERM INT)覆盖 preamble 的 cleanup trap——fail_together 无
    # ENGINE_PID、不写 early-fail(见设计 §6.2),由终止子进程 + kill 分析器收口即可。
    # 单一 trap 避免 EXIT/SIGTERM 被双 trap 后者覆盖导致的清理缺失。
    lines += [
        "pids=()",
        "terminate_children() {",
        "  local pid",
        '  for pid in "${pids[@]}"; do',
        '    kill -TERM "$pid" 2>/dev/null || true',
        "  done",
        '  kill ${LOG_ANALYZER_PID:-} 2>/dev/null || true',
        "}",
        "trap terminate_children EXIT TERM INT",
        "",
    ]
    for process in plan.processes:
        lines.append(f"# process[{process.process_index}] rank={process.dp_rank}")
        lines += _pd_render_engine_line(
            process, settings.ENGINE_LOG_FILE
        )
    lines += [
        "status=0",
        "set +e",
        'wait -n "${pids[@]}"',
        "status=$?",
        "set -e",
        "terminate_children",
        'for pid in "${pids[@]}"; do',
        '  wait "$pid" 2>/dev/null || true',
        "done",
        "if (( status == 0 )); then status=1; fi",
        'exit "$status"',
        "",
    ]
    return "\n".join(lines)


_LOG_ANALYZER_MARKERS = (
    "log_analyzer.log_analyzer",  # 分析器进程启动命令
    "--progress-file",            # 进度文件参数
    "cleanup_analyzer",           # 分析器清理 trap
)


def _render_pd_repro_sh(
    resolved: ResolvedConfig,
    system_setup_source_commands: Optional[List[str]] = None,
) -> str:
    """从同一 ProcessPlan 渲染无部署副作用的 PD 复现脚本。

    repro 只保留逐进程 env/argv 与 fail-together 监督，不启动 analyzer、不清理
    progress/log 文件，也不依赖部署期 tee 和 trap。
    """
    plan = resolved.process_plan
    if plan is None or not plan.processes:
        raise ValueError("PD repro rendering requires a non-empty process_plan")

    lines = [
        "#!/usr/bin/env bash",
        "# ─── Reproducibility Script ───",
        f"# Generated from: {', '.join(resolved.source_files)}",
        f"# Hardware: {resolved.hardware.hardware_family}",
        f"# Engine: {resolved.engine} {resolved.engine_version.resolved}",
        f"# Topology: {resolved.topology.value}",
        "# ProcessPlan is the source of truth for rank, endpoint and argv.",
        "",
        "set -euo pipefail",
        "",
    ]

    if system_setup_source_commands:
        setup_lines = _render_system_setup_comments(resolved.system_setup, system_setup_source_commands)
        if setup_lines:
            lines.extend(setup_lines)
    lines.extend(_render_system_setup_source_section(system_setup_source_commands))

    if plan.lifecycle == "single":
        process = plan.processes[0]
        lines.append(f"# process[{process.process_index}] rank={process.dp_rank} endpoint={process.advertised_endpoint}")
        lines.extend(_render_env_section(process.env_traces))
        if process.env_traces:
            lines.append("")
        lines.append("exec " + shlex.join(process.argv))
        lines.append("")
        return "\n".join(lines)

    if plan.lifecycle != "fail_together":
        raise ValueError(f"Unknown PD lifecycle: {plan.lifecycle!r}")

    lines += [
        "pids=()",
        "terminate_children() {",
        "  local pid",
        '  for pid in "${pids[@]}"; do',
        '    kill -TERM "$pid" 2>/dev/null || true',
        "  done",
        "}",
        "trap terminate_children EXIT TERM INT",
        "",
    ]
    for process in plan.processes:
        lines.append(f"# process[{process.process_index}] rank={process.dp_rank} endpoint={process.advertised_endpoint}")
        lines.append("(")
        lines.extend(f"  {line}" for line in _render_env_section(process.env_traces))
        lines.append("  exec " + shlex.join(process.argv))
        lines += [") &", 'pids+=("$!")', ""]
    lines += [
        "status=0",
        "set +e",
        'wait -n "${pids[@]}"',
        "status=$?",
        "set -e",
        "terminate_children",
        'for pid in "${pids[@]}"; do',
        '  wait "$pid" 2>/dev/null || true',
        "done",
        "if (( status == 0 )); then status=1; fi",
        'exit "$status"',
        "",
    ]
    return "\n".join(lines)


def _validate_log_analyzer_present(resolved: ResolvedConfig, script_text: str) -> None:
    """守卫校验:真实部署脚本必须含 log_analyzer 进度监控片段。

    防止"新增渲染支线漏接 log_analyzer"一类回归(本次 PD 缺漏即为先例),
    违反即抛 ``ValueError``(fail-fast,部署前暴露接线缺失)。

    例外(不校验):
    - multi_node 占位脚本(``resolved.nodes`` 非空):不可执行,非真实部署;
    - multi_node worker 节点(``multi_node_index > 0``):仅 master 运行分析器;
    - 跨 pod PD 的 worker Pod(``pd_topology.member_index > 0``):与 multi_node
      worker 语义一致,仅 member 0(head)运行分析器;
    - Mooncake master 专属 Pod 交付支线(``_deliver_mooncake_master_pod``):
      无引擎可监控,该支线不调用本守卫。

    校验用固定哨兵(启动命令 / ``--progress-file`` / ``cleanup_analyzer`` trap),
    不依赖任何可变路径,避免误报。PD 的 fail_together 虽以 ``terminate_children``
    单一 trap 收口清理,但 preamble 中 ``cleanup_analyzer`` 定义仍原样注入脚本,
    三个哨兵对 single / fail_together / 标准路径均成立。

    Args:
        resolved: 已构建脚本的解析结果。
        script_text: 待校验的 start_command.sh 文本。

    Raises:
        ValueError: 真实部署脚本缺少 log_analyzer 片段时。
    """
    # 占位脚本非真实部署,跳过
    if resolved.nodes:
        return
    # multi_node worker 不运行分析器,跳过
    if resolved.topology == Topology.MULTI_NODE:
        node_rank = int(resolved.resolution_notes.get("multi_node_index", 0))
        if node_rank > 0:
            return
    # 跨 pod PD 的 worker Pod 不运行分析器,跳过
    if _is_pd_worker_pod(resolved):
        return
    missing = [m for m in _LOG_ANALYZER_MARKERS if m not in script_text]
    if missing:
        raise ValueError(
            "deployment progress guard: start_command.sh missing log_analyzer "
            f"fragment: {missing} (topology={resolved.topology.value})"
        )


def build_scripts(
    resolved: ResolvedConfig,
    output_dir: Path,
) -> Tuple[Path, Path]:
    """生成 start_command.sh 和 repro.sh 并写入 output_dir。

    四条路径:
    - PD ``process_plan`` 非空 → 按 single/fail-together 生命周期渲染可执行脚本。
    - multi_node 占位(``resolved.nodes`` 非空,无运行时上下文)→ 占位脚本(无 exec,exit 3)。
    - multi_node 已注入(topology==MULTI_NODE 且已选 node)→ 渲染可执行脚本。
    - standalone → 渲染可执行脚本。

    ``system_setup.commands`` 默认仅以注释形式保留；引擎启动计划明确给出的
    ``source <absolute-path>`` 初始化命令会在对应 engine argv 前执行。

    Returns:
        (start_command_path, repro_path) 元组。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start_path = output_dir / "start_command.sh"
    repro_path = output_dir / "repro.sh"

    if resolved.process_plan:
        # PD 场景补齐 log_analyzer 进度监控(见设计 §4.4):从 ProcessPlan 构建 preamble。
        analyzer_preamble = _build_analyzer_preamble_from_plan(resolved)
        source_commands = build_system_setup_source_commands(resolved.engine, resolved.system_setup)
        pd_script = _render_pd_process_plan(
            resolved,
            analyzer_preamble=analyzer_preamble,
            system_setup_source_commands=source_commands,
        )
        repro_script = _render_pd_repro_sh(resolved, source_commands)
        # 部署进度功能守卫:PD 属真实部署路径,必须含 log_analyzer 片段(fail-fast)。
        # 先校验后落盘,守卫失败时不留半成品交付件。
        _validate_log_analyzer_present(resolved, pd_script)
        start_path.write_text(pd_script, encoding="utf-8")
        start_path.chmod(0o755)
        repro_path.write_text(repro_script, encoding="utf-8")
        repro_path.chmod(0o755)
        return start_path, repro_path

    # Mooncake master 专属 Pod 交付支线:先于 multi_node 占位检查。master Pod 无
    # 运行时上下文,resolve 产出 resolved.nodes 占位视图,若落进占位支线会得到
    # exit 3 的不可执行脚本,资产与 master 分支都不会产出。交付细节见
    # _deliver_mooncake_master_pod。
    if _is_mooncake_master_pod():
        return _deliver_mooncake_master_pod(resolved, start_path, repro_path)

    if resolved.nodes:
        # multi_node 占位:两件产物同为占位脚本,显式阻断误执行。
        # 占位脚本不 exec,也不追加 accel 产出。
        placeholder = _render_multi_node_placeholder(resolved)
        start_path.write_text(placeholder, encoding="utf-8")
        start_path.chmod(0o755)
        repro_path.write_text(placeholder, encoding="utf-8")
        repro_path.chmod(0o755)
        return start_path, repro_path

    # advanced_features.json(使能状态单一真相源)在脚本生成阶段写入共享卷,
    # health 接口 /v1/startup/accel 读它回显页面(对齐老仓库 wings_entry 时机)。
    _write_advanced_features_json(resolved)

    # wings-accel 文件计划(disk/cpu_disk 的 lmcache_config.yaml、KV 后端 start_kv_serve.sh 等)
    # 解析期不落盘,此处(仅正式运行,非 dry-run)校验并原子写入共享卷。
    _write_accel_generated_files(resolved.accel.generated_files)
    if resolved.accel.mooncake_script_assets_required:
        _install_mooncake_script_assets()
        # KV_MEM_OFFLOAD_SIZE=auto 智能推荐:覆盖逻辑与 master 交付支线共用
        # _mooncake_kv_mem_env_overrides(单一口径,语义见该函数 docstring)。
        env_overrides = _mooncake_kv_mem_env_overrides(resolved.accel)
        _write_mooncake_client_env(env_overrides)
        _write_mooncake_master_env(env_overrides)

    # registry 是 CLI、正式渲染和摘要共用的唯一 adapter 分发点。公共层只消费
    # 启动计划，不判断 MindIE，也不读取其 engine_state。
    launch_plan = build_launch_plan(resolved)
    argv = launch_plan.argv
    analyzer_preamble = _build_analyzer_preamble(resolved)
    # master 分支段随特性产出嵌入所有 Pod 的脚本(运行期由 IS_MOONCAKE_MASTER 判定,
    # engine Pod 上恒为 no-op)。master Pod 自身已在上方专属交付支线接管(含特性
    # 降级时的挂起兜底),不会走到本路径——此处的身份判别兜底因此不再需要。
    mooncake_master_section = getattr(resolved.accel, "mooncake_master_section", None)
    start_content = _render_start_command_sh(
        argv,
        resolved.env_traces,
        resolved.system_setup,
        engine=resolved.engine,
        # install preamble 使用实际引擎版本(优先 requested,回退 resolved)。
        engine_version=resolved.engine_version.requested or resolved.engine_version.resolved,
        packages=resolved.accel.packages,
        accel_enabled=resolved.accel.enabled,
        accel_pre_serve=resolved.accel.pre_serve,
        accel_pre_serve_master=resolved.accel.pre_serve_master,
        accel_pre_serve_client=resolved.accel.pre_serve_client,
        kv_disk_offload_path=resolved.accel.kv_disk_offload_path,
        analyzer_preamble=analyzer_preamble,
        engine_pre_start=launch_plan.pre_start_lines,
        system_setup_source_commands=launch_plan.system_setup_source_commands,
        mooncake_master_section=mooncake_master_section,
    )
    # 部署进度功能守卫:standalone / multi_node 真实部署须含 log_analyzer 片段。
    # worker 与占位按 §5.2 口径跳过;任何真实部署路径漏接都会在此 fail-fast。
    # 与 PD 路径一致,先校验后落盘:守卫失败时不留下未通过校验的交付件。
    _validate_log_analyzer_present(resolved, start_content)

    start_temp = start_path.with_name(f".{start_path.name}.tmp")
    start_temp.write_text(start_content, encoding="utf-8")
    start_temp.chmod(0o755)
    os.replace(start_temp, start_path)

    if launch_plan.repro_trace_lines is not None:
        repro_content = _render_plan_repro_sh(
            resolved,
            start_content,
            launch_plan.repro_trace_lines,
        )
    else:
        repro_content = _render_repro_sh(resolved, launch_plan.system_setup_source_commands)
    repro_temp = repro_path.with_name(f".{repro_path.name}.tmp")
    repro_temp.write_text(repro_content, encoding="utf-8")
    repro_temp.chmod(0o755)
    os.replace(repro_temp, repro_path)

    return start_path, repro_path
