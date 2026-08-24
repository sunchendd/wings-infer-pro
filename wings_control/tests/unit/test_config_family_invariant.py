"""config 硬件目录不变量:同一 engine[/version] 下,同型号不许"裸目录"与"带 _<N>G 后缀目录"并存。

为什么守这条:locator.resolve_family_dir 用"剥后缀兜底"把普通卡的冗余显存后缀去掉后命中裸目录
(如 H100_80G → h100)。若某型号同时存在裸目录和后缀目录(如 h20 与 h20_96G 并存),一个不存在的
显存档(h20_80G)会被剥后缀静默坍缩到裸 h20,用错 recipe。这条断言防 config 未来违反该前提。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator

import yaml

from wings_ctl.hardware.resolver import strip_gpu_mem_suffix


def _family_parents(engines_dir: Path) -> set[Path]:
    """收集所有"直接含 hardware_family 目录(其下有 models/)"的父目录。

    Args:
        engines_dir: config/engines 目录。

    Returns:
        父目录集合(= engines/{engine} 或 engines/{engine}/v{version})。
    """
    parents: set[Path] = set()
    for models_dir in engines_dir.rglob("models"):
        if models_dir.is_dir():
            parents.add(models_dir.parent.parent)  # {parent}/{family}/models → {parent}
    return parents


def _engine_config_mappings(value: Any) -> Iterator[dict[str, Any]]:
    """递归返回 YAML 资产中所有 ``engine_config`` mapping。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "engine_config" and isinstance(nested, dict):
                yield nested
            yield from _engine_config_mappings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _engine_config_mappings(nested)


def _contains_mtp(value: Any) -> bool:
    """递归判断 YAML 是否声明 mtp/deepseek_mtp 投机方法。"""
    if isinstance(value, dict):
        if value.get("method") in {"mtp", "deepseek_mtp"}:
            return True
        return any(_contains_mtp(nested) for nested in value.values())
    if isinstance(value, list):
        return any(_contains_mtp(nested) for nested in value)
    if isinstance(value, str):
        return bool(re.search(r'["\']method["\']\s*:\s*["\'](?:deepseek_)?mtp["\']', value))
    return False


def _model_patterns(data: Any) -> list[str]:
    """提取 model.match 下的 name_pattern。"""
    if not isinstance(data, dict):
        return []
    model = data.get("model")
    if not isinstance(model, dict):
        return []
    rules = model.get("match")
    if not isinstance(rules, list):
        return []
    return [
        rule["name_pattern"]
        for rule in rules
        if isinstance(rule, dict) and isinstance(rule.get("name_pattern"), str)
    ]


def _model_variant_keys(root: Path) -> set[tuple[str, str, str]]:
    """收集 ``(version, hardware, variant_name)`` 资产身份。"""
    keys: set[tuple[str, str, str]] = set()
    for path in root.glob("v*/*/models/*/*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        model = data.get("model") if isinstance(data, dict) else None
        if not isinstance(model, dict):
            continue
        variant_name = model.get("variant_name")
        if isinstance(variant_name, str) and variant_name.strip():
            keys.add((path.parts[-5], path.parts[-4], variant_name.strip().casefold()))
    return keys


def test_config_family_dir_no_bare_and_suffixed_collision(config_root_real):
    """真实 config:任一 engine[/version] 下,带 _<N>G 后缀目录的裸型号名不得也是一个裸目录。"""
    violations: list[str] = []
    for parent in sorted(_family_parents(config_root_real / "engines")):
        families = [c.name for c in parent.iterdir() if (c / "models").is_dir()]
        bare = {f.casefold() for f in families if strip_gpu_mem_suffix(f) == f}
        for f in families:
            if strip_gpu_mem_suffix(f) != f:  # 该目录带显存后缀
                base = strip_gpu_mem_suffix(f).casefold()
                if base in bare:
                    violations.append(f"{parent.name}: '{f}' 与裸目录 '{base}' 并存")
    assert not violations, (
        "config 硬件目录不变量被破坏(同型号裸目录 + 后缀目录并存 → 剥后缀会静默坍缩):\n"
        + "\n".join(violations)
    )


def test_vllm_flashinfer_kernel_config_uses_native_dotted_key(config_root_real):
    """vLLM 资产禁用 FlashInfer autotune 时必须使用原生嵌套 CLI 配置形式。

    ``kernel_config_enable_flashinfer_autotune: false`` 是扁平普通 bool key，会被通用渲染规则
    当成关闭的顶层开关而省略；原生 vLLM 参数应为
    ``--kernel-config.enable_flashinfer_autotune=False``，故 YAML 必须保存 dotted key 和精确的
    字符串字面值 ``"False"``。
    """
    legacy_entries: list[str] = []
    invalid_native_entries: list[str] = []
    for path in sorted((config_root_real / "engines" / "vllm").rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for engine_config in _engine_config_mappings(data):
            if "kernel_config_enable_flashinfer_autotune" in engine_config:
                legacy_entries.append(str(path))
            if (
                "kernel_config.enable_flashinfer_autotune" in engine_config
                and engine_config["kernel_config.enable_flashinfer_autotune"] != "False"
            ):
                invalid_native_entries.append(str(path))

    assert not legacy_entries, (
        "vLLM YAML 仍含扁平 FlashInfer kernel 配置;应改为 "
        "kernel_config.enable_flashinfer_autotune: \"False\":\n"
        + "\n".join(legacy_entries)
    )
    assert not invalid_native_entries, (
        "vLLM native FlashInfer kernel 配置必须使用字符串字面值 \"False\":\n"
        + "\n".join(invalid_native_entries)
    )


def test_deepseek_mtp_assets_do_not_match_unsupported_models(config_root_real):
    """声明 MTP 的 DeepSeek 资产不得匹配已知不支持 MTP 的 Coder/Distill 模型。"""
    unsupported_models = (
        "DeepSeek-Coder-V2-Instruct",
        "DeepSeek-R1-Distill-Qwen-1.5B",
        "DeepSeek-R1-Distill-Qwen-7B",
        "DeepSeek-R1-Distill-Qwen-14B",
        "DeepSeek-R1-Distill-Qwen-32B",
        "DeepSeek-R1-Distill-Llama-8B",
        "DeepSeek-R1-Distill-Llama-70B",
    )
    roots = (
        config_root_real / "engines",
        Path(__file__).resolve().parents[2] / "src" / "wings_accel" / "smart-accel",
    )
    violations: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*.yaml")):
            if "deepseek" not in str(path).casefold():
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not _contains_mtp(data):
                continue
            for pattern in _model_patterns(data):
                matched = [name for name in unsupported_models if re.search(pattern, name)]
                if matched:
                    violations.append(f"{path}: {pattern!r} -> {', '.join(matched)}")

    assert not violations, (
        "以下 DeepSeek YAML 声明了 MTP，却会匹配不支持 MTP 的 Coder/Distill 模型:\n"
        + "\n".join(violations)
    )


def _model_variant_keys_by_hardware(root: Path) -> set[tuple[str, str]]:
    """收集 ``(hardware, variant_name)`` 资产身份(跨版本合并)。

    vLLM engine 目录无版本维度(``{hardware}/models/...``),而 smart-accel 有
    (``v{version}/{hardware}/models/...``),故对比时以 ``(hardware, variant_name)``
    为键,并跨 smart-accel 所有版本目录合并。
    """
    keys: set[tuple[str, str]] = set()
    for path in root.glob("**/models/*/*.yaml"):
        parts = path.parts
        try:
            models_idx = parts.index("models")
        except ValueError:
            continue
        hardware = parts[models_idx - 1]
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        model = data.get("model") if isinstance(data, dict) else None
        if not isinstance(model, dict):
            continue
        variant_name = model.get("variant_name")
        if isinstance(variant_name, str) and variant_name.strip():
            keys.add((hardware, variant_name.strip().casefold()))
    return keys


def test_vllm_ascend_engine_variants_have_smart_assets(config_root_real):
    """每个 vLLM-Ascend engine variant 必须有同版本、同硬件、同身份的 SmartAccel 资产。"""
    engine_keys = _model_variant_keys(config_root_real / "engines" / "vllm-ascend")
    smart_root = Path(__file__).resolve().parents[2] / "src" / "wings_accel" / "smart-accel" / "vllm-ascend"
    smart_keys = _model_variant_keys(smart_root)
    engine_only = sorted(engine_keys - smart_keys)

    assert not engine_only, (
        "以下 vLLM-Ascend engine variant 缺少同版本、同硬件、同身份的 SmartAccel 资产：\n"
        + "\n".join(map(str, engine_only))
    )


def test_vllm_engine_variants_have_smart_assets(config_root_real):
    """每个 vLLM engine variant 必须有同硬件、同身份的 SmartAccel 资产。

    vLLM engine 目录无版本维度(``config/engines/vllm/{hardware}/models/...``),
    smart-accel 有版本维度(``smart-accel/vllm/v{version}/{hardware}/models/...``),
    故以 ``(hardware, variant_name)`` 为键对比,并跨 smart-accel 所有版本合并。
    """
    engine_keys = _model_variant_keys_by_hardware(config_root_real / "engines" / "vllm")
    smart_root = Path(__file__).resolve().parents[2] / "src" / "wings_accel" / "smart-accel" / "vllm"
    smart_keys = _model_variant_keys_by_hardware(smart_root)
    engine_only = sorted(engine_keys - smart_keys)

    assert not engine_only, (
        "以下 vLLM engine variant 缺少同硬件、同身份的 SmartAccel 资产：\n"
        + "\n".join(map(str, engine_only))
    )
