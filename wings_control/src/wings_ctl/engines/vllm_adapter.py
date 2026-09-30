"""VllmAdapter — engine_config traces → argv list。

输入: Dict[str, TracedValue] (engine_config_traces), engine name
输出: List[str] (argv)

规则:
- 命令前缀通过 engine → prefix 查表确定
- 顶层 key 下划线转连字符 (max_model_len → --max-model-len);点号后的嵌套路径原样保留
- 顶层 bool=true → 无值 flag (--trust-remote-code);bool=false / None → 不输出
- 点号嵌套配置始终渲为 --flag=value(包括 bool 的 True / False)
- dict/list 默认渲染为紧凑 JSON；封闭的 nargs 参数例外
- 其余标量值原样 str()
"""

from __future__ import annotations

from typing import Any, Dict, List, NamedTuple, Optional

from wings_ctl.core.models import SystemSetup, TracedValue
from wings_ctl.core.system_setup import extract_source_commands
from wings_ctl.engines.param_names import key_to_flag
from wings_ctl.rendering.serializer import serialize_nested_value


# vLLM 中少数 nargs 参数需要把 YAML 列表展开为多个 argv token。
# 保持封闭白名单，避免改变普通 dict/list 参数的既有 JSON 渲染语义。
_MULTI_TOKEN_LIST_PARAMS = frozenset({"cudagraph_capture_sizes"})


class EngineCmd(NamedTuple):
    """引擎启动命令规格:前缀 + model 传法。

    Attributes:
        prefix: 命令前缀 token(启动入口)。
        model_arg: model 的传法——``None`` = 位置参数(紧跟前缀,如 ``vllm serve <model>``);
            非空 = 具名参数,渲成 ``--{model_arg} <model>``(如 sglang ``--model-path <model>``)。
        render_system_setup_source_commands: 是否将 ``system_setup.commands`` 中的
            ``source <absolute-path>`` 指令渲染到 engine argv 前。
    """
    prefix: List[str]
    model_arg: Optional[str]
    render_system_setup_source_commands: bool = False


# 引擎 → 命令规格。新增引擎时优先在表中补充命令前缀和 model 参数形态。
_ENGINE_CMD: Dict[str, EngineCmd] = {
    "vllm": EngineCmd(["vllm", "serve"], None),                # 位置:vllm serve <model>
    "vllm-ascend": EngineCmd(["vllm", "serve"], None, True),    # 同 vllm CLI 入口
    "sglang": EngineCmd(["python3", "-m", "sglang.launch_server"], "model-path"),  # 具名:--model-path <model>
}


# model 的 canonical 键 + 别名:"model"=主键;"model_path"=部分 sglang recipe 用的同义键。
# 二者指同一概念(启动 model),渲染时**只出一次**(优先 "model")——见 resolve_model_traced/build_argv。
MODEL_KEYS = ("model", "model_path")


def resolve_model_traced(engine_config_traces: Dict[str, TracedValue]) -> Optional[TracedValue]:
    """取 model 终值:优先 canonical ``model``,回退别名 ``model_path``(sglang recipe);都无 → None。"""
    for key in MODEL_KEYS:
        traced = engine_config_traces.get(key)
        if traced is not None:
            return traced
    return None


def get_engine_cmd(engine: str) -> EngineCmd:
    """查引擎命令规格;未知引擎 → ValueError。"""
    spec = _ENGINE_CMD.get(engine)
    if spec is None:
        raise ValueError(
            f"Unknown engine '{engine}'. Known engines: {list(_ENGINE_CMD)}"
        )
    return spec


def get_engine_command_prefix(engine: str) -> List[str]:
    """获取引擎命令前缀(启动入口 token)。

    Raises:
        ValueError: engine 未知。
    """
    return list(get_engine_cmd(engine).prefix)


def build_command_head(engine: str, model_value: str) -> List[str]:
    """拼"前缀 + model"命令头,按命令规格查表分派 model 形态。

    Args:
        engine: 引擎名。
        model_value: 最终 model 值(canonical 键 "model" 的终值)。

    Returns:
        - model_arg 为 None(vllm)→ ``[*prefix, model_value]``(位置);
        - model_arg 非空(sglang)→ ``[*prefix, --{model_arg}, model_value]``(具名)。

    Raises:
        ValueError: engine 未知。
    """
    spec = get_engine_cmd(engine)
    if spec.model_arg is None:
        return list(spec.prefix) + [model_value]
    return list(spec.prefix) + [f"--{spec.model_arg}", model_value]


def build_system_setup_source_commands(engine: str, system_setup: Optional[SystemSetup]) -> List[str]:
    """提取引擎允许执行的 ``system_setup`` source 环境初始化命令。

    ``system_setup.commands`` 通常只保留为审阅注释。命令规格明确启用该能力的引擎，
    才能执行其中严格形如 ``source <absolute-path>`` 的条目。路径经 ``shlex.quote``
    重渲染，避免 YAML 中的 shell 元字符改变脚本结构；其他 commands 仍不执行。

    Args:
        engine: 规范化后的引擎名。
        system_setup: 已解析的系统设置；无设置时返回空列表。

    Returns:
        紧邻 engine argv 前执行的 source 命令列表。

    Raises:
        ValueError: source 指令不是单个绝对路径，无法安全渲染。
    """
    if system_setup is None or not get_engine_cmd(engine).render_system_setup_source_commands:
        return []

    return extract_source_commands(
        system_setup.commands,
        context=f"system_setup for engine '{engine}'",
    )


def render_param_tokens(key: str, value: Any) -> Optional[List[str]]:
    """将单个 engine_config 参数渲染为 argv token 列表。

    规则(与 build_argv 一致,不要在别处重复实现):
    - None → None (跳过)
    - 顶层 bool=True → ["--flag"];顶层 bool=False → None (跳过)
    - 点号嵌套配置 → ["--flag=value"](包括 bool;如 False → --kernel-config.xxx=False)
    - ``cudagraph_capture_sizes`` 列表 -> ["--flag", "1", "2", ...]
    - 其他顶层 dict/list -> ["--flag", compact_json]
    - 顶层标量 → ["--flag", str(value)]

    Args:
        key: 参数名(下划线形式的顶层 key,或点号嵌套配置 key,如
            "max_model_len" / "kernel_config.enable_flashinfer_autotune")。
        value: 参数值。

    Returns:
        argv token 列表,或 None 表示该参数应跳过。
    """
    if value is None:
        return None

    flag = key_to_flag(key)
    if "." in key:
        # vLLM 的 --kernel-config.<field>=<value> 是嵌套配置赋值而非开关:
        # False 也必须显式传入,且 value 与 flag 组成同一 argv token。
        if isinstance(value, (dict, list)):
            value = serialize_nested_value(value)
        return [f"{flag}={value}"]

    if isinstance(value, bool):
        return [flag] if value else None

    if key in _MULTI_TOKEN_LIST_PARAMS and isinstance(value, list):
        return [flag, *(str(item) for item in value)]

    if isinstance(value, (dict, list)):
        return [flag, serialize_nested_value(value)]

    return [flag, str(value)]


def build_argv(
    engine_config_traces: Dict[str, TracedValue],
    engine: str = "vllm",
) -> List[str]:
    """将 engine_config_traces 转换为引擎启动 argv 列表(命令头按命令规格查表)。

    `model` key 由命令规格分派:vllm 作位置参数紧跟前缀;sglang 渲成 ``--model-path <model>``。
    其余参数以 --key value 形式追加。嵌套 dict/list 值序列化为紧凑 JSON 字符串(不做 shell quoting,
    由渲染层统一处理)。

    Args:
        engine_config_traces: 参数名 → TracedValue 映射。
        engine: 引擎名称,用于查命令规格(默认 "vllm")。

    Returns:
        argv 列表。vllm 例:["vllm", "serve", "Qwen/...", "--max-model-len", "262144", ...];
        sglang 例:["python3", "-m", "sglang.launch_server", "--model-path", "/data/...", ...]。

    Raises:
        ValueError: engine 未知或缺少 model key。
    """
    # 提取 model(canonical "model" 或别名 "model_path";vllm 渲位置参数,sglang 渲 --model-path,查表分派)
    model_traced = resolve_model_traced(engine_config_traces)
    if model_traced is None:
        raise ValueError(f"engine_config must contain 'model' key for engine '{engine}'")
    model_value = str(model_traced.final_value)

    argv: List[str] = build_command_head(engine, model_value)

    for key, traced in engine_config_traces.items():
        if key in MODEL_KEYS:  # model / model_path 已由命令头渲染,跳过避免重复 --model-path
            continue
        tokens = render_param_tokens(key, traced.final_value)
        if tokens:
            argv.extend(tokens)

    return argv
