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
    is_mooncake_master: bool = False,
) -> tuple[str, Topology]:
    """根据 CLI/env 输入推导部署拓扑 ``(engine, topology)``。

    该函数在模板查找前调用,只读 CLI/env,不读 model.yaml。
    推导出的 topology 用于选择 ``scenarios.{topology}``。

    判定优先级:
        1. ``pd_role`` 为 P/D    → 对应 PD topology(``PD_ROLE`` 是 PD 唯一入口;
           ``--distributed`` 只表示该 Instance 是否跨 Pod,不改变 PD 判断)
        2. ``is_mooncake_master`` 为真 → Mooncake master 专属 Pod,豁免标准多机
           的 ``master_ip`` 强校验,仍推导 ``MULTI_NODE``(见下)
        3. ``distributed`` 为真  → 标准多机 ``MULTI_NODE``(需 ``master_ip``)
        4. 其余                  → 标准单机 ``STANDALONE``

    Args:
        engine: 引擎名(``vllm`` / ``vllm-ascend`` …)。当前直接透传。
        distributed: ``--distributed``;标准推理表示是否多机,PD 下表示当前
            logical Instance 是否跨 Pod。
        pd_role: 已规范化的当前 Pod P/D 角色；标准推理为 ``None``。
        master_ip: ``MASTER_IP`` 环境变量;标准分布式场景必填。
        is_mooncake_master: 当前 Pod 是否为 Mooncake master 专属 Pod
            (部署层事实,来自 ``IS_MOONCAKE_MASTER``,由 CLI 读取传入)。

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

    # Mooncake master 专属 Pod:部署层事实优先于标准分布式语义。该 Pod 不属于
    # 推理集群(无 RANK_IP/NODE_IPS/MASTER_IP),豁免标准多机的 MASTER_IP 强校验;
    # 仍推导 MULTI_NODE 以与 engine Pod 同拓扑值驱动 smart-accel scheme 匹配/降级
    # 判定(决策一致性由构造保证——若换 standalone,只在 multi_node scenario 声明
    # distributed_kv_offload 的模型会在 master Pod 上被误判为未适配)。实际交付由
    # script_builder 的 master 交付支线接管,不会执行 vllm serve。
    if is_mooncake_master:
        return engine, Topology.MULTI_NODE

    # 标准分布式:以 --distributed 为准;MASTER_IP 缺失则直接失败。
    if distributed:
        if not master_ip:
            raise ValueError("Distributed mode (--distributed) requires MASTER_IP in the environment")
        return engine, Topology.MULTI_NODE

    # 4) 默认单机。
    return engine, Topology.STANDALONE
