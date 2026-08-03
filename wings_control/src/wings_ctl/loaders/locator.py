"""locator — 配置文件目录定位与加载。

负责:
- 定位 _platform.yaml(平台默认层)
- 扫描 models/ 目录,按 name_pattern 匹配模型 yaml

纯 IO 层,不含合并逻辑。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wings_ctl.hardware.resolver import strip_gpu_mem_suffix
from wings_ctl.loaders.yaml_loader import load_yaml

logger = logging.getLogger(__name__)

# 卡型基名(下发 resourceCardName 去显存后缀、casefold)→ config 目录名。
# 只装"卡名 ≠ 目录名"的条目:
#   - 昇腾芯片名 → 架构代目录(config 按架构代建目录,芯片名对不上,须显式映射);
#   - 命名冗长/不统一的 NV 名(如带厂商前缀)→ 目录名。
# 缺省不入表:归一后卡名 == 目录名者走精确/剥后缀直通(见 resolve_family_dir)。
# key 一律 casefold 存;新增硬件在此加一行(紧挨 config 目录维护)。
_ALIAS: Dict[str, str] = {
    # 填法:key = casefold(去显存后缀的 resourceCardName),value = config 目录名。
    # (resolve_family_dir 先 strip_gpu_mem_suffix 再 casefold 查本表,key 必须与之一致。)
    #
    # 示例① 命名冗长的 NV 卡(有对应 recipe 目录、且下发名 ≠ 目录名时才加):
    #   "nvidia-a800-80gb-pcie": "a800",   # 下发 "NVIDIA-A800-80GB-PCIe_75G" → 去后缀+casefold → 命中 a800 目录
    # 示例② 昇腾芯片 → 架构代目录(config 按架构代建目录,芯片名对不上):
    #   "ascend910b": "ascend-a3",         # 下发 "Ascend910B_64G" → 命中 ascend-a3 目录
    #
    # 缺省不入表:去后缀+casefold 后 == 目录名者(h100 / b200 / mi300x 等)走精确/剥后缀直通,不占本表。
    "ascend910b": "ascend-a2",    # Ascend910B
    "ascend910": "ascend-a3",     # Ascend910
    "ascend910c": "ascend-a3",    # Ascend910C
    "h20": "h20_96G",             # H20
    "h20-3e": "h20_141G",         # H20-3e
    "rtx-pro-5000-48gb-blackwell": "rtx_pro_5000_48G",    # RTX-PRO-5000-48GB-Blackwell
    "rtx-pro-5000-72gb-blackwell": "rtx_pro_5000_72G",    # RTX-PRO-5000-72GB-Blackwell
}


def resolve_family_dir(
    config_root: Path,
    engine: str,
    hardware_family: str,
    version: str,
    has_version_dir: bool,
) -> str:
    """把下发的 hardware_family 解析成实际存在的 config 目录名(单一判定点)。

    下发值是资源域词汇(resourceCardName + 显存后缀,大小写不一、可能冗长),
    config 目录是资产域词汇;三步把前者映射到后者(大小写无关,回填磁盘真实目录名):
      1. 精确:下发原值(含显存后缀)直接命中显存敏感目录(如 h20_96G / h20_141G,
         显存即区分键,优先于别名——避免裸卡型别名吞掉显存档);
      2. 别名表:下发值去显存后缀得裸卡型,卡名 ≠ 目录名者
         (昇腾芯片→架构代 / 冗长 NV 名)显式映射到目录;
      3. 剥后缀:去掉 _<N>G 用裸卡名命中普通目录(如 H100_80G → h100,后缀冗余)。
    三步皆不中 → fail-fast:该卡 / 该显存档无 recipe 资产(不静默兜底,避免错配)。

    顺序要点:精确先于别名。h20 同型号有 h20_96G / h20_141G 两个显存敏感目录,
    下发 h20_141G 必须精确命中 h20_141G,不能被 _ALIAS["h20"]→"h20_96G" 一律吞掉;
    精确未命中时再按去后缀的裸卡型查 _ALIAS,保留 Ascend910B_64G 等带后缀别名硬件的兼容性。

    Args:
        config_root: 配置根目录,内含 engines/ 子树。
        engine: 引擎名。
        hardware_family: 下发原值(可能带 _<N>G 后缀、大小写不一)。
        version: 引擎版本;仅 has_version_dir=True 时用于拼版本层。
        has_version_dir: 是否含版本层目录(与 build_models_dir 口径一致)。

    Returns:
        磁盘上真实存在的 config 目录名(供 build_models_dir 定位 + accel gpu_type)。

    Raises:
        FileNotFoundError: 精确 / 别名 / 剥后缀三步都没命中任何 recipe 目录。
    """
    # 列出该 engine[/version] 下所有含 models/ 的硬件目录,按 casefold 建"归一名→真实名"索引:
    # 匹配大小写无关,命中后回填磁盘真实目录名(config 变体目录用大写 G,不能只比小写)。
    base = config_root / "engines" / engine
    parent = base / f"v{version.lstrip('v')}" if has_version_dir else base
    candidates: Dict[str, str] = {}
    if parent.is_dir():
        for child in sorted(parent.iterdir()):
            if (child / "models").is_dir():
                candidates[child.name.casefold()] = child.name

    card = strip_gpu_mem_suffix(hardware_family)  # 去显存后缀得卡型基名(无后缀时 == 原值,即裸卡型)

    # ① 精确:下发原值(含显存后缀)直接命中显存敏感目录,优先于别名。
    # h20_96G / h20_141G 这类同型号多显存档卡,显存即区分键,必须按显存精确命中,
    # 不能落到按裸卡型查的别名默认档(否则 h20_141G 会被 _ALIAS["h20"] 吞成 h20_96G)。
    if hardware_family.casefold() in candidates:
        return candidates[hardware_family.casefold()]

    # ② 别名:完整 hardware_family 精确未命中后,按去后缀的裸卡型查映射。
    # 这样 h20_141G 已在 ① 精确命中,不会被 h20 默认档吞掉;而 Ascend910B_64G 等
    # "带显存后缀 + 卡名与目录名不同"的既有别名仍能落到对应架构目录。
    aliased = _ALIAS.get(card.casefold())
    if aliased:
        if aliased.casefold() in candidates:
            logger.info("resolve_family_dir: '%s' 经别名 → %s", hardware_family, candidates[aliased.casefold()])
            return candidates[aliased.casefold()]
        # 别名命中但目标目录不存在 = _ALIAS 配错(填表时目录名写错);不静默,记 warn 再回落剥后缀。
        logger.warning(
            "resolve_family_dir: 别名 '%s' → '%s' 但该目录在 engine='%s' 下不存在(_ALIAS 配置可能有误);回落剥后缀",
            card.casefold(), aliased, engine,
        )

    # ③ 剥后缀:普通卡带冗余显存后缀,去掉后用裸卡名命中普通目录(如 H100_80G → h100)。
    if card.casefold() in candidates:
        return candidates[card.casefold()]

    raise FileNotFoundError(
        f"hardware_family='{hardware_family}' 无配置资产"
        f"(engine='{engine}';归一卡型='{card}';已试 精确/别名/剥后缀)。"
        "请确认下发的 hardware_family 带正确显存后缀(如 h20_96G)、且该硬件 recipe 已下发。"
    )


def build_models_dir(
    config_root: Path,
    engine: str,
    hardware_family: str,
    version: str,
    has_version_dir: bool,
) -> Path:
    """拼接 models 目录路径 —— 全仓唯一的"目录布局规则"来源。

    布局:
    - 有版本层(has_version_dir=True): engines/{engine}/v{version}/{hardware_family}/models
    - 无版本层(has_version_dir=False): engines/{engine}/{hardware_family}/models

    版本层有无由上游目录自判决定(目录名像不像 vX.Y.Z),不由引擎名决定;
    无版本层引擎(如 vllm)的 version 参数不参与拼接。

    Args:
        config_root: 配置根目录,内含 engines/ 子树。
        engine: 引擎名(如 "vllm" / "vllm-ascend")。
        hardware_family: 硬件族标识(如 "h200")。
        version: 引擎版本字符串;仅 has_version_dir=True 时用于拼 v{version} 层。
        has_version_dir: 是否含版本层目录(上游 version_resolver 目录自判产出)。

    Returns:
        指向 .../models 目录的 Path(不保证存在,存在性由调用方校验)。
    """
    base = config_root / "engines" / engine
    if has_version_dir:
        return base / f"v{version.lstrip('v')}" / hardware_family / "models"
    return base / hardware_family / "models"


def load_platform_config(
    config_root: Path,
    hardware_family: str,
    engine: str,
    version: str,
    has_version_dir: bool = True,
) -> Tuple[Dict[str, Any], Optional[Path]]:
    """加载平台默认配置(default_model.yaml)。

    Args:
        config_root: 配置根目录,内含 engines/ 子树。
        hardware_family: 硬件族标识(如 "h200");无版本层引擎下直接作 engines/{engine}/ 的下一层目录。
        engine: 引擎名(如 "vllm" / "vllm-ascend")。
        version: 引擎版本字符串(来自 ENGINE_VERSION env)。
                 仅有版本层的引擎(has_version_dir=True)用它拼版本目录;
                 无版本层引擎(has_version_dir=False)此参数不参与路径拼接。
        has_version_dir: 由上游 version_resolver 目录自判得出的开关。
                 True → 路径含版本层;False → 完全跳过版本目录拼接。
                 注意:有/无版本层由"目录名像不像版本号"决定,不由引擎名决定。

    目录:
    - 有版本层: config_root/engines/{engine}/(版本目录)/{hardware_family}/models/default_model.yaml
    - 无版本层: config_root/engines/{engine}/{hardware_family}/models/default_model.yaml

    若文件不存在,返回 ({}, None) 而不是抛出异常。
    """
    path = build_models_dir(
        config_root, engine, hardware_family, version, has_version_dir
    ) / "default_model.yaml"
    if not path.is_file():
        logger.warning(
            "ConfigLoader: platform default not found: %s; using empty defaults", path
        )
        return {}, None
    data = load_yaml(path)
    logger.info("ConfigLoader: loaded platform config from %s", path)
    return data, path


def load_model_config(
    config_root: Path,
    hardware_family: str,
    engine: str,
    version: str,
    model_name: str,
    has_version_dir: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[Path], str]:
    """扫描 models/ 目录,按 match 规则匹配模型 yaml。

    Args:
        config_root: 配置根目录,内含 engines/ 子树。
        hardware_family: 硬件族标识(如 "h200");无版本层引擎下直接作 engines/{engine}/ 的下一层目录。
        engine: 引擎名(如 "vllm" / "vllm-ascend")。
        version: 引擎版本字符串(来自 ENGINE_VERSION env)。
                 仅有版本层的引擎(has_version_dir=True)用它拼版本目录;
                 无版本层引擎(has_version_dir=False)此参数不参与路径拼接。
        model_name: 待匹配模型名,用于与 yaml 内 model.match[].name_pattern 正则匹配。
        has_version_dir: 由上游 version_resolver 目录自判得出的开关。
                 True → 路径含版本层;False → 完全跳过版本目录拼接。
                 注意:有/无版本层由"目录名像不像版本号"决定,不由引擎名决定。

    目录:
    - 有版本层: config_root/engines/{engine}/(版本目录)/{hw}/models/{ModelDir}/*.yaml
    - 无版本层: config_root/engines/{engine}/{hw}/models/{ModelDir}/*.yaml

    新格式文件命名: {ModelName}-{dtype}.yaml(如 Qwen3.5-0.8B-bf16.yaml)。
    默认文件名: default_model.yaml。
    匹配依据 yaml 内 model.match[].name_pattern,不依赖目录名或文件名大小写。

    匹配后收集所有候选;若多于一个,报 ValueError(ambiguous)。

    Returns:
        (data, yaml_path, matched_pattern) — 命中时返回模型数据与路径。
        无命中时返回 (None, None, "") 供上层走 default_model 默认路径。
    """
    models_dir = build_models_dir(
        config_root, engine, hardware_family, version, has_version_dir
    )
    if not models_dir.is_dir():
        raise FileNotFoundError(
            f"engine='{engine}' hardware_family='{hardware_family}' 下无配置资产"
            f"(models 目录不存在: {models_dir})。"
            "请检查 --hardware-info 里的 hardware_family 是否正确,"
            "或确认该 engine + hardware 的 recipe 已下发。"
        )

    # 两步匹配:① 精确 variant_name 优先;② name_pattern 模糊匹配作为回退。
    # variant_name = MaaS 下发的【完整变体名】,显式声明、不推断(model_id/engine_config.model/
    # 文件名后缀均被证明不可靠)。缺 variant_name 的文件不入 ① 层,靠 ② 回退
    # (单变体容错 + 向后兼容:存量未铺 variant_name 时行为不变)。
    exact_matches: List[Tuple[Dict[str, Any], Path, str]] = []      # (data, path, variant_name)
    pattern_matches: List[Tuple[Dict[str, Any], Path, str]] = []    # (data, path, hit_pattern)
    yaml_errors: List[Tuple[Path, str]] = []
    model_name_norm = model_name.strip().lower()
    for model_dir in sorted(models_dir.iterdir()):
        if not model_dir.is_dir() or model_dir.name == "default_model.yaml":
            continue
        yaml_files = sorted(model_dir.glob("*.yaml"))
        yaml_files.sort(key=lambda p: (p.name != "default_model.yaml", p.name))
        for yaml_file in yaml_files:
            try:
                data = load_yaml(yaml_file)
            except Exception as exc:
                yaml_errors.append((yaml_file, str(exc)))
                logger.warning(
                    "ConfigLoader: YAML parse failed %s: %s", yaml_file, exc,
                )
                continue
            if not isinstance(data, dict):
                continue
            model_block = data.get("model", {})
            if not isinstance(model_block, dict):
                continue
            # ① 精确层:model.variant_name == model_name(小写归一,精确相等,不走正则)
            variant_name = model_block.get("variant_name")
            if (
                isinstance(variant_name, str)
                and variant_name.strip()
                and variant_name.strip().lower() == model_name_norm
            ):
                exact_matches.append((data, yaml_file, variant_name.strip()))
            # ② 回退层:name_pattern 模糊匹配
            match_rules = model_block.get("match", [])
            if not isinstance(match_rules, list):
                continue
            for rule in match_rules:
                if not isinstance(rule, dict):
                    continue
                pattern = rule.get("name_pattern", "")
                if not pattern:
                    continue
                # 非法正则不应中断全量扫描:记录错误后跳过该规则。
                try:
                    hit = re.search(pattern, model_name)
                except re.error as exc:
                    yaml_errors.append((yaml_file, f"invalid name_pattern {pattern!r}: {exc}"))
                    logger.warning(
                        "ConfigLoader: invalid name_pattern %r in %s: %s (skip this rule)",
                        pattern, yaml_file, exc,
                    )
                    continue
                if hit:
                    pattern_matches.append((data, yaml_file, pattern))
                    break  # 同一文件只记一次

    # ── ① 精确 variant_name 优先(确定性,无正则子串坑)──
    if len(exact_matches) == 1:
        data, yaml_file, vn = exact_matches[0]
        logger.info("ConfigLoader: model '%s' 精确命中 variant_name in %s", model_name, yaml_file)
        return data, yaml_file, f"variant_name={vn}"
    if len(exact_matches) > 1:
        paths = ", ".join(str(p) for _, p, _ in exact_matches)
        raise ValueError(
            f"variant_name 冲突:多个文件声明 variant_name='{model_name}': {paths}。"
            "请确保同目录 variant_name 唯一。"
        )

    # ── ② name_pattern 模糊匹配回退 ──
    if len(pattern_matches) == 1:
        data, yaml_file, pattern = pattern_matches[0]
        logger.info("ConfigLoader: model '%s' matched in %s", model_name, yaml_file)
        return data, yaml_file, pattern  # matched_pattern 透出给 resolution_notes
    elif len(pattern_matches) == 0:
        msg = f"No model yaml matched model_name='{model_name}' under {models_dir}"
        if yaml_errors:
            details = "; ".join(f"{p}: {e}" for p, e in yaml_errors)
            msg += (
                f"\n  YAML parse errors encountered "
                f"(may contain the intended config): {details}"
            )
            raise FileNotFoundError(msg)
        logger.warning(msg)
        return None, None, ""
    else:
        paths = ", ".join(str(p) for _, p, _ in pattern_matches)
        raise ValueError(
            f"Ambiguous: model_name='{model_name}' 命中多个变体(name_pattern 家族级)。"
            "多变体请传【带 dtype 后缀的完整变体名】(= 各文件 model.variant_name),"
            f"不要只传家族名。候选: {paths}"
        )
