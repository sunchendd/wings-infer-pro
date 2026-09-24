"""SmartAccel 场景集合守护:必须是引擎 YAML 场景集合的子集。

虚构拓扑虽会被 config_resolver 先行拒绝(引擎未定义的场景直接报错),但资产
本身不应宣称引擎不支持的拓扑——后续引擎一旦补齐场景,未验证的加速参数会
自动生效。本测试锁定本批次触碰的资产,逐场景校验:

1. smart 场景集合 ⊆ 引擎 recipe 场景集合;
2. smart 场景 source_ref 与引擎侧同场景 source_ref 逐字一致(可追溯)。

引擎侧定位规则:按 variant 文件名 + 硬件目录在 config/engines/{engine} 树内
匹配(vllm 引擎配置无版本层,版本目录不参与定位)。
"""

import re
from pathlib import Path

import pytest
import yaml

from wings_accel.yaml_loader import LoadFlags

REPO_ROOT = Path(__file__).resolve().parents[2]
SMART_ROOT = REPO_ROOT / "src" / "wings_accel" / "smart-accel"
ENGINE_ROOT = REPO_ROOT / "config" / "engines"

# 本批次资产(相对 smart-accel 根)
ASSETS = [
    "vllm/kimi-k3/h20_141G/models/Kimi-K3/Kimi-K3.yaml",
    "vllm/deepseekv4-flash-vision/h20_141G/models/DeepSeek-V4-Flash-Vision-Exp/DeepSeek-V4-Flash-Vision-Exp.yaml",
    "vllm/v0.28.0/h20_141G/models/GLM5.3/GLM5.3.yaml",
    "vllm/v0.23.0/rtx_pro_5000_72G/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-fp8.yaml",
    "vllm/v0.28.0/rtx_pro_5000_72G/models/MiniMax-M3/MiniMax-M3-mxfp8.yaml",
    "vllm-ascend/v0.21.0rc/ascend-a2/models/DeepSeek-R1-0528/DeepSeek-R1-0528-w8a8-mtp-QuaRot.yaml",
    "vllm-ascend/v0.21.0rc/ascend-a2/models/DeepSeek-V3-0324/DeepSeek-V3-0324-w8a8-mtp-QuaRot.yaml",
    "vllm-ascend/v0.21.0rc/ascend-a3/models/Qwen3.6-35B-A3B/Qwen3.6-35B-A3B-bf16.yaml",
    "vllm-ascend/v0.23.0/ascend-a2/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-w8a8-mtp.yaml",
    "vllm-ascend/v0.23.0/ascend-a3/models/DeepSeek-V4-Flash/DeepSeek-V4-Flash-w8a8-mtp.yaml",
    "vllm-ascend/v0.23.0/ascend-a2/models/GLM-5.1/GLM-5.1-w4a8.yaml",
    "vllm-ascend/v0.23.0/ascend-a2/models/GLM-5.1/GLM-5.1-w8a8.yaml",
    "vllm-ascend/v0.23.0/ascend-a2/models/GLM-5/GLM-5-w4a8.yaml",
    "vllm-ascend/v0.23.0/ascend-a3/models/GLM-5.3/GLM-5.3-w8a8.yaml",
    "vllm-ascend/v0.23.0/ascend-a3/models/GLM-5.3-1M/GLM-5.3-w8a8-1M.yaml",
    "vllm-ascend/glm-5.3-flash-a3/ascend-a3/models/GLM-5.3-Flash/GLM-5.3-Flash-w8a8.yaml",
    "vllm-ascend/v0.26.0rc1/ascend-a3/models/GLM-5.3/GLM-5.3-w8a8c8.yaml",
    "vllm-ascend/v0.26.0rc1/ascend-a3/models/DeepSeek-V4-Pro/DeepSeek-V4-Pro-0813-w4a8.yaml",
    "vllm-ascend/v0.26.0rc1/ascend-a2/models/Qwen3.8-27B/Qwen3.8-27B-w8a8.yaml",
    "vllm-ascend/v0.26.0rc1/ascend-a2/models/Qwen3.6-35B-A3B/Qwen3.6-35B-A3B-w8a8.yaml",
    "vllm-ascend/v0.26.0rc1/ascend-a2/models/Qwen3.5-9B/Qwen3.5-9B.yaml",
    "vllm-ascend/v0.26.0rc1/ascend-a2/models/GLM-4.7/GLM-4.7-W8A8-floatmtp.yaml",
    "vllm-ascend/qwen3.8-next/ascend-a2/models/Qwen3.8-Flash-Next/Qwen3.8-Flash-Next-w8a8-mtp.yaml",
]


def test_glm53_w8a8_1m_patterns_only_accept_the_supported_ordering():
    """GLM-5.3 W8A8 1M 仅接受量化标记在上下文长度前的模型名。"""
    model_name = "GLM-5.3-w8a8-1M"
    paths = [
        ENGINE_ROOT
        / "vllm-ascend"
        / "v0.23.0"
        / "ascend-a3"
        / "models"
        / "GLM-5.3-1M"
        / "GLM-5.3-w8a8-1M.yaml",
        SMART_ROOT
        / "vllm-ascend"
        / "v0.23.0"
        / "ascend-a3"
        / "models"
        / "GLM-5.3-1M"
        / "GLM-5.3-w8a8-1M.yaml",
    ]

    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        patterns = [
            rule["name_pattern"]
            for rule in (data.get("model") or {}).get("match") or []
            if isinstance(rule, dict) and rule.get("name_pattern")
        ]
        assert any(re.fullmatch(pattern, model_name) for pattern in patterns), path
        for unsupported_name in ("GLM-5.3-1M", "GLM-5.3-1M-w8a8"):
            assert not any(re.fullmatch(pattern, unsupported_name) for pattern in patterns), path


def _locate_engine_yaml(rel: str) -> Path:
    """按 variant 文件名 + 硬件目录定位引擎 YAML;多命中时按版本目录消歧。

    vllm-ascend 引擎树有版本层(同名 variant 可能在多个版本目录存在,如
    GLM-5.1-w4a8 同时在 v0.21.0rc 与 v0.23.0),需用 smart 资产的版本目录消歧;
    vllm 引擎树无版本层,文件名 + 硬件目录已唯一。命中数 != 1 即失败。
    """
    parts = (SMART_ROOT / rel).relative_to(SMART_ROOT).parts
    engine, version, hardware, variant = parts[0], parts[1], parts[2], Path(rel).stem
    cands = sorted(
        p for p in ENGINE_ROOT.glob(f"{engine}/**/models/**/{variant}.yaml") if hardware in p.parts
    )
    if len(cands) > 1:
        versioned = [p for p in cands if version in p.parts]
        if len(versioned) == 1:
            cands = versioned
    assert len(cands) == 1, f"engine YAML for {rel}: expected exactly 1 candidate, got {cands}"
    return cands[0]


@pytest.mark.parametrize("rel", ASSETS, ids=lambda r: r)
def test_smart_scenarios_subset_of_engine(rel):
    smart_path = SMART_ROOT / rel
    assert smart_path.is_file(), f"missing smart asset: {rel}"
    smart = yaml.safe_load(smart_path.read_text(encoding="utf-8")) or {}
    engine = yaml.safe_load(_locate_engine_yaml(rel).read_text(encoding="utf-8")) or {}

    smart_scen = set((smart.get("smart_accel") or {}).keys())
    engine_scen = set((engine.get("scenarios") or {}).keys())
    assert smart_scen, f"{rel}: smart_accel 为空,无需守护也说明资产异常"
    assert smart_scen <= engine_scen, (
        f"{rel}: smart 场景 {sorted(smart_scen - engine_scen)} 未在引擎 recipe 中声明,"
        f"engine 仅支持 {sorted(engine_scen)}"
    )
    for name in sorted(smart_scen):
        smart_ref = (smart["smart_accel"][name] or {}).get("source_ref")
        engine_ref = (engine["scenarios"].get(name) or {}).get("source_ref")
        assert smart_ref == engine_ref, (
            f"{rel}#{name}: source_ref {smart_ref!r} 与引擎 recipe 的 {engine_ref!r} 不一致,"
            f"应指向引擎真实来源而非自动生成标记"
        )


@pytest.mark.parametrize("rel", ASSETS, ids=lambda r: r)
def test_smart_assets_have_no_placeholder_source_ref(rel):
    """source_ref 不得保留自动生成占位(如 smart_accel#standalone)。"""
    smart = yaml.safe_load((SMART_ROOT / rel).read_text(encoding="utf-8")) or {}
    for name, block in (smart.get("smart_accel") or {}).items():
        ref = (block or {}).get("source_ref") or ""
        assert not ref.startswith("smart_accel#"), (
            f"{rel}#{name}: source_ref {ref!r} 是占位值,应改为引擎 recipe 的真实 source_ref"
        )


def test_glm53_multi_node_speculative_decoding():
    """GLM-5.3 多机开启投机解码后必须产出原始命令声明的 deepseek_mtp 参数。"""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm-ascend",
        engine_version="v0.23.0",
        hardware_family="ascend-a3",
        model_name="GLM-5.3-w8a8",
        gpu_count=16,
        flags=LoadFlags(topology="multi_node", decoding_enabled=True),
    )

    assert out is not None
    assert out.smart_decoding_scheme == "deepseek_mtp"
    assert out.engine_params.engine_config["speculative_config"] == {
        "num_speculative_tokens": 3,
        "method": "deepseek_mtp",
        "enforce_eager": True,
    }


def test_glm53_flash_nightly_multi_node_mtp_and_native_kv_offload():
    """Nightly A2 dual-node GLM Flash must retain MTP and native CPU KV offload."""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm-ascend",
        engine_version="glm-5.3-flash-nightly",
        hardware_family="ascend-a2",
        model_name="GLM-5.3-Flash-w8a8",
        gpu_count=8,
        flags=LoadFlags(
            topology="multi_node",
            decoding_enabled=True,
            kv=True,
            memory_offload_size_mode="64",
        ),
    )

    assert out is not None
    assert out.smart_decoding_scheme == "deepseek_mtp"
    assert out.smart_kv_cache_scheme == "cpu"
    assert out.engine_params.engine_config == {
        "speculative_config": {
            "method": "deepseek_mtp",
            "num_speculative_tokens": 3,
            "enforce_eager": True,
        },
        "kv_offloading_backend": "native",
        "kv_offloading_size": "64",
    }
    assert out.engine_params.env == {"VLLM_USE_SIMPLE_KV_OFFLOAD": "1"}


def test_glm53_flash_nightly_a2_declares_tool_calling_and_reasoning():
    """Nightly A2 GLM Flash must retain its verified tool and reasoning parsers."""
    path = (
        ENGINE_ROOT
        / "vllm-ascend"
        / "glm-5.3-flash-nightly"
        / "ascend-a2"
        / "models"
        / "GLM-5.3-Flash"
        / "GLM-5.3-Flash-w8a8.yaml"
    )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    features = data["features"]

    assert features["tool_calling"]["args"] == [
        "--tool-call-parser",
        "glm47",
        "--enable-auto-tool-choice",
    ]
    assert features["reasoning"]["args"] == ["--reasoning-parser", "glm45"]


def test_qwen38_flash_next_910b3_standalone_speculative_decoding():
    """Qwen3.8 Flash Next 的定制 Ascend 版本可命中并保留完整 MTP 参数。"""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm-ascend",
        engine_version="qwen3.8-next",
        hardware_family="ascend-a2",
        model_name="Qwen3.8-Flash-Next-w8a8-mtp",
        gpu_count=8,
        flags=LoadFlags(topology="standalone", decoding_enabled=True),
    )

    assert out is not None
    assert out.smart_decoding_scheme == "qwen3_5_mtp"
    assert out.engine_params.engine_config["speculative_config"] == {
        "method": "qwen3_5_mtp",
        "num_speculative_tokens": 3,
        "enforce_eager": True,
    }


@pytest.mark.parametrize(
    ("sparse_level", "index_topk_freq"),
    [
        ("performance_first", 8),
        ("accuracy_first", 4),
    ],
)
def test_glm53_multi_node_sparse(sparse_level, index_topk_freq):
    """GLM-5.3 多机稀疏加速必须按策略下发对应的重算频率。"""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm-ascend",
        engine_version="v0.23.0",
        hardware_family="ascend-a3",
        model_name="GLM-5.3-w8a8",
        gpu_count=16,
        flags=LoadFlags(
            topology="multi_node",
            sparse=True,
            sparse_level=sparse_level,
        ),
    )

    assert out is not None
    assert out.engine_params.engine_config["hf_overrides"] == {
        "index_topk_freq": index_topk_freq,
    }


@pytest.mark.parametrize(
    ("sparse_level", "index_topk_freq"),
    [
        ("performance_first", 8),
        ("accuracy_first", 4),
    ],
)
def test_vllm_glm53_standalone_decoding_and_sparse(sparse_level, index_topk_freq):
    """GLM-5.3 standalone must reproduce the validated MTP and sparse parameters."""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm",
        engine_version="0.28.0",
        hardware_family="h20_141G",
        model_name="GLM-5.3",
        gpu_count=8,
        flags=LoadFlags(
            topology="standalone",
            decoding_enabled=True,
            sparse=True,
            sparse_level=sparse_level,
        ),
    )

    assert out is not None
    assert out.smart_decoding_scheme == "mtp"
    assert out.smart_kv_sparse_scheme == sparse_level
    assert out.engine_params.engine_config == {
        "speculative_config": {
            "method": "mtp",
            "num_speculative_tokens": 3,
        },
        "kv_cache_dtype": "fp8",
        "hf_overrides": {
            "index_topk_freq": index_topk_freq,
        },
    }


@pytest.mark.parametrize(
    ("topology", "gpu_count"),
    [("standalone", 8), ("multi_node", 16)],
)
@pytest.mark.parametrize(
    ("sparse_level", "index_topk_freq"),
    [
        ("performance_first", 8),
        ("accuracy_first", 4),
    ],
)
def test_minimax_m3_index_cache(topology, gpu_count, sparse_level, index_topk_freq):
    """MiniMax-M3 IndexCache must render both validated policy levels."""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm",
        engine_version="0.28.0",
        hardware_family="rtx_pro_5000_72G",
        model_name="MiniMax-M3-mxfp8",
        gpu_count=gpu_count,
        flags=LoadFlags(
            topology=topology,
            sparse=True,
            sparse_level=sparse_level,
        ),
    )

    assert out is not None
    assert out.smart_kv_sparse_scheme == sparse_level
    assert out.packages == ["b12x:v1.3.0"]
    assert out.engine_params.engine_config == {
        "kv_cache_dtype": "fp8",
        "hf_overrides": {
            "use_index_cache": True,
            "index_topk_freq": index_topk_freq,
        },
    }


@pytest.mark.parametrize("model_name", ["GLM-5.3-Flash", "GLM-5.3-w4a8"])
def test_glm53_sibling_variants_do_not_enable_speculative_decoding(model_name):
    """GLM-5.3-w8a8 SmartAccel must not inject deepseek_mtp into sibling variants."""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm-ascend",
        engine_version="v0.23.0",
        hardware_family="ascend-a3",
        model_name=model_name,
        gpu_count=16,
        flags=LoadFlags(topology="multi_node", decoding_enabled=True),
    )

    assert out is None


def test_deepseek_v4_flash_vision_uses_internal_dspark_weights():
    """DSpark must use weights embedded in the target checkpoint without a draft path."""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm",
        engine_version="deepseekv4-flash-vision",
        hardware_family="h20_141G",
        model_name="DeepSeek-V4-Flash-Vision-Exp",
        gpu_count=8,
        flags=LoadFlags(
            topology="standalone",
            decoding_enabled=True,
        ),
    )

    assert out is not None
    assert out.smart_decoding_scheme == "dspark"
    assert out.engine_params.engine_config["speculative_config"] == {
        "method": "dspark",
        "num_speculative_tokens": 3,
        "draft_sample_method": "probabilistic",
        "enable_adaptive_verification": False,
    }


def test_deepseek_v41_flash_multi_node_dspark_decoding():
    """DeepSeek V4.1 Flash multi-node must reproduce the validated DSpark settings."""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm-ascend",
        engine_version="deepseek-v4.1-flash-a3",
        hardware_family="ascend-a3",
        model_name="DeepSeek-V4.1-Flash-w8a8",
        gpu_count=16,
        flags=LoadFlags(topology="multi_node", decoding_enabled=True),
    )

    assert out is not None
    assert out.smart_decoding_scheme == "dspark"
    assert out.engine_params.engine_config["speculative_config"] == {
        "method": "dspark",
        "num_speculative_tokens": 6,
        "enforce_eager": True,
    }


def test_kimi_k3_multi_node_kv_per_rank_bytes():
    """Kimi-K3 multi_node KV 卸载的 per-rank 字节数按卡均分(multi_node 实际渲染断言)。

    KV_MEM_OFFLOAD_SIZE 是 pod 总量;cpu_bytes_to_use_per_rank 必须是
    (总量 // gpu_count) 转字节,而不是全量转字节 —— 否则 8 卡 pod 每 rank
    都申请整份 128GB,pod 总需求放大 8 倍直接打爆 host 内存。
    40GB pod / 8 卡 → 5368709120(= 引擎 recipe 基线 5GiB/rank)。
    """
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm",
        engine_version="kimi-k3",
        hardware_family="h20_141G",
        model_name="Kimi-K3",
        gpu_count=8,
        flags=LoadFlags(topology="multi_node", kv=True, memory_offload_size_mode="40"),
    )
    assert out is not None, "kimi-k3 版本目录下的资产应可命中"
    assert out.smart_kv_cache_scheme == "cpu"
    kt = out.engine_params.engine_config["kv_transfer_config"]
    assert kt["kv_connector"] == "SimpleCPUOffloadConnector"
    # 40GB // 8 卡 = 5GiB/rank = 5368709120 字节(与引擎 recipe 基线一致)
    assert kt["kv_connector_extra_config"]["cpu_bytes_to_use_per_rank"] == "5368709120", (
        "per-rank 字节数未按 gpu_count 均分:" + str(kt["kv_connector_extra_config"])
    )


def test_kimi_k3_multi_node_kv_per_rank_precision():
    """非整除 GB 时先转字节再整除,不丢下发配额:10GB/8卡 → 1.25GiB/rank(非 1GiB)。"""
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import _package_smart_accel_root

    out = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm",
        engine_version="kimi-k3",
        hardware_family="h20_141G",
        model_name="Kimi-K3",
        gpu_count=8,
        flags=LoadFlags(topology="multi_node", kv=True, memory_offload_size_mode="10"),
    )
    kt = out.engine_params.engine_config["kv_transfer_config"]
    # 10GiB * 1024^3 = 10737418240 字节;// 8 = 1342177280(1.25GiB),8 rank 共 10GiB 不丢配额
    assert kt["kv_connector_extra_config"]["cpu_bytes_to_use_per_rank"] == "1342177280", (
        "先整除 GB 会丢小数配额:" + str(kt["kv_connector_extra_config"])
    )
