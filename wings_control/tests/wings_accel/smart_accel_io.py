#!/usr/bin/env python3
"""
func_smart_accel 快速验证脚本 — 用 YAML 或 CLI flags 构造 SmartAccelInput,
打印 SmartAccelInput 与 SmartAccelOutput,用于人工/CI 验证流水线。

注意:生产/集成入口不是本脚本,而是直接调用
func_smart_accel(smart_input: SmartAccelInput) -> SmartAccelOutput。
本脚本只是为了快速从 YAML 构造输入并观察输出;两种入口都需要长期支持。

用法:
    # 默认: 同时打印 input + output
    python3 tests/wings_accel/smart_accel_io.py tests/wings_accel/fixtures/smart_accel_all_features.yaml

    # 仅看输入(loader 调试)
    python3 tests/wings_accel/smart_accel_io.py <yaml> --print input

    # JSON 输出(适合 golden/diff)
    python3 tests/wings_accel/smart_accel_io.py <yaml> --json --print both

    # 显式覆盖 flags
    python3 tests/wings_accel/smart_accel_io.py <yaml> --kv --disk --qat --memory-gb 128

选项与 LoadFlags 一致。
"""

import argparse
import dataclasses
import json
import sys

sys.path.append("src")

from wings_accel import func_smart_accel, load_smart_accel_from_yaml, LoadFlags


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
        print(f"           memory_offload={kv.memory_offload_enabled}"
              f"  memory_offload_size_mode={kv.memory_offload_size_mode or '-'}"
              f"  capacity_gb={getattr(kv, '_memory_capacity_gb', 0)}")
        print(f"           disk_offload={kv.disk_offload_enabled}"
              f"  capacity_gb={kv.disk_capacity_gb}"
              f"  path={kv.disk_path or '-'}")
        print(f"           qat={kv.qat_enabled}"
              f"  devices={kv.qat_device_count}"
              f"  level={kv.qat_compression_level}")


def _print_output(out) -> None:
    print()
    print("════════════════ SmartAccelOutput ════════════════")

    print("\n── Schemes ──")
    _print_params({
        "smart_decoding_scheme": out.smart_decoding_scheme,
        "smart_kv_sparse_scheme": out.smart_kv_sparse_scheme,
        "smart_kv_cache_scheme": out.smart_kv_cache_scheme,
    })

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


def main():
    parser = argparse.ArgumentParser(
        description="Test func_smart_accel input/output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 默认: 打印输入与输出
  python3 tests/wings_accel/smart_accel_io.py tests/wings_accel/fixtures/smart_accel_all_features.yaml

  # 仅打印输入(loader 调试)
  python3 tests/wings_accel/smart_accel_io.py <yaml> --print input

  # JSON 格式(适合 golden/diff)
  python3 tests/wings_accel/smart_accel_io.py <yaml> --json > out.json

  # 显式 flags
  python3 tests/wings_accel/smart_accel_io.py <yaml> --kv --disk --qat --memory-gb 128
        """,
    )
    parser.add_argument("yaml_path", help="模型 YAML 文件路径")
    parser.add_argument("--print", choices=["input", "output", "both"], default="both",
                        help="打印范围 (默认 both)")
    parser.add_argument("--json", action="store_true",
                        help="JSON 格式输出(便于 golden/diff)")
    parser.add_argument("--kv", action="store_true", help="启用 KVOffload")
    parser.add_argument("--sparse", action="store_true", help="启用 SmartSparse")
    parser.add_argument("--decoding-model-path", default="", help="投机解码草稿模型路径")
    parser.add_argument("--sparse-level", default="performance_first", help="稀疏等级/模式")
    parser.add_argument("--memory-offload-size-mode", default="",
                        help="KV_MEM_OFFLOAD_SIZE: auto 或数值 GB;不传表示不显式下发")
    parser.add_argument("--pod-available-memory-gb", type=int, default=0,
                        help="pod 总内存 GB(auto 模式估算输入)")
    parser.add_argument("--disk", action="store_true", help="启用磁盘卸载")
    parser.add_argument("--disk-gb", type=int, default=512, help="磁盘卸载容量 GB (默认 512)")
    parser.add_argument("--disk-path", default="/var/cache/lmcache", help="磁盘缓存目录")
    parser.add_argument("--qat", action="store_true", help="启用 QAT 压缩")
    parser.add_argument("--qat-devices", type=int, default=2, help="QAT 加速卡数量")
    parser.add_argument("--qat-level", type=int, default=1, help="QAT 压缩等级 1=fast 3=best")

    args = parser.parse_args()
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


if __name__ == "__main__":
    main()
