"""大策略层:在读模板前先判断 topology。"""

from __future__ import annotations

from wings_ctl.core.models import PdRole
from wings_ctl.core.topology import Topology


def pre_template_strategy(
    engine: str,
    *,
    distributed: bool | None = None,
    pd_role: PdRole | None = None,
    master_ip: str | None = None,
) -> tuple[str, Topology]:
    """根据 CLI/env 输入推导部署拓扑 ``(engine, topology)``。

    该函数在模板查找前调用,只读 CLI/env,不读 model.yaml。
    推导出的 topology 用于选择 ``scenarios.{topology}``。

    判定优先级:
        1. ``pd_role`` 为 P/D    → 对应 PD topology(``PD_ROLE`` 是 PD 唯一入口;
           ``--distributed`` 只表示该 Instance 是否跨 Pod,不改变 PD 判断)
        2. ``distributed`` 为真  → 标准多机 ``MULTI_NODE``(需 ``master_ip``)
        3. 其余                  → 标准单机 ``STANDALONE``

    Args:
        engine: 引擎名(``vllm`` / ``vllm-ascend`` …)。当前直接透传。
        distributed: ``--distributed``;标准推理表示是否多机,PD 下表示当前
            logical Instance 是否跨 Pod。
        pd_role: 已规范化的当前 Pod P/D 角色；标准推理为 ``None``。
        master_ip: ``MASTER_IP`` 环境变量;标准分布式场景必填。

    Returns:
        ``(engine, topology)``:engine 透传;topology 为推导出的 :class:`Topology` 枚举。

    Raises:
        ValueError: 标准多机缺 ``master_ip``。
    """
    if pd_role is not None:
        topology_by_role = {
            PdRole.PREFILL: Topology.PD_PREFILL,
            PdRole.DECODE: Topology.PD_DECODE,
        }
        return engine, topology_by_role[pd_role]

    # 标准分布式:以 --distributed 为准;MASTER_IP 缺失则直接失败。
    if distributed:
        if not master_ip:
            raise ValueError("分布式场景(--distributed)必填 MASTER_IP(env),当前缺失。")
        return engine, Topology.MULTI_NODE

    # 3) 默认单机。
    return engine, Topology.STANDALONE
