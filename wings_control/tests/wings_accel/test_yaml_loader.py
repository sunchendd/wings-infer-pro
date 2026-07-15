"""yaml_loader 单测 — memory_offload_size_mode 智能内存分配 + pd_role 透传 + 扫描定位。"""

from pathlib import Path

import pytest

from wings_accel import func_smart_accel, resolve_smart_accel_from_config
from wings_accel.yaml_loader import (
    LoadFlags,
    build_smart_accel_yaml_path,
    find_smart_accel_yaml_path,
    load_smart_accel_from_config,
    load_smart_accel_from_yaml,
)


YAML_TEMPLATE = """
model:
  name: Test-Model
  model_id: test/model
  architecture: llama
hardware_profile:
  gpu_type: RTXPro5000
  gpu_count: 8
scenarios:
  standalone:
    strategies:
      default:
        default_strategy: true
        engine_config:
          engine: vllm
          version: "0.22.0"
          tensor_parallel_size: 4
          data_parallel_size: 2
smart_accel:
  kv_offload:
    - name: cpu
      cli_params:
        kv_transfer_config:
          kv_connector: OffloadingConnector
          kv_role: kv_both
"""


def _write_yaml(tmp_path, content):
    tmp_path = tmp_path if hasattr(tmp_path, 'mkdir') else Path(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "model.yaml"
    p.write_text(content)
    return str(p)


class TestMemoryOffloadSizeMode:
    def test_auto_enables_with_sufficient_pod(self, tmp_path):
        """256G pod, TP4×DP2=8 workers → engine_self=59, margin=25.6, available=171"""
        path = _write_yaml(tmp_path, YAML_TEMPLATE)
        flags = LoadFlags(
            kv=True,
            memory_offload_size_mode="auto",
            pod_available_memory_gb=256,
            min_offload_threshold_gb=100,
        )
        smart_input = load_smart_accel_from_yaml(path, flags)
        cfg = smart_input.smart_kv_cache_config
        assert cfg.memory_offload_enabled is True
        assert getattr(cfg, "_memory_capacity_gb") == 171

    def test_auto_disables_below_threshold(self, tmp_path):
        """100G pod → available=31G < 100G threshold → memory offload off"""
        path = _write_yaml(tmp_path, YAML_TEMPLATE)
        flags = LoadFlags(
            kv=True,
            memory_offload_size_mode="auto",
            pod_available_memory_gb=100,
            min_offload_threshold_gb=100,
        )
        smart_input = load_smart_accel_from_yaml(path, flags)
        cfg = smart_input.smart_kv_cache_config
        assert cfg.memory_offload_enabled is False

    def test_auto_dp_doubles_overhead(self, tmp_path):
        """DP2 → 8 workers, vs DP1 → 4 workers;available 相差 28G(4 worker × 7G)"""
        yaml_dp1 = YAML_TEMPLATE.replace("data_parallel_size: 2", "data_parallel_size: 1")
        path_dp1 = _write_yaml(tmp_path / "dp1", yaml_dp1)
        path_dp2 = _write_yaml(tmp_path / "dp2", YAML_TEMPLATE)

        flags = LoadFlags(kv=True, memory_offload_size_mode="auto", pod_available_memory_gb=512)
        inp1 = load_smart_accel_from_yaml(path_dp1, flags)
        inp2 = load_smart_accel_from_yaml(path_dp2, flags)
        # DP1: 512 - (3+7*4) - 51.2 = 429.8 → 429; DP2: 512 - (3+7*8) - 51.2 = 401.8 → 401
        assert getattr(inp1.smart_kv_cache_config, "_memory_capacity_gb") == 429
        assert getattr(inp2.smart_kv_cache_config, "_memory_capacity_gb") == 401

    def test_manual_uses_fixed_memory_gb(self, tmp_path):
        """manual 模式 → 用 flags.memory_gb 静态值"""
        path = _write_yaml(tmp_path, YAML_TEMPLATE)
        flags = LoadFlags(kv=True, memory_offload_size_mode="128")
        smart_input = load_smart_accel_from_yaml(path, flags)
        assert getattr(smart_input.smart_kv_cache_config, "_memory_capacity_gb") == 128

    def test_numeric_memory_size_uses_fixed_gb(self, tmp_path):
        """KV_MEM_OFFLOAD_SIZE 数值字符串 → manual + 固定 GB。"""
        path = _write_yaml(tmp_path, YAML_TEMPLATE)
        flags = LoadFlags(kv=True, memory_offload_size_mode="192")
        smart_input = load_smart_accel_from_yaml(path, flags)
        cfg = smart_input.smart_kv_cache_config
        assert cfg.memory_offload_size_mode == "192"
        assert getattr(cfg, "_memory_capacity_gb") == 192


class TestPdRole:
    def test_pd_role_prefill_wired(self, tmp_path):
        path = _write_yaml(tmp_path, YAML_TEMPLATE)
        flags = LoadFlags(pd_role="prefill")
        smart_input = load_smart_accel_from_yaml(path, flags)
        assert smart_input.deployment_mode.pd_role == "prefill"

    def test_pd_role_decode_wired(self, tmp_path):
        path = _write_yaml(tmp_path, YAML_TEMPLATE)
        flags = LoadFlags(pd_role="decode")
        smart_input = load_smart_accel_from_yaml(path, flags)
        assert smart_input.deployment_mode.pd_role == "decode"

    def test_pd_role_none_by_default(self, tmp_path):
        path = _write_yaml(tmp_path, YAML_TEMPLATE)
        smart_input = load_smart_accel_from_yaml(path)
        assert smart_input.deployment_mode.pd_role is None


def test_default_model_yaml_not_merged(tmp_path):
    """default_model.yaml 不被读取:smart_accel 只取自 model yaml 本身。"""
    models_dir = tmp_path / "models"
    model_dir = models_dir / "MyModel"
    model_dir.mkdir(parents=True)
    (models_dir / "default_model.yaml").write_text(
        "smart_accel:\n  kv_offload:\n    - name: cpu\n      cli_params: {x: 1}\n",
        encoding="utf-8",
    )
    (model_dir / "model.yaml").write_text(
        "model:\n  name: M\n  model_id: m\n  architecture: llama\n",
        encoding="utf-8",
    )
    smart_input = load_smart_accel_from_yaml(str(model_dir / "model.yaml"))
    assert "kv_offload" not in smart_input.smart_accel
    assert smart_input.smart_kv_cache_config.enabled is False


def test_load_smart_accel_from_config_uses_smart_accel_tree(tmp_path):
    """按 smart-accel/{engine}/v{version}/{hw}/models 扫描匹配。"""
    yaml_path = tmp_path / "smart-accel" / "vllm" / "v0.23.0" / "rtx_pro_5000_48G" / "models" / "M" / "M.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(YAML_TEMPLATE, encoding="utf-8")

    assert build_smart_accel_yaml_path(
        tmp_path, "vllm", "0.23.0", "rtx_pro_5000_48G", "M", "M.yaml",
    ) == yaml_path
    smart_input = load_smart_accel_from_config(tmp_path, "vllm", "v0.23.0", "rtx_pro_5000_48G", "M")
    # new:list 形式,cpu scheme 在 cli_params.kv_transfer_config.kv_connector
    cpu = smart_input.smart_accel["kv_offload"][0]
    assert cpu["cli_params"]["kv_transfer_config"]["kv_connector"] == "OffloadingConnector"


def test_resolve_smart_accel_from_config_self_contained(tmp_path):
    """独立接口仅靠入参+smart-accel 配置完成输入构造、解析与输出返回。"""
    yaml_path = tmp_path / "smart-accel" / "vllm" / "v0.23.0" / "h200" / "models" / "M" / "M.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(YAML_TEMPLATE, encoding="utf-8")

    out = resolve_smart_accel_from_config(
        config_root=tmp_path, engine="vllm", engine_version="0.23.0",
        hardware_family="h200", model_name="M",
        flags=LoadFlags(kv=True, memory_offload_size_mode="64"),
    )
    assert out is not None
    assert out.smart_kv_cache_scheme is not None


def test_load_smart_accel_from_config_missing_returns_none(tmp_path):
    """硬件目录或模型 YAML 缺失 → 返回 None,调用方 no-op。"""
    assert load_smart_accel_from_yaml(str(tmp_path / "missing.yaml")) is None
    assert load_smart_accel_from_config(tmp_path, "vllm", "v0.23.0", "rtx_pro_5000_48G", "MissingModel") is None


def test_scanner_matches_model_pattern(tmp_path):
    """扫描时优先按 model.match[].name_pattern 匹配模型名。"""
    yaml_path = tmp_path / "smart-accel" / "vllm" / "v0.23.0" / "h200" / "models" / "Alias" / "alias.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(
        YAML_TEMPLATE.replace(
            "model:\n  name: Test-Model",
            "model:\n  match:\n    - name_pattern: 'Qwen.*72B'\n  name: Test-Model",
        ),
        encoding="utf-8",
    )
    assert find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "Qwen3-72B") == yaml_path


def test_scanner_ambiguous_raises(tmp_path):
    """多个 YAML 同时匹配同一模型名时显式报错。"""
    for model_dir in ("A", "B"):
        yaml_path = tmp_path / "smart-accel" / "vllm" / "v0.23.0" / "h200" / "models" / model_dir / f"{model_dir}.yaml"
        yaml_path.parent.mkdir(parents=True)
        yaml_path.write_text(
            YAML_TEMPLATE.replace(
                "model:\n  name: Test-Model",
                "model:\n  match:\n    - name_pattern: 'SameModel'\n  name: Test-Model",
            ),
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="Ambiguous SmartAccel YAML"):
        find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "SameModel")


# ── docs/48 同步:variant_name 精确优先 + name_pattern 模糊兜底 ────────────────

def _write_accel_yaml(tmp_path, model_dir, yaml_name, model_block_yaml, body="smart_accel: {}\n"):
    """在 smart-accel/vllm/v0.23.0/h200/models/{model_dir}/{yaml_name} 写一个 yaml。"""
    p = tmp_path / "smart-accel" / "vllm" / "v0.23.0" / "h200" / "models" / model_dir / yaml_name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(model_block_yaml + body, encoding="utf-8")
    return p


def test_scanner_variant_name_exact_match(tmp_path):
    """① 发完整精度变体名 → variant_name 精确命中,不走正则(确定性主路径)。"""
    p = _write_accel_yaml(
        tmp_path, "M", "M.yaml",
        "model:\n  name: M\n  variant_name: 'M-fp8'\n  match:\n    - name_pattern: '(?i)m'\n",
    )
    assert find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "M-fp8") == p


def test_scanner_variant_name_case_insensitive(tmp_path):
    """① variant_name 精确匹配忽略大小写(MaaS 大小写漂移容错)。"""
    p = _write_accel_yaml(
        tmp_path, "M", "M.yaml",
        "model:\n  variant_name: 'Qwen3-72B'\n  match:\n    - name_pattern: 'nomatch'\n",
    )
    assert find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "qwen3-72b") == p


def test_scanner_variant_name_conflict_raises(tmp_path):
    """① 同目录两个文件声明同一 variant_name → 报错(可判别性被破坏)。"""
    for d in ("A", "B"):
        _write_accel_yaml(
            tmp_path, d, f"{d}.yaml",
            "model:\n  variant_name: 'Dup'\n  match:\n    - name_pattern: 'nomatch'\n",
        )
    with pytest.raises(ValueError, match="variant_name 冲突"):
        find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "Dup")


def test_scanner_multi_variant_disambiguated_by_full_name(tmp_path):
    """多变体同家族 name_pattern:发家族名→②歧义报错;发完整变体名→①精确选中对应文件。"""
    fp8 = _write_accel_yaml(
        tmp_path, "Fam", "Fam-fp8.yaml",
        "model:\n  name: Fam\n  variant_name: 'Fam-fp8'\n  match:\n    - name_pattern: '(?i)fam'\n",
    )
    nvfp4 = _write_accel_yaml(
        tmp_path, "Fam", "Fam-nvfp4.yaml",
        "model:\n  name: Fam\n  variant_name: 'Fam-nvfp4'\n  match:\n    - name_pattern: '(?i)fam'\n",
    )
    # 发家族名 → 两文件 name_pattern 都命中 → 歧义报错(要全名)
    with pytest.raises(ValueError, match="Ambiguous SmartAccel YAML"):
        find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "Fam")
    # 发完整变体名 → 精确层选中对应文件(即便另一文件宽 name_pattern 也命中,精确层优先)
    assert find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "Fam-nvfp4") == nvfp4
    assert find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "Fam-fp8") == fp8


def test_scanner_stem_fallback_when_no_variant_no_pattern(tmp_path):
    """③ 无 variant_name + 无 name_pattern → 目录名/stem 精确兜底(存量单变体向后兼容)。"""
    p = _write_accel_yaml(tmp_path, "Solo", "Solo-bf16.yaml", "")  # 完全无 model 块
    assert find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "Solo-bf16") == p  # stem
    assert find_smart_accel_yaml_path(tmp_path, "vllm", "0.23.0", "h200", "Solo") == p        # 目录名


def test_load_flags_new_fields(tmp_path):
    """decoding_model_path / sparse_level / memory_offload_size_mode 映射到输入。"""
    path = _write_yaml(tmp_path, YAML_TEMPLATE + "  sparse:\n    - name: performance_first\n      cli_params: {}\n")
    flags = LoadFlags(
        decoding_model_path="/draft",
        sparse_level="accuracy_first",
        memory_offload_size_mode="false",
        pod_available_memory_gb=512,
    )
    smart_input = load_smart_accel_from_yaml(path, flags)
    assert smart_input.smart_decoding_config.model_path == "/draft"
    assert smart_input.smart_kv_sparse_config.mode == "accuracy_first"
    assert smart_input.smart_kv_cache_config.memory_offload_enabled is False
    assert smart_input.smart_kv_cache_config.memory_offload_size_mode == ""
    assert smart_input.hardware_config.pod_available_memory_gb == 512


def test_memory_override_true_requires_cpu_scheme(tmp_path):
    """显式 memory_on 仍要求 YAML 存在 cpu scheme,避免无介质产出。"""
    path = _write_yaml(
        tmp_path,
        "model:\n  name: M\n  model_id: m\n  architecture: llama\n"
        "smart_accel:\n  kv_offload:\n    - name: disk\n      cli_params: {}\n",
    )
    smart_input = load_smart_accel_from_yaml(path, LoadFlags(kv=True, memory_offload_size_mode="auto"))
    assert smart_input.smart_kv_cache_config.memory_offload_enabled is False


def test_offload_no_media_returns_none(tmp_path):
    """主开关开但 yaml 无 cpu/disk scheme → offload 返回 None。"""
    model_dir = tmp_path / "MyModel"
    model_dir.mkdir(parents=True)
    (model_dir / "model.yaml").write_text(
        "model:\n  name: M\n  model_id: m\n  architecture: llama\n"
        "smart_accel:\n  kv_offload: []\n",
        encoding="utf-8",
    )
    smart_input = load_smart_accel_from_yaml(str(model_dir / "model.yaml"), LoadFlags(kv=True))
    # kv 显式 enable(flags.kv=True),但 yaml 无 cpu/disk scheme → memory/disk_offload 关
    assert smart_input.smart_kv_cache_config.enabled is True
    assert smart_input.smart_kv_cache_config.memory_offload_enabled is False
    out = func_smart_accel(smart_input)
    assert out.smart_kv_cache_scheme is None  # 无介质 → None
