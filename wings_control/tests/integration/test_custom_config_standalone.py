"""E2E test — 自定义传参方式(--config-file)standalone 最小闭环(阶段 1)。

覆盖:
(a) resolve_custom_config:params 进入 engine_config_traces,config_file 层、user_cli 最高优先
(b) params 不匹配 recipe:config-file 参数完全以用户为准,不落 recipe 值(tp 覆盖等)
(c) 黑名单(§4.1)params 静默弃用 + 记 config_file_dropped 审计;CLI 侧 model 仍由 translator 供
(d) env 注入到 start_command.sh / repro.sh;config_file_env 层 allow_unsafe 放行 $(hostname)
(e) 普通 env(${VAR} 合法引用仍安全校验通过;不安全的 $(...) 普通 env 值应经 _validate 拒绝)
(f) 三件产物(start_command.sh / repro.sh / audit.json)落盘 + bash -n 语法通过
(g) audit.json:config_file_params(applied+dropped)与 user_cli_params 均含
(h) multi_node/PD topology → NotImplementedError(custom 仅 standalone,阶段0拍板 §3/§4)
(i) resolve_pipeline_custom / run_pipeline_custom 复用 hardware/version + 三件产物
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.core.config_resolver import resolve_custom_config
from wings_ctl.core.models import (
    CustomConfigFile,
    PipelineRequest,
    ResolvedEnv,
    Target,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.pipeline import resolve_pipeline_custom, run_pipeline_custom
from wings_ctl.rendering.script_builder import build_scripts


CONFIG_FILE = CustomConfigFile(
    params={
        # 引擎原生参数,用户自管(config_file 层)。
        # kebab-case key 也应归一 snake_case(经 resolve_custom_config._to_snake)。
        "tensor-parallel-size": 2,
        "gpu-memory-utilization": 0.9,
        "max-num-seqs": 256,
        "enable-prefix-caching": True,
        # 命中黑名单(§4.1 归 CLI):应被静默弃用,不落地。
        "host": "1.2.3.4",
        "model_path": "/weights/should/be/ignored",
        "nnodes": 4,
        # 各节点一致、用户可填(点3):不在黑名单 → 应落入最终 params。
        "data_parallel_rpc_port": 13389,
        # 全局 DP 由用户自管(§4.4),非黑名单:应落入最终 params。
        "data_parallel_size": 8,
    },
    env={
        # 用户自管 env,允许 $(hostname) 命令替换(unsafe 渲染)。
        "OTEL_RESOURCE_ATTRIBUTES": "service.instance.id=$(hostname)",
        # 普通静态值,也应渲染(双引号)。
        "MY_STATIC": "static-value",
        # vllm env 黑名单(框架派生网卡):应被静默弃用。
        "GLOO_SOCKET_IFNAME": "eth0",
    },
)

# CLI 侧提供第 1 页参数:model-path → model(经 CLITranslator 落入 user_cli)。
CLI_OVERRIDES = {"model": "/weights/MiniMax-M3-MXFP8", "served_model_name": "MiniMax-M3-MXFP8"}


def _env(config_root: Path, hardware_info_path: Path) -> ResolvedEnv:
    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        hardware = resolve_hardware(hardware_info_path)
        engine_version = resolve_engine_version(
            config_root, hardware.hardware_family, engine="vllm"
        )
        return ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version)
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def _resolve(config_root: Path, hardware_info_path: Path, *, config_file=CONFIG_FILE,
             user_input=None, topology=Topology.STANDALONE):
    user_input = user_input or UserInput(cli_overrides=CLI_OVERRIDES)
    return resolve_custom_config(
        _env(config_root, hardware_info_path),
        Target(model_name="MiniMax-M3-MXFP8", topology=topology, engine="vllm"),
        config_file=config_file,
        user_input=user_input,
        device_count=2,
    )


def _request(config_root: Path, hardware_info_path: Path) -> PipelineRequest:
    return PipelineRequest(
        target=Target(model_name="MiniMax-M3-MXFP8", topology=Topology.STANDALONE, engine="vllm"),
        hardware_info_path=hardware_info_path,
        config_root=config_root,
        user_input=UserInput(cli_overrides=CLI_OVERRIDES),
        device_count=2,
    )


# ─── (a)(b) params 进入 traces + custom 优先于 recipe + CLI 最高优先 ───


def test_a_params_in_engine_config_traces(config_root, hardware_info_path):
    """params 进入 engine_config_traces,层名为 config_file。"""
    resolved = _resolve(config_root, hardware_info_path)
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 2
    assert resolved.engine_config_traces["tensor_parallel_size"].final_layer == "config_file"
    assert resolved.engine_config_traces["gpu_memory_utilization"].final_value == 0.9
    assert resolved.engine_config_traces["max_num_seqs"].final_value == 256
    # kebab-case → snake_case 归一
    assert "tensor_parallel_size" in resolved.engine_config_traces
    assert "tensor-parallel-size" not in resolved.engine_config_traces


def test_b_custom_overrides_recipe_and_cli_highest(config_root, hardware_info_path):
    """config-file 参数以用户为准(不落 recipe);CLI(user_cli)为最高优先。

    传入 config-file 的 max_num_seqs 与 CLI 的 max_num_seqs → 取 CLI 侧。
    """
    resolved = _resolve(config_root, hardware_info_path)
    # model 由 CLI 侧提供(user_cli 层),不被 config-file 的 model_path 影响
    model_tr = resolved.engine_config_traces["model"]
    assert model_tr.final_value == "/weights/MiniMax-M3-MXFP8"
    assert model_tr.final_layer == "user_cli"

    resolved2 = _resolve(
        config_root, hardware_info_path,
        user_input=UserInput(cli_overrides={**CLI_OVERRIDES, "max_num_seqs": 512}),
    )
    assert resolved2.engine_config_traces["max_num_seqs"].final_value == 512
    assert resolved2.engine_config_traces["max_num_seqs"].final_layer == "user_cli"


# ─── (c) 黑名单 params 静默弃用 + audit ───


def test_c_blacklist_params_dropped(config_root, hardware_info_path):
    """黑名单 params(host/model_path/nnodes)被静默弃用,不落地、进 config_file_dropped。"""
    resolved = _resolve(config_root, hardware_info_path)
    # host:config-file 填的 1.2.3.4 被弃用,host 取 builtin_default 0.0.0.0
    assert resolved.engine_config_traces["host"].final_value == "0.0.0.0"
    assert resolved.engine_config_traces["host"].final_layer == "builtin_default"
    # model 不被 config-file 的 model_path 覆盖(仍 user_cli)。model_path 黑名单不落地。
    assert "model_path" not in resolved.engine_config_traces
    assert "nnodes" not in resolved.engine_config_traces
    # 全局 DP 由用户自管(§4.4):data_parallel_size 不属黑名单 → 落入最终 params。
    assert resolved.engine_config_traces["data_parallel_size"].final_value == 8

    dropped = [d for d in resolved.config_file_params if d["status"] == "dropped"]
    dropped_keys = {d["key"] for d in dropped}
    assert {"host", "model_path", "nnodes"} <= dropped_keys
    assert all("blacklist" in (d["reason"] or "") for d in dropped)

    applied = [d for d in resolved.config_file_params if d["status"] == "applied"]
    applied_keys = {d["key"] for d in applied}
    assert "tensor_parallel_size" in applied_keys
    assert "max_num_seqs" in applied_keys
    assert "data_parallel_size" in applied_keys


def test_c2_env_blacklist_dropped(config_root, hardware_info_path):
    """vllm env 黑名单(GLOO_SOCKET_IFNAME)被静默弃用,不落地、进 config_file_dropped。

    普通 env 与 unsafe env 仍进入 env_traces。
    """
    resolved = _resolve(config_root, hardware_info_path)
    # 黑名单 env 不入 env_traces
    assert "GLOO_SOCKET_IFNAME" not in resolved.env_traces
    # 普通 + unsafe env 保留
    assert resolved.env_traces["MY_STATIC"].final_value == "static-value"
    assert resolved.env_traces["OTEL_RESOURCE_ATTRIBUTES"].final_value == "service.instance.id=$(hostname)"

    dropped = [d for d in resolved.config_file_params if d["status"] == "dropped"]
    assert any(d["key"] == "GLOO_SOCKET_IFNAME" and "env" in (d["reason"] or "") for d in dropped)


def test_c3_rpc_port_user_fillable(config_root, hardware_info_path):
    """data_parallel_rpc_port 各节点一致、用户可填(点3):不在黑名单,落入最终 params。

    data_parallel_address 与 rpc_port 不同:框架权威(arg_utils 用 host_ip/master_addr 派生),
    vllm 系"用户填不出"→ vllm / vllm-ascend 均在黑名单。这里验 rpc_port 用户可填。
    """
    resolved = _resolve(config_root, hardware_info_path)
    assert resolved.engine_config_traces["data_parallel_rpc_port"].final_value == 13389
    assert resolved.engine_config_traces["data_parallel_rpc_port"].final_layer == "config_file"
    # data_parallel_address 框架权威(vllm 黑名单):用户未填 → 不在 traces(非被弃,只是没填)。
    assert "data_parallel_address" not in resolved.engine_config_traces


def test_c4_blacklist_is_per_engine(config_root, hardware_info_path):
    """黑名单按 engine 区分与叠加(sglang 的 dp_size 在 sglang 黑名单,不在 vllm)。

    端到端只验 vllm(本配置资产仅有 vllm 目录);sglang/mindie 走黑名单函数单测(无需 engine 资产)。
    """
    from wings_ctl.core.config_resolver import (
        _config_file_env_blacklist,
        _config_file_params_blacklist,
        _filter_config_file_blacklist,
    )

    vllm_bl = _config_file_params_blacklist("vllm")
    sglang_bl = _config_file_params_blacklist("sglang")
    # data_parallel_size(全局 DP)用户自管,两引擎都不拦;data_parallel_size_local 等派生键仅 vllm 系拦。
    assert "data_parallel_size" not in vllm_bl and "data_parallel_size" not in sglang_bl
    assert "data_parallel_size_local" in vllm_bl
    assert "data_parallel_size_local" not in sglang_bl
    assert "model" in vllm_bl and "model" in sglang_bl
    # master_addr/headless 仅 vllm 系(CLI --master-addr/--headless);sglang 用 --dist-init-addr
    assert "master_addr" in vllm_bl and "headless" in vllm_bl
    assert "master_addr" not in sglang_bl and "headless" not in sglang_bl
    # dist_init_addr **不在**黑名单(设计 §5.1.3 端口用户可填;host 由派生层覆盖),vllm 也无
    assert "dist_init_addr" not in sglang_bl and "dist_init_addr" not in vllm_bl
    unknown_bl = _config_file_params_blacklist("mindie")
    assert "model" in unknown_bl and "dist_init_addr" not in unknown_bl
    assert "master_addr" not in unknown_bl and "headless" not in unknown_bl
    # env 黑名单:vllm-ascend 才拦 HCCL_IF_IP;vllm 不拦
    assert "HCCL_IF_IP" in _config_file_env_blacklist("vllm-ascend")
    assert "HCCL_IF_IP" not in _config_file_env_blacklist("vllm")

    # vllm 端到端:data_parallel_size(全局 DP)用户自管 → 保留(非黑名单)。
    from wings_ctl.core.models import CustomConfigFile

    cf = CustomConfigFile(params={"data_parallel_size": 8}, env={})
    resolved_vllm = _resolve(config_root, hardware_info_path, config_file=cf)
    assert resolved_vllm.engine_config_traces["data_parallel_size"].final_value == 8

    # sglang 过滤函数单测:data_parallel_size 用户自管(留);dist_init_addr 现不在黑名单
    # (端口用户可填),故同样保留——端口由用户 config-file 填,host 由派生层覆盖。
    kept, dropped = _filter_config_file_blacklist(
        {"data_parallel_size": 8, "dist_init_addr": "x"}, engine="sglang"
    )
    assert "data_parallel_size" in kept
    assert "dist_init_addr" in kept
    assert dropped == []


# ─── (d)(e) env 渲染:unsafe 放行 / 普通安全校验 ───


def test_d_env_unsafe_rendered_in_scripts(config_root, hardware_info_path, tmp_path):
    """config_file env 的 $(hostname) 双引号放行,出现在 start/repro;allow_unsafe=True。"""
    resolved = _resolve(config_root, hardware_info_path)
    env_attr = resolved.env_traces["OTEL_RESOURCE_ATTRIBUTES"]
    assert env_attr.final_layer == "config_file_env"
    assert env_attr.allow_unsafe is True

    start_path, repro_path = build_scripts(resolved, tmp_path)
    for p in (start_path, repro_path):
        content = p.read_text()
        assert 'export OTEL_RESOURCE_ATTRIBUTES="service.instance.id=$(hostname)"' in content
        assert 'export MY_STATIC="static-value"' in content
    # bash -n 语法通过(双引号内 $(hostname) 不破坏语法)
    subprocess.run(["bash", "-n", str(start_path)], check=True)
    subprocess.run(["bash", "-n", str(repro_path)], check=True)


def test_e_non_config_file_env_still_validated(config_root, hardware_info_path):
    """普通 env(非 config_file_env 层)值含 $(...) 仍被安全校验拒绝。"""
    from wings_ctl.rendering.env_renderer import render_env_export

    with pytest.raises(ValueError, match="unsafe shell constructs"):
        render_env_export("X", "a=$(rm -rf /)")


def test_e2_env_trace_allow_unsafe_default_false(config_root, hardware_info_path):
    """sigma: 非 config_file env 层的 TracedValue.allow_unsafe 默认 False。"""
    from wings_ctl.core.config_resolver import MergeLayer, trace_merge

    merged = trace_merge([
        MergeLayer("normal_env", {"A": "1"}, "f.yaml", "env"),
    ])
    assert merged["A"].allow_unsafe is False


# ─── (f)(g) 三件产物 + audit ───


def test_f_three_artifacts_generated(config_root, hardware_info_path, tmp_path):
    """run_pipeline_custom 落三件产物:start_command.sh / repro.sh / audit.json。"""
    os.environ["WINGS_START_LOG"] = str(tmp_path / "wings_start.log")
    try:
        resolved, start_path, repro_path, audit_path = run_pipeline_custom(
            _request(config_root, hardware_info_path), CONFIG_FILE, tmp_path
        )
    finally:
        os.environ.pop("WINGS_START_LOG", None)

    assert start_path.exists()
    assert repro_path.exists()
    assert audit_path.exists()

    argv = build_argv(resolved.engine_config_traces, engine="vllm")
    assert "--tensor-parallel-size 2" in shlex.join(argv)
    assert "--max-num-seqs 256" in shlex.join(argv)
    assert "/weights/MiniMax-M3-MXFP8" in shlex.join(argv)
    # 黑名单参数不落地
    assert "--nnodes" not in shlex.join(argv)
    # config_file env 注入
    start_content = start_path.read_text()
    assert '$(hostname)' in start_content

    subprocess.run(["bash", "-n", str(start_path)], check=True)
    subprocess.run(["bash", "-n", str(repro_path)], check=True)


def test_g_audit_config_and_user_cli_params(config_root, hardware_info_path, tmp_path):
    """audit.json 含 config_file_params(applied+dropped)与 user_cli_params。"""
    resolved = _resolve(config_root, hardware_info_path)
    audit_path = emit_audit(resolved, tmp_path)
    audit = json.loads(audit_path.read_text())

    cfs = audit["config_file_params"]
    assert any(d["status"] == "applied" and d["key"] == "tensor_parallel_size" for d in cfs)
    assert any(d["status"] == "dropped" and d["key"] == "nnodes" for d in cfs)
    assert any(d["key"] == "model" for d in audit["user_cli_params"])

    # engine_config / env trace 均带 full 来源链
    assert audit["engine_config"]["max_num_seqs"]["final_layer"] == "config_file"
    assert audit["env"]["OTEL_RESOURCE_ATTRIBUTES"]["final_layer"] == "config_file_env"


# ─── (h) PD / 缺 placement → 拒绝;multi_node 需 placement ───


@pytest.mark.parametrize("topology", [Topology.PD_PREFILL, Topology.PD_DECODE])
def test_h_pd_raises(config_root, hardware_info_path, topology):
    """custom 路径 PD 分离 → NotImplementedError(阶段0拍板 §3 单独立项,阶段2 仍未实现)。"""
    with pytest.raises(NotImplementedError, match="multi_node"):
        _resolve(config_root, hardware_info_path, topology=topology)


def test_h_multinode_missing_placement_raises(config_root, hardware_info_path):
    """custom multi_node 缺运行时 placement(NODE_IPS/RANK_IP)→ ValueError 引导早爆。"""
    with pytest.raises(ValueError, match="分布式运行时上下文"):
        _resolve(config_root, hardware_info_path, topology=Topology.MULTI_NODE)


# ─── (i) resolve_pipeline_custom 复用 hardware/version ───


def test_i_pipeline_custom_missing_model_raises(config_root, hardware_info_path):
    """CLI 未提供 model(user_cli 无 model)→ resolve_custom_config 直接报错(引导早爆)。"""
    with pytest.raises(ValueError, match="model"):
        _resolve(
            config_root, hardware_info_path,
            user_input=UserInput(cli_overrides={}),  # 无 model
        )


def test_pipeline_custom_end_to_end(config_root, hardware_info_path, tmp_path):
    """resolve_pipeline_custom 产出可 build_argv 的 config;模型 path 经 CLI 供。**

    验证 pipeline 层复用 hardware/version 解析 + config-file 参数进入最终 argv。
    """
    resolved = resolve_pipeline_custom(_request(config_root, hardware_info_path), CONFIG_FILE)
    argv = build_argv(resolved.engine_config_traces, engine="vllm")
    joined = shlex.join(argv)
    assert "vllm serve /weights/MiniMax-M3-MXFP8" in joined
    assert "--tensor-parallel-size 2" in joined
    assert "--gpu-memory-utilization 0.9" in joined
