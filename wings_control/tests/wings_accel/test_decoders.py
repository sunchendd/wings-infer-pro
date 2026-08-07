import pytest

from wings_accel.decoders import smart_decoding_expander
from wings_accel.render import PlaceholderContext
from wings_accel.schemas import ModelConfig, SmartDecodingConfig


def make_ctx(draft=""):
    return PlaceholderContext(draft_model_path=draft)


def make_input(enabled, model_path="", model_arch=""):
    return (
        SmartDecodingConfig(enabled=enabled, model_path=model_path),
        ModelConfig(model_path="/models/llama", model_arch=model_arch),
    )


def make_decoding_block():
    """new:list 形式,speculative_config 在 cli_params 下。"""
    return [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "cli_params": {
                "speculative_config": {
                    "method": "eagle3",
                    "num_speculative_tokens": 3,
                    "model": "$path",
                    "enforce_eager": True,  # bool → 进 speculative_config JSON
                },
            },
            "envs": {"EARS_TOLERANCE": "0.3"},
        },
        {
            "name": "mtp",
            "cli_params": {"speculative_config": {"method": "mtp", "num_speculative_tokens": 1}},
            "envs": {},
        },
    ]


def test_decoding_enabled_false():
    cfg, mod = make_input(enabled=False)
    assert smart_decoding_expander(cfg, mod, None, make_ctx()) is None


def test_decoding_model_based_hit():
    cfg, mod = make_input(enabled=True, model_path="/draft/eagle", model_arch="EAGLE3-LLaMA")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx("/draft/eagle"))
    assert out.scheme == "eagle3"
    assert out.degraded is False
    assert out.engine_params.engine_config["speculative_config"]["method"] == "eagle3"
    assert out.engine_params.engine_config["speculative_config"]["model"] == "/draft/eagle"
    assert out.engine_params.engine_config["speculative_config"]["enforce_eager"] is True
    # envs
    assert out.engine_params.env == {"EARS_TOLERANCE": "0.3"}


def test_decoding_model_based_miss_degrade_to_no_model():
    block = [{"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}}]
    cfg, mod = make_input(enabled=True, model_path="/draft/unknown", model_arch="UnknownArch")
    out = smart_decoding_expander(cfg, mod, block, make_ctx("/draft/unknown"))
    assert out.scheme == "mtp"
    assert out.degraded is True
    assert "model_based_miss->no_model" in out.degrade_reason


def test_decoding_no_model_hit():
    cfg, mod = make_input(enabled=True, model_path="", model_arch="")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx())
    assert out.scheme == "mtp"
    assert out.degraded is False


def test_decoding_requires_model_path_gate():
    """requires_model_path 的方案在无草稿路径时不可选 → 回落 no_model。"""
    block = [
        {"name": "eagle3", "requires_model_path": True,
         "cli_params": {"speculative_config": {"method": "eagle3"}}},
        {"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    # 无 model_path 时 model_based 完全跳过
    cfg, mod = make_input(enabled=True, model_path="", model_arch="eagle")
    out = smart_decoding_expander(cfg, mod, block, make_ctx())
    assert out.scheme == "mtp"  # eagle3 因 requires_model_path 被门挡住


@pytest.mark.parametrize("bogus", ["none", "None", "NONE", "null", "Null", " none "])
def test_decoding_requires_model_path_gate_none_literal(bogus):
    """requires_model_path 方案在草稿路径为 none/null 字面量时也应被门挡住。

    MaaS 下发 SPECULATIVE_DECODE_MODEL_PATH 未填可能下发字面量 "none"/"null";
    若当真实路径,eagle3 会产出 model:"none" 致 vllm serve 启动失败。归一在
    消费点(decoders._normalize_optional_path / _eligible)完成,适配层原样透传。
    """
    block = [
        {"name": "eagle3", "requires_model_path": True,
         "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}}},
        {"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    cfg, mod = make_input(enabled=True, model_path=bogus, model_arch="eagle")
    out = smart_decoding_expander(cfg, mod, block, make_ctx())
    assert out.scheme == "mtp"  # none/null 字面量等同空,model_based 被门挡住


def test_decoding_no_method_match_fallback():
    cfg, mod = make_input(enabled=True)
    assert smart_decoding_expander(cfg, mod, [], make_ctx()) is None


def test_decoding_missing_block_disabled():
    cfg, mod = make_input(enabled=True)
    assert smart_decoding_expander(cfg, mod, None, make_ctx()) is None


def test_decoding_topology_param_is_noop_after_scenario_refactor():
    """scenario 重构后,topology 参数不再参与过滤(scenario 路由在 loader 完成)。

    旧机制(scheme 级 deploy_modes)已废弃;新结构下 expander 只看扁平 decoding 列表,
    无论 topology 是什么,只要 block 含合格方案就产出。
    """
    cfg, mod = make_input(enabled=True, model_path="/draft/eagle", model_arch="EAGLE3")
    block = [{"name": "eagle3", "requires_model_path": True,
              "cli_params": {"speculative_config": {"method": "eagle3", "num_speculative_tokens": 3}}}]
    # topology=pd_prefill / pd_decode / standalone / None 都不过滤
    for topo in ("pd_prefill", "pd_decode", "standalone", "multi_node", None):
        out = smart_decoding_expander(cfg, mod, block, make_ctx("/draft/eagle"), topology=topo)
        assert out is not None and out.scheme == "eagle3", f"topology={topo!r} 不应过滤 decoding"


def test_decoding_scenario_isolation_via_loader_route():
    """scenario 路由的真正判定点在 yaml_loader._route_smart_accel_block(wings_control 风格结构)。

    PD-prefill 场景下,loader 路由到 nodes[role=prefill](不含 decoding 键),
    故 expander 拿到 None → 不产出。本测试验证路由函数行为。
    """
    from wings_accel.yaml_loader import _route_smart_accel_block

    sa = {
        "standalone": {
            "match": {"distributed": False, "pd_role": None},
            "strategies": {"single_node": {"default_strategy": True, "decoding": [{"name": "mtp"}]}},
        },
        "multi_node": {
            "match": {"distributed": True, "pd_role": None},
            "strategies": {"multi_node_dp": {"default_strategy": True, "decoding": [{"name": "mtp"}]}},
        },
        "pd_disaggregation": {
            "match": {"distributed": True, "pd_role": None},
            "strategies": {"pd_cluster": {"default_strategy": True, "nodes": [
                {"role": "prefill", "index": 0, "sparse": [{"name": "performance_first"}]},  # 不含 decoding
                {"role": "decode", "index": 0, "decoding": [{"name": "mtp"}], "sparse": [{"name": "performance_first"}]},
            ]}},
        },
    }
    # standalone / None → strategies.single_node(含 decoding)
    assert "decoding" in _route_smart_accel_block(sa, "standalone")
    assert "decoding" in _route_smart_accel_block(sa, None)
    # pd_prefill → nodes[role=prefill](不含 decoding → expander 拿 None → 不产出)
    assert "decoding" not in _route_smart_accel_block(sa, "pd_prefill")
    # pd_decode → nodes[role=decode](含 decoding)
    assert "decoding" in _route_smart_accel_block(sa, "pd_decode")


# ── draft_arch 匹配(config.json architectures → method 选择)──


def _make_draft_dir(tmp_path, architectures):
    """创建含 config.json 的草稿目录。"""
    import json
    d = tmp_path / "draft"
    d.mkdir()
    (d / "config.json").write_text(json.dumps({"architectures": architectures}))
    return str(d)


def test_draft_arch_matches_eagle3(tmp_path):
    """草稿 architectures 含 eagle3 → 选 eagle3 方案(非首序的 dflash)。"""
    draft = _make_draft_dir(tmp_path, ["Eagle3LlamaForCausalLM"])
    cfg, mod = make_input(enabled=True, model_path=draft, model_arch="EAGLE3")
    block = [
        {"name": "eagle3", "requires_model_path": True, "draft_arch": ["eagle3"],
         "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path", "num_speculative_tokens": 3}}},
        {"name": "dflash", "requires_model_path": True, "draft_arch": ["dflash"],
         "cli_params": {"speculative_config": {"method": "dflash", "model": "$path", "num_speculative_tokens": 15}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "eagle3"


def test_draft_arch_matches_dflash(tmp_path):
    """草稿 architectures 含 dflash → 选 dflash(即使 eagle3 在前)。"""
    draft = _make_draft_dir(tmp_path, ["DFlashQwen3ForCausalLM"])
    cfg, mod = make_input(enabled=True, model_path=draft, model_arch="EAGLE3")
    block = [
        {"name": "eagle3", "requires_model_path": True, "draft_arch": ["eagle3"],
         "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}}},
        {"name": "dflash", "requires_model_path": True, "draft_arch": ["dflash"],
         "cli_params": {"speculative_config": {"method": "dflash", "model": "$path"}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "dflash"


def test_draft_arch_unknown_falls_to_generic_draft(tmp_path):
    """草稿 architectures 不匹配任何 draft_arch → 降级通用 draft(未声明 draft_arch)。"""
    draft = _make_draft_dir(tmp_path, ["SomeUnknownArch"])
    cfg, mod = make_input(enabled=True, model_path=draft)
    block = [
        {"name": "eagle3", "requires_model_path": True, "draft_arch": ["eagle3"],
         "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}}},
        {"name": "draft", "requires_model_path": True,
         "cli_params": {"speculative_config": {"method": "draft_model", "model": "$path"}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "draft"


def test_draft_arch_no_config_json_falls_to_generic_draft():
    """草稿路径非本地(无 config.json)→ 降级通用 draft。"""
    cfg, mod = make_input(enabled=True, model_path="hf/repo-id")
    block = [
        {"name": "eagle3", "requires_model_path": True, "draft_arch": ["eagle3"],
         "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}}},
        {"name": "draft", "requires_model_path": True,
         "cli_params": {"speculative_config": {"method": "draft_model", "model": "$path"}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx("hf/repo-id"))
    assert out.scheme == "draft"


def test_no_draft_path_falls_to_no_model():
    """无草稿路径 → no_model 方案(至多一个,取首序)。"""
    cfg, mod = make_input(enabled=True, model_path="")
    block = [
        {"name": "eagle3", "requires_model_path": True, "draft_arch": ["eagle3"],
         "cli_params": {"speculative_config": {"method": "eagle3"}}},
        {"name": "mtp",
         "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(""))
    assert out.scheme == "mtp"


def test_dspark_dual_form_no_draft(tmp_path):
    """dspark 无草稿形态(主模型自带权重,如 DeepSeek V4 Pro/Flash 0731):
    不声明 requires_model_path → 进 no_model 分支,无草稿路径也产出。"""
    cfg, mod = make_input(enabled=True, model_path="")
    block = [
        {"name": "dspark",  # 无 requires_model_path → no_model
         "cli_params": {"speculative_config": {"method": "dspark", "num_speculative_tokens": 7, "draft_sample_method": "greedy"}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(""))
    assert out.scheme == "dspark"
    sc = out.engine_params.engine_config.get("speculative_config", {})
    assert "model" not in sc  # 无草稿形态不带 model 字段


def test_dspark_dual_form_with_draft(tmp_path):
    """dspark 有草稿形态(如 Kimi K3 单独发草稿):
    声明 requires_model_path + draft_arch → config.json 含 dspark 时匹配,带 model 字段。"""
    draft = _make_draft_dir(tmp_path, ["K3DSparkModel"])
    cfg, mod = make_input(enabled=True, model_path=draft)
    block = [
        {"name": "dspark", "requires_model_path": True, "draft_arch": ["dspark", "k3dspark"],
         "cli_params": {"speculative_config": {"method": "dspark", "model": "$path", "num_speculative_tokens": 7}}},
        {"name": "dspark",
         "cli_params": {"speculative_config": {"method": "dspark", "num_speculative_tokens": 7}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "dspark"
    sc = out.engine_params.engine_config.get("speculative_config", {})
    assert "model" in sc  # 有草稿形态带 model 字段


def test_dspark_dual_form_coexistence(tmp_path):
    """同一 yaml 同时声明无草稿 dspark + 有草稿 dspark:
    无草稿路径 → 选无草稿 dspark(no_model,无 model);传草稿 → 选有草稿 dspark(model_based,带 model)。"""
    block = [
        {"name": "dspark", "requires_model_path": True, "draft_arch": ["dspark"],
         "cli_params": {"speculative_config": {"method": "dspark", "model": "$path"}}},
        {"name": "dspark",
         "cli_params": {"speculative_config": {"method": "dspark", "num_speculative_tokens": 7}}},
    ]
    # 无草稿路径 → 无草稿 dspark
    cfg1, mod1 = make_input(enabled=True, model_path="")
    out1 = smart_decoding_expander(cfg1, mod1, block, make_ctx(""))
    assert out1.scheme == "dspark"
    assert "model" not in out1.engine_params.engine_config.get("speculative_config", {})
    # 传 dspark 草稿 → 有草稿 dspark
    draft = _make_draft_dir(tmp_path, ["K3DSparkModel"])
    cfg2, mod2 = make_input(enabled=True, model_path=draft)
    out2 = smart_decoding_expander(cfg2, mod2, block, make_ctx(draft))
    assert out2.scheme == "dspark"
    assert "model" in out2.engine_params.engine_config.get("speculative_config", {})
