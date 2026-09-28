#!/usr/bin/env python3
"""
func_smart_accel 验证脚本 — 单 YAML 快照 + 全量矩阵扫描两种形态。

形态一(legacy,单 YAML 快照):
    用 YAML 或 CLI flags 构造 SmartAccelInput,打印 input/output,人工/CI 验证。
    python3 tests/wings_accel/smart_accel_io.py tests/wings_accel/fixtures/smart_accel_all_features.yaml

形态二(matrix / scan / coverage / save-samples,逐特性逐变体):
    对 smart-accel 资产里的每个模型,把 decoding / sparse / kv_offload 各变体【隔离】成
    单元素 block,每次只开一个特性、一个变体,跑 func_smart_accel 并核对选中 scheme。
      投机(decoding):每个 method 单测;model_based 给 stub 草稿路径。
      稀疏(sparse):每个 scheme 单测,mode=scheme.name。
      卸载(kv_offload):每个 scheme 单测,按 connector+backend 分为
        native / memcache / mooncake / lmcache(:disk|:cpu_disk) / lmcache-ascend,
        并按需开 memory / disk 主开关。
    offload 的 files: 块统一渲染为文件计划，并在内存中校验内容；计划路径使用临时根目录,
    不会写入宿主 /shared-volume。

用法:
    # 单模型矩阵:测一个模型全部变体
    python3 tests/wings_accel/smart_accel_io.py <yaml> --matrix

    # 扫描所有模型(默认 vllm + vllm-ascend)
    python3 tests/wings_accel/smart_accel_io.py --scan-all
    python3 tests/wings_accel/smart_accel_io.py --scan vllm vllm-ascend
    python3 tests/wings_accel/smart_accel_io.py --scan vllm-ascend --filter GLM-5.2

    # 路径覆盖检查(按特性/变体统计哪些模型路径声明了它)
    python3 tests/wings_accel/smart_accel_io.py --coverage
    python3 tests/wings_accel/smart_accel_io.py --coverage --feature offload --max-paths 0

    # 每种变体取一条代表路径,把完整输出写成 markdown 供审阅
    python3 tests/wings_accel/smart_accel_io.py --save-samples tests/wings_accel/samples

    # JSON 结构化结果(适合 golden/diff)
    python3 tests/wings_accel/smart_accel_io.py --scan-all --json > scan.json

生产/集成入口不是本脚本,而是直接调用 func_smart_accel(smart_input) -> output;
本脚本仅供快速验证。两种入口都长期支持。
"""

import argparse
import dataclasses
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

# 兼容两种启动姿势:从 wings_control/ 运行(旧:sys.path.append("src")),
# 或从任意 CWD 运行(按脚本位置定位 src)。
sys.path.append("src")
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from wings_accel import (
    LoadFlags,
    func_smart_accel,
    load_smart_accel_from_yaml,
)
from wings_accel.schemas import (
    SmartAccelInput,
    SmartAccelOutput,
    SmartDecodingConfig,
    DistributedKVCacheConfig,
    SmartKVCacheConfig,
    SmartKVSparseConfig,
)

# ── 资产路径 ── smart_accel_io.py → wings_control/src/wings_accel/smart-accel
_SMART_ACCEL_ROOT = Path(__file__).resolve().parents[2] / "src" / "wings_accel" / "smart-accel"
DEFAULT_SCAN_DIRS = ["vllm", "vllm-ascend"]


@contextmanager
def _draft_stub(method: dict) -> Iterator[str]:
    """为 model_based 变体构造临时 stub 草稿目录(含 config.json),用完自动清理。

    architectures 按 draft_arch 首个关键字定制,保证专用方法命中其声明架构;
    无 draft_arch 的通用草稿(draft_model/ernie_mtp 等)用方法名当关键字,
    走 generic 分支。本地有 config.json 是 decoders 架构门控的前提。
    """
    arch = method.get("draft_arch") or [method.get("name") or "draft"]
    kw = arch[0] if isinstance(arch, list) else arch
    with tempfile.TemporaryDirectory(prefix="draft-stub-") as d:
        (Path(d) / "config.json").write_text(json.dumps({"architectures": [f"{kw}StubForCausalLM"]}), encoding="utf-8")
        yield str(d)


_MEM_CAPACITY_GB = 128  # 内存卸载容量(GB),用于占位符 {memory_capacity_gb} / {= ... // gpu_count}
_DISK_CAPACITY_GB = 512
_DISK_PATH = "/var/cache/lmcache"

# SmartAccelOutput 选中字段 / 诊断 key,按特性分叉(core._collect_diagnostics 的 key)
_SCHEME_GETTER = {
    "decoding": lambda o: o.smart_decoding_scheme,
    "sparse": lambda o: o.smart_kv_sparse_scheme,
    "offload": lambda o: o.smart_kv_cache_scheme,
    "distributed": lambda o: o.smart_distributed_kv_cache_scheme,
}
_DIAG_KEY = {"decoding": "decoding", "sparse": "sparse", "offload": "kv_cache", "distributed": "distributed_kv_cache"}


# ══════════════════════════════════════════════════════════════════
# 形态一:legacy 单 YAML 快照(保留原行为)
# ══════════════════════════════════════════════════════════════════


def _flags_from_args(args) -> LoadFlags:
    return LoadFlags(
        kv=args.kv,
        sparse=args.sparse,
        disk=args.disk,
        qat=args.qat,
        disk_gb=args.disk_gb,
        disk_path=args.disk_path,
        qat_devices=args.qat_devices,
        qat_level=args.qat_level,
        decoding_model_path=args.decoding_model_path,
        sparse_level=args.sparse_level,
        memory_offload_size_mode=args.memory_offload_size_mode,
        pod_available_memory_gb=args.pod_available_memory_gb,
    )


def _print_input(inp) -> None:
    print("════════════════ SmartAccelInput ════════════════")
    hw = inp.hardware_config
    print(f"[Hardware] gpu_type={hw.gpu_type}  gpu_count={hw.gpu_count}")
    m = inp.model_config
    print(f"[Model]    name={m.model_name or '-'}  arch={m.model_arch or '-'}")
    print(f"           path={m.model_path or '-'}")
    e = inp.engine_config
    print(f"[Engine]   name={e.name}  version={e.version}")
    print(f"[Deploy]   pd_role={inp.deployment_mode.pd_role or '-'}")

    dec = inp.smart_decoding_config
    print(f"[Decoding] enabled={dec.enabled}  model_path={dec.model_path or '-'}")

    sp = inp.smart_kv_sparse_config
    print(f"[Sparse]   enabled={sp.enabled}  mode={sp.mode}")

    kv = inp.smart_kv_cache_config
    print(f"[KVCache]  enabled={kv.enabled}")
    if kv.enabled:
        print(
            f"           memory_offload={kv.memory_offload_enabled}"
            f"  memory_offload_size_mode={kv.memory_offload_size_mode or '-'}"
            f"  capacity_gb={getattr(kv, '_memory_capacity_gb', 0)}"
        )
        print(
            f"           disk_offload={kv.disk_offload_enabled}"
            f"  capacity_gb={kv.disk_capacity_gb}"
            f"  path={kv.disk_path or '-'}"
        )
        print(f"           qat={kv.qat_enabled}  devices={kv.qat_device_count}  level={kv.qat_compression_level}")


def _print_output(out) -> None:
    print()
    print("════════════════ SmartAccelOutput ════════════════")

    print("\n── Schemes ──")
    _print_params(
        {
            "smart_decoding_scheme": out.smart_decoding_scheme,
            "smart_kv_sparse_scheme": out.smart_kv_sparse_scheme,
            "smart_kv_cache_scheme": out.smart_kv_cache_scheme,
        }
    )

    print("\n── EngineParams ──")
    _print_params(out.engine_params.engine_config)
    _print_env(out.engine_params.env)


def _print_params(params) -> None:
    if not params:
        print("  (无)")
        return
    for k, v in params.items():
        print(f"  {k}: {v if v is not None else '-'}")


def _print_cli(cli) -> None:
    if cli:
        print(f"  CLI: {' '.join(cli)}")


def _print_env(env) -> None:
    if env:
        print("  ENV:")
        for k, v in env.items():
            print(f"    {k}={v}")


def _legacy_main(args) -> int:
    """形态一:单 YAML 快照,打印 input/output(或 JSON)。"""
    flags = _flags_from_args(args)
    smart_input = load_smart_accel_from_yaml(args.yaml_path, flags)
    if smart_input is None:
        raise SystemExit(f"SmartAccel YAML not found: {args.yaml_path}")
    output = func_smart_accel(smart_input)

    if args.json:
        result = {}
        if args.print in ("input", "both"):
            result["input"] = dataclasses.asdict(smart_input)
        if args.print in ("output", "both"):
            result["output"] = dataclasses.asdict(output)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if args.print in ("input", "both"):
            _print_input(smart_input)
        if args.print in ("output", "both"):
            _print_output(output)
    return 0


# ══════════════════════════════════════════════════════════════════
# 形态二:matrix / scan —— 逐特性逐变体隔离测试
# ══════════════════════════════════════════════════════════════════


@dataclass
class VariantResult:
    """单个(模型, 特性, 变体)的测试结果。"""

    feature: str  # decoding / sparse / offload
    label: str  # 变体标签(method 名 / sparse mode / offload 类型)
    ok: bool  # 选中 scheme 与预期一致且无异常
    scheme: Optional[str] = None  # 实际选中 scheme(None=未产出)
    expect: Optional[str] = None  # 预期 scheme 名(= 隔离变体的 name)
    degraded: bool = False  # 是否降级(diagnostics 标记)
    error: str = ""  # 异常信息 / 不匹配说明;ok 时为空
    engine_config: Dict[str, Any] = field(default_factory=dict)
    envs: Dict[str, str] = field(default_factory=dict)
    packages: List[str] = field(default_factory=list)
    file_errors: List[str] = field(default_factory=list)  # offload 文件计划语义校验错误(JSON/YAML/bash)
    pre_serve: List[str] = field(default_factory=list)
    pre_serve_master: List[str] = field(default_factory=list)
    pre_serve_client: List[str] = field(default_factory=list)


def _load_base_input(yaml_path: Path) -> Optional[SmartAccelInput]:
    """加载模型 YAML 为 base SmartAccelInput(全特性关闭,仅取上下文 + smart_accel 模板)。

    config_root 指向 smart-accel 根,使 files: 条目的 src: 模板可解析(与生产
    load_smart_accel_from_config 行为对齐)。
    """
    inp = load_smart_accel_from_yaml(str(yaml_path), LoadFlags())
    if inp is None:
        return None
    inp.config_root = str(_SMART_ACCEL_ROOT)
    return inp


def _disable_all_features(inp: SmartAccelInput) -> None:
    """把三个特性 intent 全部置为关闭(隔离测试的起点,再按需开一个)。"""
    inp.smart_decoding_config = SmartDecodingConfig(enabled=False)
    inp.smart_kv_cache_config = SmartKVCacheConfig(enabled=False)
    inp.distributed_kv_cache_config = DistributedKVCacheConfig(enabled=False)
    inp.smart_kv_sparse_config = SmartKVSparseConfig(enabled=False)


def _validate_generated_file_plans(file_plans) -> None:
    """Validate GeneratedFile plan content in memory without writing to the shared volume."""
    errors: List[str] = []
    for file_plan in file_plans or []:
        path = Path(str(getattr(file_plan, "path", "") or ""))
        text = str(getattr(file_plan, "content", "") or "")
        try:
            if path.suffix.lower() == ".json":
                json.loads(text)
            elif path.suffix.lower() in (".yaml", ".yml"):
                yaml.safe_load(text)
            elif path.suffix.lower() == ".sh":
                process = subprocess.run(["bash", "-n"], input=text, capture_output=True, text=True, timeout=5)
                if process.returncode != 0:
                    stderr = (process.stderr or "").strip()[:120]
                    errors.append(f"{path.name}: bash -n failed: {stderr}")
            elif not text.strip():
                errors.append(f"{path.name}: empty file")
        except Exception as exc:
            errors.append(f"{path.name}: invalid rendered content: {exc}")
    if errors:
        raise ValueError("generated file plan validation failed: " + "; ".join(errors))


def _run_one(feature: str, label: str, inp: SmartAccelInput, expect: str) -> VariantResult:
    """跑一次 func_smart_accel,核对选中 scheme 是否 == 预期。"""
    try:
        out: SmartAccelOutput = func_smart_accel(inp)
        _validate_generated_file_plans(out.generated_files)
    except Exception as exc:  # 单变体异常不中断整体扫描
        return VariantResult(
            feature=feature,
            label=label,
            ok=False,
            expect=expect,
            error=f"{type(exc).__name__}: {exc}",
        )
    got = _SCHEME_GETTER[feature](out)
    diag = out.diagnostics.get(_DIAG_KEY[feature], {})
    degraded = bool(diag.get("degraded"))
    ok = got == expect
    err = (
        ""
        if ok
        else (f"scheme={got!r} expected={expect!r}" + (f" degraded={diag.get('degrade_reason')}" if degraded else ""))
    )
    return VariantResult(
        feature=feature,
        label=label,
        ok=ok,
        scheme=got,
        expect=expect,
        degraded=degraded,
        error=err,
        engine_config=dict(out.engine_params.engine_config or {}),
        envs=dict(out.engine_params.env or {}),
        packages=list(out.packages or []),
        pre_serve=list(out.pre_serve or []),
        pre_serve_master=list(out.pre_serve_master or []),
        pre_serve_client=list(out.pre_serve_client or []),
    )


def _as_scheme_list(block: Any) -> List[Dict[str, Any]]:
    """decoding/sparse/kv_offload 块兼容两种写法:list 直接序列;dict 取 methods。"""
    if isinstance(block, list):
        return [s for s in block if isinstance(s, dict)]
    if isinstance(block, dict):
        methods = block.get("methods")
        return [s for s in methods if isinstance(s, dict)] if isinstance(methods, list) else []
    return []


def _test_decoding(base: SmartAccelInput) -> List[VariantResult]:
    """投机:逐 method 隔离;model_based 给 stub 草稿路径,no_model 留空。"""
    out: List[VariantResult] = []
    for m in _as_scheme_list((base.smart_accel or {}).get("decoding")):
        name = str(m.get("name") or "?")
        inp = deepcopy(base)
        sa = inp.smart_accel
        sa["decoding"] = [m]
        sa["sparse"] = []
        sa["kv_offload"] = []
        sa["custom_features"] = []
        _disable_all_features(inp)
        if m.get("requires_model_path"):
            with _draft_stub(m) as stub:
                inp.smart_decoding_config = SmartDecodingConfig(enabled=True, model_path=stub)
                out.append(_run_one("decoding", name, inp, expect=name))
            continue
        inp.smart_decoding_config = SmartDecodingConfig(enabled=True, model_path="")
        out.append(_run_one("decoding", name, inp, expect=name))
    return out


def _test_sparse(base: SmartAccelInput) -> List[VariantResult]:
    """稀疏:逐 scheme 隔离,mode=scheme.name(精确命中,不触发降级)。"""
    out: List[VariantResult] = []
    for s in _as_scheme_list((base.smart_accel or {}).get("sparse")):
        name = str(s.get("name") or "?")
        inp = deepcopy(base)
        sa = inp.smart_accel
        sa["sparse"] = [s]
        sa["decoding"] = []
        sa["kv_offload"] = []
        sa["custom_features"] = []
        _disable_all_features(inp)
        inp.smart_kv_sparse_config = SmartKVSparseConfig(enabled=True, mode=name)
        out.append(_run_one("sparse", name, inp, expect=name))
    return out


def _offload_classifier(scheme: Dict[str, Any]) -> Tuple[str, bool, bool]:
    """按 connector + backend 分类卸载变体,返回 (标签, 需内存, 需磁盘)。

    native           = OffloadingConnector(vllm 原生 CPU 卸载)
    memcache/mooncake= AscendStoreConnector + backend:memcache/mooncake(内存方法,走 backend scheme)
    lmcache:disk/cpu_disk = LMCacheConnectorV1(CUDA lmcache;disk=纯磁盘,cpu_disk=内存+磁盘)
    lmcache-ascend   = LMCacheAscendConnectorV1Dynamic(ascend lmcache,内存方法)
    """
    kt = (scheme.get("cli_params") or {}).get("kv_transfer_config") or {}
    connector = kt.get("kv_connector") or ""
    extra = kt.get("kv_connector_extra_config") or {}
    backend = extra.get("backend") or ""
    name = str(scheme.get("name") or "")
    needs_disk = name in ("disk", "cpu_disk")
    if connector == "AscendStoreConnector":
        return (f"backend:{backend}" if backend else "backend:?", True, needs_disk)
    if connector == "LMCacheAscendConnectorV1Dynamic":
        return "lmcache-ascend", True, needs_disk
    if connector == "LMCacheConnectorV1":
        needs_mem = name in ("cpu", "cpu_disk")
        return (f"lmcache:{name}" if name else "lmcache"), needs_mem, needs_disk
    if connector == "OffloadingConnector":
        return "native", True, needs_disk  # 原生 cpu 纯内存(name=cpu);理论无 disk 形态
    return (f"other:{connector}" if connector else "other:?", True, needs_disk)


def _test_offload(base: SmartAccelInput) -> List[VariantResult]:
    """Test every offload scheme and validate its rendered GeneratedFile plans in memory."""
    results: List[VariantResult] = []
    base_tp = base.smart_kv_cache_config.tp_size or 1
    for scheme in _as_scheme_list((base.smart_accel or {}).get("kv_offload")):
        label, needs_mem, needs_disk = _offload_classifier(scheme)
        inp = deepcopy(base)
        selected = inp.smart_accel
        selected["kv_offload"] = [scheme]
        selected["decoding"] = []
        selected["sparse"] = []
        selected["custom_features"] = []
        _disable_all_features(inp)
        kv = SmartKVCacheConfig(
            enabled=True,
            memory_offload_enabled=needs_mem,
            memory_offload_size_mode=str(_MEM_CAPACITY_GB) if needs_mem else "",
            disk_offload_enabled=needs_disk,
            disk_capacity_gb=_DISK_CAPACITY_GB,
            disk_path=_DISK_PATH,
            tp_size=base_tp,
        )
        setattr(kv, "_memory_capacity_gb", _MEM_CAPACITY_GB if needs_mem else 0)
        inp.smart_kv_cache_config = kv
        expected = str(scheme.get("name") or "")
        results.append(_run_one("offload", label, inp, expect=expected))
    return results


def _test_distributed(base: SmartAccelInput) -> List[VariantResult]:
    """Mooncake standalone-store: 单独启用每个声明的 distributed scheme。"""
    results: List[VariantResult] = []
    for scheme in _as_scheme_list((base.smart_accel or {}).get("distributed_kv_offload")):
        inp = deepcopy(base)
        inp.smart_accel["distributed_kv_offload"] = [scheme]
        inp.smart_accel["decoding"] = []
        inp.smart_accel["sparse"] = []
        inp.smart_accel["kv_offload"] = []
        inp.smart_accel["custom_features"] = []
        _disable_all_features(inp)
        inp.distributed_kv_cache_config = DistributedKVCacheConfig(
            enabled=True,
            protocol="rdma",
            serving_config_id="matrix-test",
            local_buffer_size="1GB",
            memory_offload_enabled=True,
            memory_capacity_gb=_MEM_CAPACITY_GB,
        )
        results.append(_run_one("distributed", str(scheme.get("name") or "?"), inp, expect=str(scheme.get("name") or "")))
    return results


_FEATURE_TESTERS = {
    "decoding": _test_decoding,
    "sparse": _test_sparse,
    "offload": _test_offload,
    "distributed": _test_distributed,
}


def _run_matrix(yaml_path: Path, features: List[str]) -> Tuple[Optional[SmartAccelInput], List[VariantResult]]:
    """对单个模型 YAML 跑选定特性的全部变体。"""
    base = _load_base_input(yaml_path)
    if base is None:
        return None, []
    results: List[VariantResult] = []
    for feat in features:
        results.extend(_FEATURE_TESTERS[feat](base))
    return base, results


# ── 输出渲染 ──


def _result_line(r: VariantResult) -> str:
    tag = "OK  " if r.ok else "FAIL"
    msg = f"{r.feature}:{r.label}"
    if r.degraded:
        msg += " [degraded]"
    if r.scheme is not None:
        msg += f" -> scheme={r.scheme}"
    if r.error:
        msg += f"  ({r.error})"
    return f"  [{tag}] {msg}"


def _print_variant_detail(r: VariantResult, vol_tmp: str = "") -> None:
    """verbose:打印单个变体的完整渲染结果(含 pre_serve)。

    vol_tmp: offload 文件计划使用的临时路径根;pre_serve 命令里的该路径改写为生产卷 /shared-volume 便于阅读。
    """
    print(_result_line(r))
    if r.engine_config:
        print("        engine_config:")
        for k, v in r.engine_config.items():
            print(f"          {k}: {v}")
    if r.envs:
        print("        envs:")
        for k, v in r.envs.items():
            print(f"          {k}={v}")
    if r.packages:
        print(f"        packages: {r.packages}")
    if r.pre_serve:
        print("        pre_serve(所有节点):")
        for c in _to_canonical_volume(r.pre_serve, vol_tmp):
            print(f"          {c}")
    if r.pre_serve_master:
        print("        pre_serve_master(仅 master):")
        for c in _to_canonical_volume(r.pre_serve_master, vol_tmp):
            print(f"          {c}")
    if r.pre_serve_client:
        print("        pre_serve_client(仅 client):")
        for c in _to_canonical_volume(r.pre_serve_client, vol_tmp):
            print(f"          {c}")


def _print_matrix(
    yaml_path: Path, base: Optional[SmartAccelInput], results: List[VariantResult], verbose: bool, vol_tmp: str = ""
) -> None:
    rel = _relpath(yaml_path)
    model_name = base.model_config.model_name if base else "?"
    print(f"═══ {rel}  (model={model_name}) ═══")
    if not results:
        print("  (无 decoding/sparse/kv_offload 变体)")
        return
    if verbose:
        for r in results:
            _print_variant_detail(r, vol_tmp)
    else:
        for r in results:
            print(_result_line(r))
    n_ok = sum(1 for r in results if r.ok)
    print(f"  -> {n_ok}/{len(results)} ok")


def _relpath(p: Path) -> str:
    """相对 smart-accel 根的路径(更短、更易读);越界则原样。"""
    try:
        return str(p.relative_to(_SMART_ACCEL_ROOT))
    except ValueError:
        return str(p)


def _iter_yaml_files(dirs: List[str], filter_sub: Optional[str]) -> List[Path]:
    """枚举 smart-accel/<dir> 下所有模型 YAML(去重保序)。"""
    files: List[Path] = []
    seen = set()
    for d in dirs:
        root = _SMART_ACCEL_ROOT / d
        if not root.is_dir():
            print(f"[warn] 扫描目录不存在: {root}", file=sys.stderr)
            continue
        for yf in sorted(root.rglob("*.yaml")):
            if yf in seen:
                continue
            seen.add(yf)
            if filter_sub and filter_sub.lower() not in str(yf).lower():
                continue
            files.append(yf)
    return files


def _result_to_dict(yaml_path: Path, base: Optional[SmartAccelInput], results: List[VariantResult]) -> Dict[str, Any]:
    return {
        "yaml": _relpath(yaml_path),
        "model": base.model_config.model_name if base else None,
        "loaded": base is not None,
        "variants": [dataclasses.asdict(r) for r in results],
        "ok": sum(1 for r in results if r.ok),
        "total": len(results),
    }


def _run_scan(args, dirs: List[str]) -> int:
    """形态二-扫描:枚举模型,逐个跑矩阵,汇总。"""
    logging.getLogger().setLevel(logging.ERROR)  # 压制库内 INFO/WARN 噪音,异常由本脚本捕获

    files = _iter_yaml_files(dirs, args.filter)
    if not files:
        print(
            f"[error] 未找到模型 YAML(dirs={dirs}" + (f", filter={args.filter!r}" if args.filter else "") + ")",
            file=sys.stderr,
        )
        return 2

    features = args.feature or ["decoding", "sparse", "offload", "distributed"]
    if args.limit:
        files = files[: args.limit]

    # offload file plans use a temporary path root and are validated in memory
    tmpdir = tempfile.mkdtemp(prefix="smart_accel_io_")
    os.environ["SHARED_VOLUME_PATH"] = tmpdir

    if not args.json:
        print(f"扫描 smart-accel: {', '.join(dirs)}  ({len(files)} 个 YAML,features={features})")
        if args.verbose:
            print(f"offload file plan temporary root: {tmpdir}")
        print()

    all_results: List[Tuple[Path, Optional[SmartAccelInput], List[VariantResult]]] = []
    json_records: List[Dict[str, Any]] = []
    failures: List[Tuple[Path, VariantResult]] = []

    try:
        for idx, yf in enumerate(files, 1):
            base, results = _run_matrix(yf, features)
            all_results.append((yf, base, results))
            if args.json:
                json_records.append(_result_to_dict(yf, base, results))
            if not args.json:
                if args.verbose:
                    _print_matrix(yf, base, results, verbose=True, vol_tmp=tmpdir)
                elif not args.quiet:
                    n_ok = sum(1 for r in results if r.ok)
                    status = "OK  " if n_ok == len(results) else "FAIL"
                    feat_counts = ", ".join(
                        f"{f}={sum(1 for r in results if r.feature == f and r.ok)}/"
                        f"{sum(1 for r in results if r.feature == f)}"
                        for f in features
                    )
                    print(f"[{status}] {_relpath(yf)}  ({feat_counts})" + ("" if base else "  <load failed>"))
            for r in results:
                if not r.ok:
                    failures.append((yf, r))
            if not args.json and not args.quiet and idx % 50 == 0:
                print(f"  …已处理 {idx}/{len(files)}", file=sys.stderr)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if args.json:
        agg = _aggregate(all_results, features)
        print(
            json.dumps(
                {"scan_dirs": dirs, "features": features, "aggregate": agg, "models": json_records},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1 if agg["fail"] else 0

    # 失败详情
    if failures:
        print()
        print(f"═══ 失败变体 ({len(failures)}) ═══")
        for yf, r in failures:
            print(f"  {_relpath(yf)}")
            _print_variant_detail(r, vol_tmp=tmpdir)
    else:
        if not args.quiet:
            print()

    _print_summary(all_results, features)
    agg = _aggregate(all_results, features)
    return 1 if agg["fail"] else 0


def _aggregate(all_results, features) -> Dict[str, Any]:
    total = ok = 0
    per_feat: Dict[str, List[int]] = {f: [0, 0] for f in features}  # [ok, total]
    n_models = len(all_results)
    n_failed_models = 0
    for _yf, _base, results in all_results:
        model_bad = False
        for r in results:
            total += 1
            per_feat.setdefault(r.feature, [0, 0])[1] += 1
            if r.ok:
                ok += 1
                per_feat[r.feature][0] += 1
            else:
                model_bad = True
        if results and model_bad:
            n_failed_models += 1
    return {
        "models": n_models,
        "failed_models": n_failed_models,
        "variants": total,
        "pass": ok,
        "fail": total - ok,
        "per_feature": {f: {"pass": v[0], "total": v[1]} for f, v in per_feat.items()},
    }


def _print_summary(all_results, features) -> None:
    agg = _aggregate(all_results, features)
    print("═══ 汇总 ═══")
    print(
        f"  模型: {agg['models']}   变体: {agg['variants']}   "
        f"通过: {agg['pass']}   失败: {agg['fail']}   失败模型: {agg['failed_models']}"
    )
    print("  按特性(pass/total):")
    for f in features:
        s = agg["per_feature"].get(f, {"pass": 0, "total": 0})
        print(f"    {f:9s} {s['pass']}/{s['total']}")
    if agg["fail"] == 0:
        print("  ✓ 全部通过")


# ══════════════════════════════════════════════════════════════════
# 路径覆盖检查 —— 按特性/变体统计「哪些模型路径声明了它」
# ══════════════════════════════════════════════════════════════════


def _load_yaml(yf: Path) -> Dict[str, Any]:
    """轻量读取 YAML(只取 smart_accel 块,不做 SmartAccelInput 构造)。"""
    try:
        with open(yf) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _coverage(files: List[Path], features: List[str]) -> Dict[str, Dict[str, List[Path]]]:
    """按 特性 -> 变体标签 -> [声明该变体的路径] 汇总。

    decoding/sparse 变体标签 = scheme.name;offload 标签 = _offload_classifier(connector+backend)。
    一条路径声明多个变体(GLM-5.2 同时有 mooncake+memcache)时,分别计入各自变体。

    scenario 嵌套结构(对齐 wings_control,§1.1)后,smart_accel 按 topology 路由;此处直接读 yaml
    不经 loader,故取 standalone.strategies.{default} 子块(最全,包含资产支持的所有特性)统计覆盖。
    """
    from wings_accel.yaml_loader import _extract_strategy_features

    cov: Dict[str, Dict[str, List[Path]]] = {f: {} for f in features}
    for yf in files:
        sa_raw = (_load_yaml(yf) or {}).get("smart_accel") or {}
        # scenario 嵌套(wings_control 风格):取 standalone.strategies.{default} 的特性
        standalone = sa_raw.get("standalone") if isinstance(sa_raw, dict) else None
        sa = _extract_strategy_features(standalone) if standalone else {}
        if "decoding" in cov:
            for m in _as_scheme_list(sa.get("decoding")):
                cov["decoding"].setdefault(str(m.get("name") or "?"), []).append(yf)
        if "sparse" in cov:
            for s in _as_scheme_list(sa.get("sparse")):
                cov["sparse"].setdefault(str(s.get("name") or "?"), []).append(yf)
        if "offload" in cov:
            for s in _as_scheme_list(sa.get("kv_offload")):
                label, _, _ = _offload_classifier(s)
                cov["offload"].setdefault(label, []).append(yf)
    return cov


_FEAT_TITLE = {"decoding": "投机 decoding", "sparse": "稀疏 sparse", "offload": "卸载 offload", "distributed": "分布式 Mooncake"}


def _print_coverage(
    cov: Dict[str, Dict[str, List[Path]]], features: List[str], n_files: int, dirs: List[str], max_paths: int
) -> None:
    print("═══ 路径覆盖检查 ═══")
    print(f"目录: {', '.join(dirs)}   模型 YAML: {n_files}   特性: {features}")
    print()
    for f in features:
        variants = cov.get(f, {})
        distinct = {p for paths in variants.values() for p in paths}
        print(f"── {_FEAT_TITLE.get(f, f)}  ({len(variants)} 种变体, {len(distinct)} 路径声明) ──")
        if not variants:
            print("  (无)")
            print()
            continue
        for label in sorted(variants, key=lambda k: (-len(variants[k]), k)):
            paths = variants[label]
            print(f"  {label:24s} {len(paths):4d} 路径")
            shown = paths if max_paths <= 0 else paths[:max_paths]
            for p in shown:
                print(f"      {_relpath(p)}")
            if max_paths > 0 and len(paths) > max_paths:
                print(f"      …还有 {len(paths) - max_paths} 个(用 --max-paths 0 查看全部)")
        print()


def _coverage_to_json(cov, features, n_files, dirs) -> Dict[str, Any]:
    out: Dict[str, Any] = {"dirs": dirs, "files": n_files, "features": features}
    cov_out = {}
    for f in features:
        variants = cov.get(f, {})
        distinct = {p for paths in variants.values() for p in paths}
        cov_out[f] = {
            "variant_count": len(variants),
            "distinct_paths": len(distinct),
            "variants": {
                label: {"count": len(paths), "paths": [_relpath(p) for p in paths]}
                for label, paths in sorted(variants.items(), key=lambda kv: (-len(kv[1]), kv[0]))
            },
        }
    out["coverage"] = cov_out
    return out


def _run_coverage(args, dirs: List[str]) -> int:
    """路径覆盖检查:不跑 func_smart_accel,只统计各变体被哪些路径声明。"""
    files = _iter_yaml_files(dirs, args.filter)
    if not files:
        print(
            f"[error] 未找到模型 YAML(dirs={dirs}" + (f", filter={args.filter!r}" if args.filter else "") + ")",
            file=sys.stderr,
        )
        return 2
    features = args.feature or ["decoding", "sparse", "offload", "distributed"]
    cov = _coverage(files, features)
    if args.json:
        print(json.dumps(_coverage_to_json(cov, features, len(files), dirs), indent=2, ensure_ascii=False))
    else:
        _print_coverage(cov, features, len(files), dirs, args.max_paths)
    return 0


# ══════════════════════════════════════════════════════════════════
# 样本存档 —— 每种变体取一条代表路径,把完整渲染输出写成 markdown 供审阅
# ══════════════════════════════════════════════════════════════════

_SAMPLE_HEADER = (
    "# {title} — 变体输出样本\n\n"
    "> 由 `smart_accel_io.py --save-samples` 生成。每个变体取一条**代表性模型路径**,"
    "隔离测试(仅开该特性 + 该变体)后 `func_smart_accel` 的完整输出。\n"
    "> 测试用占位输入:草稿路径=临时 stub 目录(本地目录契约,样本中统一展示为"
    "`/dummy/draft-model`)、内存卸载容量=128 GB、磁盘=512 GB @ `/var/cache/lmcache`。\n"
    "> offload 的 `files:` 仅生成并校验文件计划；此处展示生成的 pre_serve 命令与 env/cli。\n\n"
)


def _anchor(label: str) -> str:
    """markdown 锚点:非字母数字 → '-',小写。"""
    return "".join(c if c.isalnum() else "-" for c in label.lower()).strip("-")


def _to_canonical_volume(cmds: List[str], vol_tmp: str) -> List[str]:
    """把 pre_serve 命令里的临时卷路径改写为生产卷 /shared-volume(仅用于样本文档可读性)。"""
    if not vol_tmp:
        return cmds
    return [c.replace(vol_tmp, "/shared-volume") for c in cmds]


# 样本文档固定展示值:每次运行生成的 /tmp/draft-stub-* 路径统一改写,保证样例可复现
_DRAFT_STUB_DISPLAY = "/dummy/draft-model"
_DRAFT_STUB_RE = re.compile(r"/tmp/draft-stub-[^\s\"']+")


def _to_canonical_draft(value: Any) -> Any:
    """递归把样本文档里的临时 stub 草稿路径改写为固定展示值(仅可读性,不影响校验)。"""
    if isinstance(value, str):
        return _DRAFT_STUB_RE.sub(_DRAFT_STUB_DISPLAY, value)
    if isinstance(value, list):
        return [_to_canonical_draft(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_canonical_draft(v) for k, v in value.items()}
    return value


def _fmt_variant_section(label: str, count: int, rep: Path, r: Optional[VariantResult], vol_tmp: str = "") -> str:
    """单个变体的 markdown 段落(代表路径 + 完整渲染输出)。

    vol_tmp: offload 文件计划使用的临时路径根;pre_serve 命令里的该路径会被改写为生产卷
    ``/shared-volume``,使样本文档展示的是「实际会生成」的命令,而非已删除的临时目录。
    """
    lines = [f"## `{label}`  ({count} 路径)", ""]
    if r is None:
        lines += [f"- **代表路径:** `{_relpath(rep)}`", "- **结果:** 未产出(无匹配变体)", "", "---", ""]
        return "\n".join(lines)
    status = f"`{r.scheme}` (预期 `{r.expect}`) ✓" if r.ok else f"`{r.scheme}` (预期 `{r.expect}`) ✗ {r.error}"
    lines.append(f"- **代表路径:** `{_relpath(rep)}`")
    lines.append(f"- **选中 scheme:** {status}")
    lines.append(f"- **降级:** {'是 — ' + r.error if r.degraded else '无'}")
    if r.engine_config:
        lines += [
            "",
            "**engine_config:**",
            "```json",
            json.dumps(_to_canonical_draft(r.engine_config), indent=2, ensure_ascii=False),
            "```",
        ]
    if r.envs:
        lines += ["", "**envs:**", "```", "\n".join(f"{k}={v}" for k, v in _to_canonical_draft(r.envs).items()), "```"]
    if r.packages:
        lines += ["", f"**packages:** {', '.join(r.packages)}"]
    if r.pre_serve:
        lines += ["", "**pre_serve(所有节点):**", "```sh", "\n".join(_to_canonical_volume(r.pre_serve, vol_tmp)), "```"]
    if r.pre_serve_master:
        lines += [
            "",
            "**pre_serve_master(仅 master):**",
            "```sh",
            "\n".join(_to_canonical_volume(r.pre_serve_master, vol_tmp)),
            "```",
        ]
    if r.pre_serve_client:
        lines += [
            "",
            "**pre_serve_client(仅 client):**",
            "```sh",
            "\n".join(_to_canonical_volume(r.pre_serve_client, vol_tmp)),
            "```",
        ]
    lines += ["", "---", ""]
    return "\n".join(lines)


def _save_samples(args, dirs: List[str]) -> int:
    """每种变体取一条代表路径,把完整输出按特性写成 markdown 文档。"""
    logging.getLogger().setLevel(logging.ERROR)
    outdir = Path(args.save_samples)
    outdir.mkdir(parents=True, exist_ok=True)
    files = _iter_yaml_files(dirs, args.filter)
    if not files:
        print(
            f"[error] 未找到模型 YAML(dirs={dirs}" + (f", filter={args.filter!r}" if args.filter else "") + ")",
            file=sys.stderr,
        )
        return 2
    features = args.feature or ["decoding", "sparse", "offload", "distributed"]
    cov = _coverage(files, features)

    # offload file plans use a temporary path root and are validated in memory
    tmpdir = tempfile.mkdtemp(prefix="smart_accel_io_")
    os.environ["SHARED_VOLUME_PATH"] = tmpdir

    index = [
        "# 路径覆盖样本索引\n",
        "> 生成自 `smart_accel_io.py --save-samples`\n",
        f"> 目录: {', '.join(dirs)}   模型 YAML: {len(files)}\n",
    ]
    try:
        for f in features:
            variants = cov.get(f, {})
            md = [_SAMPLE_HEADER.format(title=_FEAT_TITLE.get(f, f))]
            index.append(f"\n## {_FEAT_TITLE.get(f, f)}({len(variants)} 变体)\n")
            for label in sorted(variants, key=lambda k: (-len(variants[k]), k)):
                paths = variants[label]
                rep = paths[0]
                _base, results = _run_matrix(rep, [f])
                r = next((x for x in results if x.label == label), None)
                md.append(_fmt_variant_section(label, len(paths), rep, r, vol_tmp=tmpdir))
                index.append(f"- [{label}](./{f}.md#{_anchor(label)}) — {len(paths)} 路径,代表 `{_relpath(rep)}`")
            (outdir / f"{f}.md").write_text("\n".join(md), encoding="utf-8")
            print(f"  写入 {outdir / f'{f}.md'}")
        (outdir / "INDEX.md").write_text("\n".join(index), encoding="utf-8")
        print(f"  写入 {outdir / 'INDEX.md'}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\n样本已保存至 {outdir}")
    return 0


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="func_smart_accel 验证:单 YAML 快照(形态一)或逐特性逐变体矩阵扫描(形态二)。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
形态一(单 YAML 快照):
  python3 tests/wings_accel/smart_accel_io.py <yaml>
  python3 tests/wings_accel/smart_accel_io.py <yaml> --json --print both
  python3 tests/wings_accel/smart_accel_io.py <yaml> --kv --disk --qat --memory-gb 128

形态二(逐特性逐变体):
  python3 tests/wings_accel/smart_accel_io.py <yaml> --matrix
  python3 tests/wings_accel/smart_accel_io.py --scan-all
  python3 tests/wings_accel/smart_accel_io.py --scan vllm-ascend --filter GLM-5.2 --verbose
  python3 tests/wings_accel/smart_accel_io.py --coverage --feature offload --max-paths 0
  python3 tests/wings_accel/smart_accel_io.py --save-samples tests/wings_accel/samples
        """,
    )
    parser.add_argument("yaml_path", nargs="?", help="模型 YAML 路径(形态一 / --matrix 必填)")

    # 形态二开关
    parser.add_argument("--matrix", action="store_true", help="对单个 YAML 跑全部特性变体(逐个隔离)")
    parser.add_argument(
        "--scan",
        nargs="*",
        default=None,
        metavar="DIR",
        help=f"扫描 smart-accel 下指定目录(默认 {DEFAULT_SCAN_DIRS});不带值=默认目录",
    )
    parser.add_argument("--scan-all", action="store_true", help=f"扫描 {DEFAULT_SCAN_DIRS} 全部模型(= --scan 不带值)")
    parser.add_argument(
        "--coverage", action="store_true", help="路径覆盖检查:按特性/变体统计哪些模型路径声明了它(不跑渲染)"
    )
    parser.add_argument(
        "--save-samples",
        metavar="DIR",
        default=None,
        help="每种变体取一条代表路径,把完整输出按特性写成 markdown(DIR 目录)",
    )
    parser.add_argument(
        "--feature", nargs="+", choices=["decoding", "sparse", "offload", "distributed"], help="只测指定特性(默认全部)"
    )
    parser.add_argument("--filter", default=None, help="路径子串过滤(不区分大小写)")
    parser.add_argument("--limit", type=int, default=0, help="最多扫描 N 个模型(0=不限)")
    parser.add_argument("--verbose", action="store_true", help="打印每个变体的完整渲染结果(含 pre_serve)")
    parser.add_argument("--quiet", action="store_true", help="扫描时只打印汇总(失败仍打印)")
    parser.add_argument("--max-paths", type=int, default=8, help="覆盖检查时每个变体最多列出 N 条路径(0=全部,默认 8)")
    # 形态一开关(legacy)
    parser.add_argument(
        "--print", choices=["input", "output", "both"], default="both", help="打印范围(默认 both,形态一)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--kv", action="store_true", help="启用 KVOffload(形态一)")
    parser.add_argument("--sparse", action="store_true", help="启用 SmartSparse(形态一)")
    parser.add_argument("--decoding-model-path", default="", help="投机解码草稿模型路径(形态一)")
    parser.add_argument("--sparse-level", default="performance_first", help="稀疏等级/模式(形态一)")
    parser.add_argument("--memory-offload-size-mode", default="", help="KV_MEM_OFFLOAD_SIZE:auto 或数值 GB(形态一)")
    parser.add_argument(
        "--pod-available-memory-gb", type=int, default=0, help="pod 总内存 GB(auto 模式估算输入,形态一)"
    )
    parser.add_argument("--disk", action="store_true", help="启用磁盘卸载(形态一)")
    parser.add_argument("--disk-gb", type=int, default=512, help="磁盘卸载容量 GB(默认 512,形态一)")
    parser.add_argument("--disk-path", default="/var/cache/lmcache", help="磁盘缓存目录(形态一)")
    parser.add_argument("--qat", action="store_true", help="启用 QAT 压缩(形态一)")
    parser.add_argument("--qat-devices", type=int, default=2, help="QAT 加速卡数量(形态一)")
    parser.add_argument("--qat-level", type=int, default=1, help="QAT 压缩等级 1=fast 3=best(形态一)")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    # 形态二:scan / coverage / save-samples / matrix
    if args.scan_all or args.scan is not None or args.coverage or args.save_samples:
        dirs = args.scan if (args.scan and len(args.scan) > 0) else DEFAULT_SCAN_DIRS
        if args.coverage:
            return _run_coverage(args, dirs)
        if args.save_samples:
            return _save_samples(args, dirs)
        return _run_scan(args, dirs)
    if args.matrix:
        if not args.yaml_path:
            raise SystemExit("--matrix 需要一个 YAML 路径")
        ypath = Path(args.yaml_path)
        if not ypath.is_file():
            raise SystemExit(f"YAML 不存在: {ypath}")
        features = args.feature or ["decoding", "sparse", "offload", "distributed"]
        # offload file plans use a temporary path root; displayed commands are normalized to /shared-volume
        tmpdir = tempfile.mkdtemp(prefix="smart_accel_io_")
        os.environ["SHARED_VOLUME_PATH"] = tmpdir
        try:
            base, results = _run_matrix(ypath, features)
            if args.json:
                print(json.dumps(_result_to_dict(ypath, base, results), indent=2, ensure_ascii=False))
            else:
                _print_matrix(ypath, base, results, verbose=True, vol_tmp=tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return 0 if all(r.ok for r in results) else 1

    # 形态一:legacy 单 YAML 快照
    if not args.yaml_path:
        raise SystemExit("需要 YAML 路径,或使用 --matrix / --scan / --scan-all / --coverage / --save-samples")
    return _legacy_main(args)


if __name__ == "__main__":
    sys.exit(main())
