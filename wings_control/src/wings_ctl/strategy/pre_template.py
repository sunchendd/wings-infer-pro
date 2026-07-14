"""大策略层:在读模板前先判断 topology。"""

from __future__ import annotations

from wings_ctl.core.topology import Topology


def pre_template_strategy(
    engine: str,
    *,
    distributed: bool | None = None,
    pd_role: str | None = None,
    master_ip: str | None = None,
) -> tuple[str, Topology]:
    """根据 CLI/env 输入推导部署拓扑 ``(engine, topology)``。

    该函数在模板查找前调用,只读 CLI/env,不读 model.yaml。
    推导出的 topology 用于选择 ``scenarios.{topology}``。

    判定优先级(``--distributed`` 为权威开关):
        1. ``pd_role`` 置位      → PD 分离(当前不支持)
        2. ``distributed`` 为真  → 多机 ``MULTI_NODE``(需 ``master_ip``)
        3. 其余                  → 单机 ``STANDALONE``

    Args:
        engine: 引擎名(``vllm`` / ``vllm-ascend`` …)。当前直接透传。
        distributed: ``--distributed`` 总开关;True 表示分布式部署。
        pd_role: ``PD_ROLE`` 环境变量(``P``/``D``);非空表示 PD 分离场景。
        master_ip: ``MASTER_IP`` 环境变量;分布式场景必填。

    Returns:
        ``(engine, topology)``:engine 透传;topology 为推导出的 :class:`Topology` 枚举。

    Raises:
        ValueError: ``distributed`` 为真但缺 ``master_ip``。
        NotImplementedError: ``pd_role`` 置位(当前版本不支持 PD 分离)。
    """
    # 1) PD 分离:当前不支持,直接报错。
    if pd_role:
        raise NotImplementedError(
            f"PD 分离场景(PD_ROLE={pd_role})待后续实现。"
        )

    # 2) 分布式:以 --distributed 为准;MASTER_IP 缺失则直接失败。
    if distributed:
        if not master_ip:
            raise ValueError(
                "分布式场景(--distributed)必填 MASTER_IP(env),当前缺失。"
            )
        return engine, Topology.MULTI_NODE

    # 3) 默认单机。
    return engine, Topology.STANDALONE
