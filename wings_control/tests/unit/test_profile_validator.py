"""profile 资产合法性离线校验单测（registry.md §5）。

覆盖：必填四要素缺失、未注册 key、必填 key 值非法、可选 key 多算子叠加、
`hardware` 值 ∉ 合法硬件表。
"""

from __future__ import annotations

from wings_ctl.loaders.profile_validator import validate_assets, validate_profile

LEGAL = {"h20_141G", "h20_96G", "ascend-a3", "h100"}


def _valid_profile():
    return {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h20_141G"}}


def test_valid_profile_no_error():
    result = validate_profile(_valid_profile(), legal_hardware=LEGAL)
    assert result.valid
    assert result.errors() == []


def test_missing_required_key():
    result = validate_profile({"engine": "vllm", "model": "m", "version": "v"}, legal_hardware=LEGAL)
    assert not result.valid
    assert any("必填" in i.message for i in result.issues)


def test_unregistered_key():
    profile = {**_valid_profile(), "dtype": "bf16"}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert not result.valid
    assert any("未注册" in i.message for i in result.issues)


def test_multi_operator_accumulation():
    profile = {**_valid_profile(), "context_length": {">=": 1, "<=": 2}}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert not result.valid
    assert any("一个算子" in i.message for i in result.issues)


def test_unregistered_operator():
    profile = {**_valid_profile(), "context_length": {"!=": 1}}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert not result.valid
    assert any("未注册算子" in i.message for i in result.issues)


def test_hardware_not_in_legal_table_is_warning():
    # 硬件表是增量维护的登记表，不完整是预期；未登记硬件 → warning（不阻断），不报 error。
    profile = {**_valid_profile(), "hardware": {"h999"}}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert result.valid  # 无 error
    assert any(i.severity == "warning" and "未登记硬件" in i.message for i in result.issues)


def test_hardware_legal_table_casefold():
    # 合法表大小写无关：h20_141G 与 h20_141g 等价
    result = validate_profile({**_valid_profile(), "hardware": {"H20_141G"}}, legal_hardware=LEGAL)
    assert result.valid


def test_hardware_yaml_flow_mapping_as_set():
    # YAML `hardware: {ascend-a3}` 解析为 dict {"ascend-a3": None}，取键为成员，不按算子 dict 解释
    profile = {**_valid_profile(), "hardware": {"ascend-a3": None}}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert result.valid


def test_cpu_arch_set_value_valid():
    profile = {**_valid_profile(), "cpu_arch": {"aarch64", "x86_64"}}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert result.valid


def test_cpu_arch_not_checked_against_hardware_table():
    # cpu_arch 不属于硬件表范围：即使值不在合法硬件表内，也不产生「未登记硬件」warning。
    profile = {**_valid_profile(), "cpu_arch": {"aarch64"}}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert result.valid
    assert not any("未登记硬件" in i.message for i in result.issues)


def test_cpu_arch_invalid_value():
    # cpu_arch 值必须是集合/列表/字符串；标量 int → error。
    profile = {**_valid_profile(), "cpu_arch": 123}
    result = validate_profile(profile, legal_hardware=LEGAL)
    assert not result.valid
    assert any("cpu_arch" in i.message for i in result.issues)


def test_validate_assets_batch():
    assets = [
        {"path": "a.yaml", "profile": _valid_profile()},
        {"path": "b.yaml", "profile": {"engine": "vllm"}},  # 缺必填
    ]
    result = validate_assets(assets, legal_hardware=LEGAL)
    assert not result.valid
    assert any(i.path == "b.yaml" for i in result.issues)
