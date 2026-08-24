"""从项目完整模板生成 MindIE 2.3.0 config.json。

本模块只读取版本化项目模板并决定字段属于哪个嵌套节点，不读取 ranktable、厂商
安装目录或环境变量。单机与双机共享模型和调度字段；双机的 ``worldSize`` 使用本地
设备数，而 ``tp`` 使用全局规模，二者不得互换。runtime 只负责把最终完整 JSON
原子落盘，不再合并引擎内部 ``conf/config.json``。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Union

from wings_ctl.engines.mindie.dual_node import MindieDualNodePlan
from wings_ctl.engines.mindie.standalone import MindieStandalonePlan


MindiePlan = Union[MindieStandalonePlan, MindieDualNodePlan]

# config.json 与健康探测必须共享同一份管理端点事实。模板中的值仍作为可读默认，
# 但最终运行配置始终由这组常量投影，避免模板与 Extension profile 独立漂移。
MINDIE_MANAGEMENT_HOST = "127.0.0.2"
MINDIE_MANAGEMENT_PORT = 1026


def build_config_overrides(plan: MindiePlan) -> Dict[str, Any]:
    """构造仅包含当前能力拥有字段的 2.3.0 嵌套覆盖。"""
    common = plan.common
    if isinstance(plan, MindieDualNodePlan):
        server_host = plan.master_ip
        device_ids = list(plan.local_device_ids)
        local_world_size = plan.local_world_size
        multi_node = True
    else:
        server_host = common.host
        device_ids = list(plan.device_ids)
        local_world_size = plan.local_world_size
        multi_node = False

    model_config: Dict[str, Any] = {
        "modelName": common.model_name,
        "modelWeightPath": common.model_path,
        "worldSize": local_world_size,
        "trustRemoteCode": common.trust_remote_code,
    }
    parallel = plan.parallel
    if parallel.tp is not None:
        # 这些字段是 MindIE 2.3.0 的领域投影，不复用公共 tensor/data_parallel_size。
        model_config["tp"] = parallel.tp
    if parallel.dp is not None:
        model_config["dp"] = parallel.dp
    if parallel.ep_enabled:
        if (
            parallel.moe_tp is None
            or parallel.moe_ep is None
            or parallel.ep_level is None
            or parallel.model_family is None
        ):
            raise ValueError("MindIE EP plan is incomplete")
        model_config.update(
            {
                "moe_tp": parallel.moe_tp,
                "moe_ep": parallel.moe_ep,
                "models": {
                    parallel.model_family: {"ep_level": parallel.ep_level},
                },
            }
        )

    overrides: Dict[str, Any] = {
        "server": {"ipAddress": server_host, "port": common.port},
        "backend": {
            "npuDeviceIds": [device_ids],
            "multiNodesInferEnabled": multi_node,
        },
        "model_deploy": {
            "maxSeqLen": common.max_seq_len,
            "maxInputTokenLen": common.max_input_token_len,
        },
        "model_config": model_config,
        "schedule": {
            "maxPrefillTokens": common.max_prefill_tokens,
            "maxIterTimes": common.max_iter_times,
        },
    }
    if parallel.ep_enabled:
        overrides["root"] = {"enable_ep_moe": True}
    return overrides


def _load_template(path: Path) -> Dict[str, Any]:
    """读取项目模板并校验 projector 依赖的结构；禁止镜像配置 fallback。"""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load MindIE config template {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"MindIE config template must be an object: {path}")
    if document.get("Version") != "1.0.0":
        raise ValueError(f"MindIE 2.3.0 config template requires Version='1.0.0', got {document.get('Version')!r}")
    for meta_key in ("_comment", "_usage"):
        document.pop(meta_key, None)
    return document


def _require_mapping(parent: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"MindIE config template field {key} must be an object")
    return value


def _deep_update(target: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """只对显式覆盖字段递归合并，保留完整模板中的稳定子结构。"""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def build_full_config(plan: MindiePlan) -> Dict[str, Any]:
    """生成可直接交给 MindIE 的完整配置，不产生任何文件副作用。"""
    config = _load_template(plan.common.config_template_path)
    overrides = build_config_overrides(plan)

    server = _require_mapping(config, "ServerConfig")
    backend = _require_mapping(config, "BackendConfig")
    deploy = _require_mapping(backend, "ModelDeployConfig")
    schedule = _require_mapping(backend, "ScheduleConfig")
    model_configs = deploy.get("ModelConfig")
    if not isinstance(model_configs, list) or not model_configs or not isinstance(model_configs[0], dict):
        raise ValueError(
            "MindIE config template field BackendConfig.ModelDeployConfig.ModelConfig must be a non-empty object array"
        )

    _deep_update(server, overrides["server"])
    _deep_update(
        server,
        {
            "managementIpAddress": MINDIE_MANAGEMENT_HOST,
            "managementPort": MINDIE_MANAGEMENT_PORT,
        },
    )
    _deep_update(backend, overrides["backend"])
    _deep_update(deploy, overrides["model_deploy"])
    _deep_update(model_configs[0], overrides["model_config"])
    _deep_update(schedule, overrides["schedule"])
    _deep_update(config, overrides.get("root", {}))
    return config
