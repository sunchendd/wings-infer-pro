"""v2 资产加载器单测（refactor.md §3/§5 + registry.md §6）。

覆盖：v2 资产扫描、合一文件解析、profile 匹配 + 偏序裁决（locate_v2）、
未命中回退、歧义告警 + 选第一个。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wings_ctl.loaders.v2_loader import (
    load_v2_assets,
    locate_v2,
    parse_v2_asset,
    scan_v2_assets,
    v2_root,
)


@pytest.fixture
def v2_tree(tmp_path: Path) -> Path:
    """构造一个最小 v2 资产树（含泛用/特化 hardware 两个资产）。"""
    root = tmp_path / "config" / "v2"
    # 泛用资产：h20_96G + h20_141G
    generic_dir = root / "vllm" / "v0.30.0" / "h20" / "DeepSeek-V3"
    generic_dir.mkdir(parents=True)
    (generic_dir / "DeepSeek-V3-bf16.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm\n"
        "  version: \"v0.30.0\"\n"
        "  hardware: [h20_96G, h20_141G]\n"
        "  model: DeepSeek-V3-bf16\n"
        "model:\n"
        "  name: DeepSeek-V3\n"
        "  variant_name: DeepSeek-V3-bf16\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: deepseek-ai/DeepSeek-V3\n"
        "          tensor_parallel_size: 8\n"
        "smart_accel:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        decoding:\n"
        "        - name: mtp\n"
        "          cli_params: {}\n"
        "          envs: {}\n",
        encoding="utf-8",
    )
    # 特化资产：仅 h20_141G
    specific_dir = root / "vllm" / "v0.30.0" / "h20_141G" / "DeepSeek-V3"
    specific_dir.mkdir(parents=True)
    (specific_dir / "DeepSeek-V3-bf16.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm\n"
        "  version: \"v0.30.0\"\n"
        "  hardware: [h20_141G]\n"
        "  model: DeepSeek-V3-bf16\n"
        "model:\n"
        "  name: DeepSeek-V3\n"
        "  variant_name: DeepSeek-V3-bf16\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: deepseek-ai/DeepSeek-V3\n"
        "          tensor_parallel_size: 8\n",
        encoding="utf-8",
    )
    return tmp_path / "config"


def test_scan_v2_assets(v2_tree):
    files = scan_v2_assets(v2_tree)
    assert len(files) == 2


def test_load_v2_assets(v2_tree):
    assets = load_v2_assets(v2_tree)
    assert len(assets) == 2
    for asset in assets:
        assert isinstance(asset.profile, dict)
        assert "scenarios" in asset.data


def test_parse_v2_asset_missing_profile_skipped(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema: v2\nmodel: {}\n", encoding="utf-8")
    assert parse_v2_asset(bad) is None


def test_locate_v2_picks_most_specific(v2_tree):
    ctx = {
        "engine": "vllm",
        "version": "v0.30.0",
        "hardware": "h20_141G",
        "model": "DeepSeek-V3-bf16",
    }
    hit = locate_v2(v2_tree, ctx)
    assert hit is not None
    # 特化资产（仅 h20_141G）应胜出
    assert "h20_141G" in str(hit.path)


def test_locate_v2_no_match_returns_none(v2_tree):
    ctx = {
        "engine": "vllm",
        "version": "v0.30.0",
        "hardware": "h100",
        "model": "DeepSeek-V3-bf16",
    }
    assert locate_v2(v2_tree, ctx) is None


def test_locate_v2_ambiguous_picks_first(v2_tree):
    # 两个等价资产（同 hardware 集合）→ 告警 + 确定性选第一个，不再 fail-fast。
    # 在 v2_tree 基础上追加一个与泛用资产等价的重复资产。
    dup_dir = v2_tree / "v2" / "vllm" / "v0.30.0" / "h20" / "DeepSeek-V3"
    dup_dir.mkdir(parents=True, exist_ok=True)
    (dup_dir / "DeepSeek-V3-bf16-dup.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm\n"
        "  version: \"v0.30.0\"\n"
        "  hardware: [h20_96G, h20_141G]\n"
        "  model: DeepSeek-V3-bf16\n"
        "model:\n"
        "  name: DeepSeek-V3\n"
        "  variant_name: DeepSeek-V3-bf16\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: deepseek-ai/DeepSeek-V3\n"
        "          tensor_parallel_size: 8\n",
        encoding="utf-8",
    )
    ctx = {
        "engine": "vllm",
        "version": "v0.30.0",
        "hardware": "h20_96G",
        "model": "DeepSeek-V3-bf16",
    }
    # 泛用资产与重复资产等价 → 不抛错，返回第一个（确定性）。
    hit = locate_v2(v2_tree, ctx)
    assert hit is not None
    # 排序后 `-dup` 文件在前，确定性选第一个。
    assert "DeepSeek-V3-bf16-dup.yaml" in str(hit.path)


def test_v2_root_path(v2_tree):
    assert v2_root(v2_tree).name == "v2"


def test_locate_v2_alias_normalization(tmp_path):
    """别名归一化：ctx 的 hardware 命中别名表 → 归一化到目标硬件再匹配。"""
    # 构造 v2 资产树 + 别名表
    root = tmp_path / "config"
    asset_dir = root / "v2" / "vllm-ascend" / "v0.23.0" / "ascend-a3" / "DeepSeek-V4-Flash"
    asset_dir.mkdir(parents=True)
    (asset_dir / "DeepSeek-V4-Flash-w8a8-mtp.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm-ascend\n"
        "  version: \"v0.23.0\"\n"
        "  hardware: [Ascend910C_64G]\n"
        "  model: DeepSeek-V4-Flash-w8a8-mtp\n"
        "model:\n"
        "  name: DeepSeek-V4-Flash\n"
        "  variant_name: DeepSeek-V4-Flash-w8a8-mtp\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: Eco-Tech/DeepSeek-V4-Flash-w8a8-mtp\n",
        encoding="utf-8",
    )
    # 别名表：Ascend910_64G → Ascend910C_64G
    (root / "v2" / "hardware_table.yaml").write_text(
        "hardware:\n"
        "  - Ascend910C_64G\n"
        "aliases:\n"
        "  Ascend910_64G: Ascend910C_64G\n",
        encoding="utf-8",
    )

    base = {"engine": "vllm-ascend", "version": "v0.23.0", "model": "DeepSeek-V4-Flash-w8a8-mtp"}
    # 别名 Ascend910_64G → 归一化到 Ascend910C_64G → 命中
    assert locate_v2(root, {**base, "hardware": "Ascend910_64G"}) is not None
    # 合法硬件 Ascend910C_64G → 命中
    assert locate_v2(root, {**base, "hardware": "Ascend910C_64G"}) is not None
    # 非别名非合法硬件 → 不命中
    assert locate_v2(root, {**base, "hardware": "Ascend910C_128G"}) is None


def test_locate_v2_context_length_generic_vs_specific(tmp_path):
    """context_length 泛化/特化：区间包含偏序取最特化者（registry.md §3.2）。

    泛化资产声明 `>= 0`（覆盖所有上下文），特化资产声明 `>= 131072`（长上下文）。
    短上下文命中泛化，长上下文命中特化；ctx 缺 context_length 时两者都不命中。
    """
    root = tmp_path / "config"
    asset_dir = root / "v2" / "vllm-ascend" / "v0.23.0" / "ascend-a3" / "TestModel"
    asset_dir.mkdir(parents=True)
    # 泛化资产：context_length >= 0
    (asset_dir / "TestModel-generic.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm-ascend\n"
        "  version: \"v0.23.0\"\n"
        "  hardware: [Ascend910C_64G]\n"
        "  model: TestModel\n"
        "  context_length: { \">=\": 0 }\n"
        "model:\n"
        "  name: TestModel\n"
        "  variant_name: TestModel\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: /m/TestModel\n"
        "          max_num_batched_tokens: 1024\n",
        encoding="utf-8",
    )
    # 特化资产：context_length >= 131072
    (asset_dir / "TestModel-longctx.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm-ascend\n"
        "  version: \"v0.23.0\"\n"
        "  hardware: [Ascend910C_64G]\n"
        "  model: TestModel\n"
        "  context_length: { \">=\": 131072 }\n"
        "model:\n"
        "  name: TestModel\n"
        "  variant_name: TestModel\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: /m/TestModel\n"
        "          max_num_batched_tokens: 8192\n",
        encoding="utf-8",
    )
    (root / "v2" / "hardware_table.yaml").write_text(
        "hardware:\n"
        "  - Ascend910C_64G\n",
        encoding="utf-8",
    )

    base = {"engine": "vllm-ascend", "version": "v0.23.0", "hardware": "Ascend910C_64G", "model": "TestModel"}
    # 短上下文 → 泛化资产
    hit = locate_v2(root, {**base, "context_length": 4096})
    assert hit is not None and "generic" in hit.path.name
    # 长上下文 → 特化资产（>= 含等号，131072 命中特化）
    hit = locate_v2(root, {**base, "context_length": 200000})
    assert hit is not None and "longctx" in hit.path.name
    hit = locate_v2(root, {**base, "context_length": 131072})
    assert hit is not None and "longctx" in hit.path.name
    # ctx 缺 context_length → 两个资产都声明了 context_length，均不命中
    assert locate_v2(root, base) is None


def test_locate_v2_cpu_arch_generic_vs_specific(tmp_path):
    """cpu_arch 泛化/特化：集合包含偏序取最特化者。

    泛化资产声明 `{aarch64, x86_64}`（匹配两种架构），特化资产声明 `{x86_64}`。
    x86_64 ctx 命中特化；aarch64 ctx 命中泛化；未声明 cpu_arch 的资产最泛化兜底。
    """
    root = tmp_path / "config"
    asset_dir = root / "v2" / "vllm" / "v0.30.0" / "h20_141G" / "ArchDemo"
    asset_dir.mkdir(parents=True)
    # 泛化资产：cpu_arch {aarch64, x86_64}
    (asset_dir / "ArchDemo-generic.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm\n"
        "  version: \"v0.30.0\"\n"
        "  hardware: [h20_141G]\n"
        "  model: ArchDemo\n"
        "  cpu_arch: {aarch64, x86_64}\n"
        "model:\n"
        "  name: ArchDemo\n"
        "  variant_name: ArchDemo\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: /m/ArchDemo\n",
        encoding="utf-8",
    )
    # 特化资产：cpu_arch {x86_64}
    (asset_dir / "ArchDemo-x86.yaml").write_text(
        "schema: v2\n"
        "profile:\n"
        "  engine: vllm\n"
        "  version: \"v0.30.0\"\n"
        "  hardware: [h20_141G]\n"
        "  model: ArchDemo\n"
        "  cpu_arch: {x86_64}\n"
        "model:\n"
        "  name: ArchDemo\n"
        "  variant_name: ArchDemo\n"
        "scenarios:\n"
        "  standalone:\n"
        "    strategies:\n"
        "      single_node:\n"
        "        default_strategy: true\n"
        "        engine_config:\n"
        "          model: /m/ArchDemo\n",
        encoding="utf-8",
    )
    (root / "v2" / "hardware_table.yaml").write_text(
        "hardware:\n"
        "  - h20_141G\n",
        encoding="utf-8",
    )

    base = {"engine": "vllm", "version": "v0.30.0", "hardware": "h20_141G", "model": "ArchDemo"}
    # x86_64 → 特化资产（{x86_64} ⊆ {aarch64, x86_64}）
    hit = locate_v2(root, {**base, "cpu_arch": "x86_64"})
    assert hit is not None and "x86" in hit.path.name
    # aarch64 → 只有泛化命中
    hit = locate_v2(root, {**base, "cpu_arch": "aarch64"})
    assert hit is not None and "generic" in hit.path.name
    # ctx 缺 cpu_arch → 两个资产都声明了 cpu_arch，均不命中
    assert locate_v2(root, base) is None
