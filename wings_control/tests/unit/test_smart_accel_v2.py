"""v2 加速块复用单测（refactor.md §6 + registry.md §6.3）。

覆盖：apply_smart_accel_v2 委托 wings_accel.load_smart_accel_from_yaml + func_smart_accel，
门控关闭 → no-op，模块缺失 → no-op，配置错误 → 上抛。

注：本模块 import 自 wings_ctl.accel.smart_accel（经 env_utils 依赖 fcntl），
仅 Linux 可运行；Windows 环境无法导入（既有环境限制）。
"""

from __future__ import annotations

import types

import pytest

from wings_ctl.accel.smart_accel_v2 import apply_smart_accel_v2
from wings_ctl.loaders.v2_loader import V2Asset


def _make_asset(tmp_path) -> V2Asset:
    path = tmp_path / "model.yaml"
    path.write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm\n"
        "  version: \"v0.30.0\"\n"
        "  hardware: [h20_141G]\n"
        "  model: M-bf16\n"
        "model:\n"
        "  name: M\n"
        "  variant_name: M-bf16\n"
        "smart_accel:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        decoding:\n"
        "        - name: mtp\n"
        "          cli_params:\n"
        "            speculative_config:\n"
        "              method: mtp\n"
        "          envs: {}\n",
        encoding="utf-8",
    )
    return V2Asset(
        path=path,
        profile={"engine": "vllm", "version": "v0.30.0", "hardware": {"h20_141G"}, "model": "M-bf16"},
        data={},
    )


def _stub_mod():
    """duck-typed 假 wings_accel 模块。"""
    mod = types.SimpleNamespace()

    def _load_smart_accel_from_yaml(yaml_path, flags=None):
        return types.SimpleNamespace(
            smart_accel={"decoding": [{"name": "mtp"}]},
            source_file=yaml_path,
        )

    def _func_smart_accel(smart_input):
        return types.SimpleNamespace(
            engine_params=types.SimpleNamespace(
                engine_config={"speculative_config": {"method": "mtp"}},
                env={},
            ),
            smart_decoding_scheme="mtp",
            smart_kv_sparse_scheme=None,
            smart_kv_cache_scheme=None,
            smart_distributed_kv_cache_scheme=None,
            diagnostics={},
            packages=[],
            pre_serve=[],
            pre_serve_master=[],
            pre_serve_client=[],
            pre_serve_trusted=None,
            generated_files=[],
            kv_mem_offload_size_gb=None,
            kv_disk_offload_path=None,
            mooncake_component_sources={},
            mooncake_script_assets_required=False,
            mooncake_master_section=[],
            mooncake_transfer_engine_package=None,
        )

    mod.load_smart_accel_from_yaml = _load_smart_accel_from_yaml
    mod.func_smart_accel = _func_smart_accel
    mod.LoadFlags = types.SimpleNamespace
    return mod


def test_apply_disabled_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr("wings_ctl.accel.smart_accel_v2._import_accel", _stub_mod)
    result = apply_smart_accel_v2(_make_asset(tmp_path), enabled=False)
    assert result.enabled is False
    assert result.engine_config == {}


def test_apply_module_absent_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr("wings_ctl.accel.smart_accel_v2._import_accel", lambda: None)
    result = apply_smart_accel_v2(_make_asset(tmp_path), enabled=True)
    assert result.enabled is False


def test_apply_with_stub(tmp_path, monkeypatch):
    monkeypatch.setattr("wings_ctl.accel.smart_accel_v2._import_accel", _stub_mod)
    result = apply_smart_accel_v2(_make_asset(tmp_path), enabled=True)
    assert result.enabled is True
    assert result.engine_config["speculative_config"]["method"] == "mtp"
    assert result.audit["smart_decoding_scheme"] == "mtp"


def test_apply_propagates_configuration_error(tmp_path, monkeypatch):
    class SmartAccelConfigurationError(ValueError):
        pass

    mod = _stub_mod()
    mod.SmartAccelConfigurationError = SmartAccelConfigurationError

    def _raise(smart_input):
        raise SmartAccelConfigurationError("bad asset")

    mod.func_smart_accel = _raise
    monkeypatch.setattr("wings_ctl.accel.smart_accel_v2._import_accel", lambda: mod)

    with pytest.raises(SmartAccelConfigurationError, match="bad asset"):
        apply_smart_accel_v2(_make_asset(tmp_path), enabled=True)
