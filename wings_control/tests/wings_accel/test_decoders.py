import json

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
            "draft_arch": ["eagle3"],
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


def test_decoding_model_based_hit(tmp_path):
    draft = _make_draft_dir(tmp_path, ["EAGLE3LLaMAForCausalLM"])
    cfg, mod = make_input(enabled=True, model_path=draft, model_arch="EAGLE3-LLaMA")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx(draft))
    assert out.scheme == "eagle3"
    assert out.degraded is False
    assert out.engine_params.engine_config["speculative_config"]["method"] == "eagle3"
    assert out.engine_params.engine_config["speculative_config"]["model"] == draft
    assert out.engine_params.engine_config["speculative_config"]["enforce_eager"] is True
    # envs
    assert out.engine_params.env == {"EARS_TOLERANCE": "0.3"}


def test_decoding_draft_with_undeclared_asset_disables(tmp_path, caplog):
    """mtp-only 资产 + 草稿路径 → 不降级 mtp、不内置合成,关闭投机+warning。

    MR133: 资产能力声明是唯一真相源;mtp 不吃草稿,未声明 draft 方案就不拼 argv。
    """
    import logging as _logging

    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "config.json").write_text(json.dumps({"architectures": ["UnknownArchForCausalLM"]}))
    block = [{"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}}]
    cfg, mod = make_input(enabled=True, model_path=str(draft))
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, block, make_ctx(str(draft)))
    assert out is None  # 不产 draft 也不降级 mtp
    assert "match no declared scheme" in caplog.text


def test_decoding_dedicated_miss_with_declared_generic_draft(tmp_path):
    """eagle3(声明 draft_arch)+ 朴素小模型草稿(架构 miss)→ 资产声明的 generic draft_model。"""
    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "config.json").write_text(json.dumps({"architectures": ["Qwen3ForCausalLM"]}))
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {
            "name": "draft_model",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"model": "$path", "num_speculative_tokens": 4}},
        },
        {"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    cfg, mod = make_input(enabled=True, model_path=str(draft))
    out = smart_decoding_expander(cfg, mod, block, make_ctx(str(draft)))
    assert out.scheme == "draft_model"
    assert out.engine_params.engine_config["speculative_config"]["model"] == str(draft)


def test_decoding_empty_block_with_draft_path_disables(tmp_path, caplog):
    """空占位资产 + 草稿路径 → 不内置合成,关闭投机(MR133 阻塞问题修复)。"""
    import logging as _logging

    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "config.json").write_text(json.dumps({"architectures": ["Qwen3ForCausalLM"]}))
    cfg, mod = make_input(enabled=True, model_path=str(draft))
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, [], make_ctx(str(draft)))
    assert out is None
    assert smart_decoding_expander(cfg, mod, None, make_ctx(str(draft))) is None
    assert "match no declared scheme" in caplog.text


def test_decoding_dedicated_mismatch_disables_speculative(tmp_path, caplog):
    """方案②:专用草稿错配 → 关闭投机(None)+ warning,不喂给朴素 draft。

    dflash 草稿头不是完整 LM,资产只声明 eagle3(draft_arch miss)时,
    喂给朴素 draft 必崩或静默丢弃用户 dflash 意图 → 宁可不开投机。
    """
    import logging as _logging

    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "config.json").write_text(json.dumps({"architectures": ["KimiForCausalLMDFLASH"]}))
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    cfg, mod = make_input(enabled=True, model_path=str(draft))
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, block, make_ctx(str(draft)))
    assert out is None  # 关闭投机,不产 draft 也不降级 mtp
    assert "dflash" in caplog.text  # warning 指明检测到的专用方法
    assert "draft_arch" in caplog.text  # 提示补资产的方向


def test_decoding_dedicated_hit_with_draft_arch(tmp_path):
    """声明 draft_arch 的专用方法在草稿架构命中时优先选中(优于 generic)。"""
    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "config.json").write_text(json.dumps({"architectures": ["XxxForCausalLMEagle3"]}))
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {
            "name": "draft_model",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"model": "$path", "num_speculative_tokens": 4}},
        },
    ]
    cfg, mod = make_input(enabled=True, model_path=str(draft))
    out = smart_decoding_expander(cfg, mod, block, make_ctx(str(draft)))
    assert out.scheme == "eagle3"
    assert out.degraded is False


def test_decoding_no_model_hit():
    cfg, mod = make_input(enabled=True, model_path="", model_arch="")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx())
    assert out.scheme == "mtp"
    assert out.degraded is False


def test_decoding_requires_model_path_gate():
    """requires_model_path 的方案在无草稿路径时不可选 → 回落 no_model。"""
    block = [
        {"name": "eagle3", "requires_model_path": True, "cli_params": {"speculative_config": {"method": "eagle3"}}},
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
        {
            "name": "eagle3",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    cfg, mod = make_input(enabled=True, model_path=bogus, model_arch="eagle")
    out = smart_decoding_expander(cfg, mod, block, make_ctx())
    assert out.scheme == "mtp"  # none/null 字面量等同空,model_based 被门挡住


def test_decoding_no_method_match_fallback():
    cfg, mod = make_input(enabled=True)
    assert smart_decoding_expander(cfg, mod, [], make_ctx()) is None  # 无草稿路径 + 空 methods → None


def test_decoding_missing_block_disabled():
    cfg, mod = make_input(enabled=True)
    assert smart_decoding_expander(cfg, mod, None, make_ctx()) is None


def test_decoding_topology_param_is_noop_after_scenario_refactor(tmp_path):
    """scenario 重构后,topology 参数不再参与过滤(scenario 路由在 loader 完成)。

    旧机制(scheme 级 deploy_modes)已废弃;新结构下 expander 只看扁平 decoding 列表,
    无论 topology 是什么,只要 block 含合格方案就产出。
    """
    draft = _make_draft_dir(tmp_path, ["EAGLE3LlamaForCausalLM"])
    cfg, mod = make_input(enabled=True, model_path=draft, model_arch="EAGLE3")
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "num_speculative_tokens": 3}},
        }
    ]
    # topology=pd_prefill / pd_decode / standalone / None 都不过滤
    for topo in ("pd_prefill", "pd_decode", "standalone", "multi_node", None):
        out = smart_decoding_expander(cfg, mod, block, make_ctx(draft), topology=topo)
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
            "strategies": {
                "pd_cluster": {
                    "default_strategy": True,
                    "nodes": [
                        {"role": "prefill", "index": 0, "sparse": [{"name": "performance_first"}]},  # 不含 decoding
                        {
                            "role": "decode",
                            "index": 0,
                            "decoding": [{"name": "mtp"}],
                            "sparse": [{"name": "performance_first"}],
                        },
                    ],
                }
            },
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
    d = tmp_path / "draft"
    d.mkdir()
    (d / "config.json").write_text(json.dumps({"architectures": architectures}))
    return str(d)


def test_draft_arch_matches_eagle3(tmp_path):
    """草稿 architectures 含 eagle3 → 选 eagle3 方案(非首序的 dflash)。"""
    draft = _make_draft_dir(tmp_path, ["Eagle3LlamaForCausalLM"])
    cfg, mod = make_input(enabled=True, model_path=draft, model_arch="EAGLE3")
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path", "num_speculative_tokens": 3}},
        },
        {
            "name": "dflash",
            "requires_model_path": True,
            "draft_arch": ["dflash"],
            "cli_params": {"speculative_config": {"method": "dflash", "model": "$path", "num_speculative_tokens": 15}},
        },
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "eagle3"


def test_draft_arch_matches_dflash(tmp_path):
    """草稿 architectures 含 dflash → 选 dflash(即使 eagle3 在前)。"""
    draft = _make_draft_dir(tmp_path, ["DFlashQwen3ForCausalLM"])
    cfg, mod = make_input(enabled=True, model_path=draft, model_arch="EAGLE3")
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {
            "name": "dflash",
            "requires_model_path": True,
            "draft_arch": ["dflash"],
            "cli_params": {"speculative_config": {"method": "dflash", "model": "$path"}},
        },
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "dflash"


def test_draft_arch_unknown_falls_to_generic_draft(tmp_path):
    """草稿 architectures 不匹配任何 draft_arch → 降级通用 draft(未声明 draft_arch)。"""
    draft = _make_draft_dir(tmp_path, ["SomeUnknownArch"])
    cfg, mod = make_input(enabled=True, model_path=draft)
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {
            "name": "draft",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"method": "draft_model", "model": "$path"}},
        },
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "draft"


def test_draft_arch_no_config_json_disables(caplog):
    """草稿路径非本地(无 config.json)→ 关闭投机,不降级通用 draft。

    仅支持本地挂载草稿目录:读不到架构时不猜、不当普通 draft(MR133 检视意见 2)。
    """
    import logging as _logging

    cfg, mod = make_input(enabled=True, model_path="hf/repo-id")
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {
            "name": "draft",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"method": "draft_model", "model": "$path"}},
        },
    ]
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, block, make_ctx("hf/repo-id"))
    assert out is None
    assert "unreadable" in caplog.text


def test_draft_path_as_config_file_disables(tmp_path, caplog):
    """传入 config.json 文件路径(非模型目录)→ 关闭投机,不降级通用 draft。

    原始输入会经 $path 渲染进 speculative_config.model,引擎需要模型目录,
    故门控只接受目录。文件里即便含可命中的专用架构(故意放 eagle3)也必须在
    目录校验处拦截,不得进入架构匹配。
    """
    import json
    import logging as _logging

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"architectures": ["Eagle3LlamaForCausalLM"]}))
    cfg, mod = make_input(enabled=True, model_path=str(cfg_file))
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
        {
            "name": "draft",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"method": "draft_model", "model": "$path"}},
        },
    ]
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, block, make_ctx(str(cfg_file)))
    assert out is None
    assert "unreadable" in caplog.text


def test_no_draft_path_falls_to_no_model():
    """无草稿路径 → no_model 方案(至多一个,取首序)。"""
    cfg, mod = make_input(enabled=True, model_path="")
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3"}},
        },
        {"name": "mtp", "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(""))
    assert out.scheme == "mtp"


def test_dspark_dual_form_no_draft(tmp_path):
    """dspark 无草稿形态(主模型自带权重,如 DeepSeek V4 Pro/Flash 0731):
    不声明 requires_model_path → 进 no_model 分支,无草稿路径也产出。
    """
    cfg, mod = make_input(enabled=True, model_path="")
    block = [
        {
            "name": "dspark",  # 无 requires_model_path → no_model
            "cli_params": {
                "speculative_config": {"method": "dspark", "num_speculative_tokens": 7, "draft_sample_method": "greedy"}
            },
        },
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(""))
    assert out.scheme == "dspark"
    sc = out.engine_params.engine_config.get("speculative_config", {})
    assert "model" not in sc  # 无草稿形态不带 model 字段


def test_dspark_dual_form_with_draft(tmp_path):
    """dspark 有草稿形态(如 Kimi K3 单独发草稿):
    声明 requires_model_path + draft_arch → config.json 含 dspark 时匹配,带 model 字段。
    """
    draft = _make_draft_dir(tmp_path, ["K3DSparkModel"])
    cfg, mod = make_input(enabled=True, model_path=draft)
    block = [
        {
            "name": "dspark",
            "requires_model_path": True,
            "draft_arch": ["dspark", "k3dspark"],
            "cli_params": {"speculative_config": {"method": "dspark", "model": "$path", "num_speculative_tokens": 7}},
        },
        {"name": "dspark", "cli_params": {"speculative_config": {"method": "dspark", "num_speculative_tokens": 7}}},
    ]
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out.scheme == "dspark"
    sc = out.engine_params.engine_config.get("speculative_config", {})
    assert "model" in sc  # 有草稿形态带 model 字段


def test_dspark_dual_form_coexistence(tmp_path):
    """同一 yaml 同时声明无草稿 dspark + 有草稿 dspark:
    无草稿路径 → 选无草稿 dspark(no_model,无 model);传 K3 草稿 → 选有草稿 dspark(model_based,带 model)。

    注:有草稿形态声明 draft_arch: ["dspark", "k3dspark"] —— K3DSparkModel 架构
    在双向数字边界下仅命中 k3dspark(dspark 前面是数字 3 被拦),单声明 ["dspark"]
    无法命中 K3 草稿(词边界回归,MR133 二轮检视)。
    """
    block = [
        {
            "name": "dspark",
            "requires_model_path": True,
            "draft_arch": ["dspark", "k3dspark"],
            "cli_params": {"speculative_config": {"method": "dspark", "model": "$path"}},
        },
        {"name": "dspark", "cli_params": {"speculative_config": {"method": "dspark", "num_speculative_tokens": 7}}},
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


def test_decoding_dspark_mismatch_disables(tmp_path, caplog):
    """dspark 专用草稿错配:资产未声明 dspark 草稿形态 → None+warning,不喂 generic draft。

    dspark 双形态:DeepSeek 系内置权重(无草稿),Kimi-K3 外部草稿
    (requires_model_path + draft_arch 含 dspark/k3dspark)。无草稿形态资产收到
    dspark 草稿时不得错配喂给其他方法(MR133 检视意见 4)。
    """
    import logging as _logging

    draft = _make_draft_dir(tmp_path, ["K3DSparkModel"])
    block = [
        {"name": "dspark", "cli_params": {"speculative_config": {"method": "dspark", "num_speculative_tokens": 7}}},
        {
            "name": "draft_model",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"model": "$path", "num_speculative_tokens": 4}},
        },
    ]
    cfg, mod = make_input(enabled=True, model_path=draft)
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out is None
    assert "dspark" in caplog.text


def test_decoding_unreadable_draft_dir_disables(caplog, tmp_path):
    """本地 config.json 读不到(HF repo id/未挂载/不可读)→ None+warning,不猜。

    仅支持本地挂载草稿目录(MR133 检视意见 2 方案 A):读不到架构时
    不得把草稿当普通 draft 喂给 generic 方案。
    """
    import logging as _logging

    hf_repo_id = "org/eagle3-draft-model"  # 控制节点不存在的路径
    block = [
        {
            "name": "draft_model",
            "requires_model_path": True,
            "cli_params": {"speculative_config": {"model": "$path", "num_speculative_tokens": 4}},
        },
    ]
    cfg, mod = make_input(enabled=True, model_path=hf_repo_id)
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, block, make_ctx(hf_repo_id))
    assert out is None
    assert "unreadable" in caplog.text
    # 本地目录但无 config.json 同样不可读
    empty = tmp_path / "empty-draft"
    empty.mkdir()
    cfg2, mod2 = make_input(enabled=True, model_path=str(empty))
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out2 = smart_decoding_expander(cfg2, mod2, block, make_ctx(str(empty)))
    assert out2 is None


# ── 词边界匹配回归(MR133 二轮检视:eagle 不得匹配 eagle3)──


def test_eagle_keyword_does_not_match_eagle3_arch(tmp_path, caplog):
    """eagle-only 资产 + Eagle3 草稿 → None(词边界),不再误产出 method: eagle。

    普通子串匹配时 'eagle' in 'eagle3llamaforcausallm' 成立,22 个 eagle-only
    资产(Mistral 系)收到 Eagle3 草稿会错误生成 method: eagle → 引擎层崩。
    双向数字边界:后面跟 3 拦住 eagle;守卫层检出 eagle3 走错配关闭。
    """
    import logging as _logging

    draft = _make_draft_dir(tmp_path, ["Eagle3LlamaForCausalLM"])
    block = [
        {
            "name": "eagle",
            "requires_model_path": True,
            "draft_arch": ["eagle"],
            "cli_params": {"speculative_config": {"method": "eagle", "model": "$path"}},
        },
    ]
    cfg, mod = make_input(enabled=True, model_path=draft)
    with caplog.at_level(_logging.WARNING, logger="wings_accel.decoders"):
        out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out is None  # eagle3 草稿不是 eagle 草稿
    assert "eagle3" in caplog.text  # 守卫检出的是 eagle3(不是 eagle)


def test_eagle3_keyword_does_not_match_eagle_arch(tmp_path):
    """反向:eagle3-only 资产 + eagle 草稿 → None(词边界防反向误命中)。"""
    draft = _make_draft_dir(tmp_path, ["MistralEagleForCausalLM"])
    block = [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "draft_arch": ["eagle3"],
            "cli_params": {"speculative_config": {"method": "eagle3", "model": "$path"}},
        },
    ]
    cfg, mod = make_input(enabled=True, model_path=draft)
    out = smart_decoding_expander(cfg, mod, block, make_ctx(draft))
    assert out is None


def test_word_boundary_matches_real_arch_shapes(tmp_path):
    """词边界保持既有资产兼容:真实架构名各形态仍正确命中。"""
    from wings_accel.decoders import _keyword_in_arch

    # eagle 方法命中:eagle 结尾 / eagle 词中(CamelCase 连写)
    assert _keyword_in_arch("eagle", "deepseekv2forcausallmeagle")
    assert _keyword_in_arch("eagle", "mistraleagleforcausallm")
    assert _keyword_in_arch("eagle3", "llamaforcausallmeagle3")
    assert not _keyword_in_arch("eagle", "llamaforcausallmeagle3")  # 核心回归
    # dspark 双形态:DeepSeek 与 K3 各归各
    assert _keyword_in_arch("dspark", "deepseekdsparkforcausallm")
    assert _keyword_in_arch("k3dspark", "k3dsparkmodel")
    assert not _keyword_in_arch("dspark", "k3dsparkmodel")  # 前缀数字拦住


def test_ernie_mtp_without_draft_path():
    """ERNIE-MTP 使用主模型 checkpoint 内置权重，不要求外部草稿路径。"""
    cfg, mod = make_input(enabled=True, model_path="")
    block = [
        {
            "name": "ernie_mtp",
            "cli_params": {
                "speculative_config": {
                    "method": "ernie_mtp",
                    "num_speculative_tokens": 1,
                }
            },
        },
    ]

    out = smart_decoding_expander(cfg, mod, block, make_ctx(""))

    assert out is not None
    assert out.scheme == "ernie_mtp"
    assert out.engine_params.engine_config["speculative_config"] == {
        "method": "ernie_mtp",
        "num_speculative_tokens": 1,
    }
