"""并行度协调公共核,单机与多机路径共用同一套公式。

本仓"单一判定点"护栏落点:
- ``dp_local_from_device_count``:**唯一一处**实现「DP-local = device_count // TP」及其校验
  (TP 静态绝不算)。单机 ``device_count_transform`` 与多机 A 类
  ``coordinate_parallelism`` 都调用这里。
- ``dp_start_rank``:**唯一一处** ``data_parallel_start_rank = index × dp_local`` 公式;
  多机模板展开与运行时协调共用这一入口。
"""

from __future__ import annotations


def dp_local_from_device_count(device_count: int, tp: int) -> int:
    """按 device_count 与静态 TP 算每实例 DP-local = ``device_count // TP``(带校验)。

    Args:
        device_count: 下发卡数(单机=整机;多机 A 类=本 Pod)。
        tp: 模板静态 ``tensor_parallel_size``(**只读,绝不在此计算**)。

    Returns:
        ``device_count // tp``。

    Raises:
        ValueError: ``tp <= 0``(recipe 的 TP 非正,除数不合法)/ ``device_count <= 0`` /
            ``< tp`` / 非 ``tp`` 整数倍(**不向下取整**)。
    """
    # tp 是除数,须为正整数。recipe 若给出非正 tensor_parallel_size(畸形配置),
    # 在此显式报错,避免 device_count % tp 抛出难以定位的 ZeroDivisionError。
    if tp <= 0:
        raise ValueError(
            f"tensor_parallel_size={tp} 非法(recipe 的 TP 须为正整数);无法据此协调 device-count 的 DP"
        )
    if device_count <= 0:
        raise ValueError(f"device-count={device_count} 非法(须为正整数)")
    if device_count < tp:
        raise ValueError(
            f"device-count={device_count} < tensor_parallel_size={tp}:装不下一个 TP 组(cnt 须 ≥ TP)"
        )
    if device_count % tp != 0:
        raise ValueError(
            f"device-count={device_count} 不是 tensor_parallel_size={tp} 的整数倍(不向下取整)"
        )
    return device_count // tp


def dp_start_rank(index: int, dp_local: int) -> int:
    """本 Pod 的 ``data_parallel_start_rank = index × dp_local``(单一公式)。

    Args:
        index: 本 Pod 在集群中的下标(0 = head)。
        dp_local: 每 Pod 的 DP 副本数。

    Returns:
        ``index * dp_local``。
    """
    return index * dp_local


def _is_power_of_two(n: int) -> bool:
    """判断正整数是否为 2 的幂(收缩守卫用)。

    Args:
        n: 待判定的整数。

    Returns:
        ``n`` 为正且是 2 的幂(1/2/4/8...)时 True,否则 False。
    """
    return n > 0 and (n & (n - 1)) == 0


def resolve_replica_tp_dp(device_count: int, tp: int) -> tuple[int, int]:
    """单机(replica-per-Pod)按 device_count 定"生效 TP + DP"(含收缩)。

    统一处理"够卡调 DP"与"少卡收缩 TP"两支:
    - ``device_count >= tp``:TP 静态不动,``DP = device_count // tp``(须整除)。
    - ``device_count <  tp``:一份模型都占不满 TP 张卡 → **收缩** TP 到 device_count、DP=1
      (受限例外)。此支要求 device_count 是 2 的幂(挡异形 TP;head 整除与显存闸
      由调用方在拿到 model_path/最终 gpu_util 后另校)。

    Args:
        device_count: 下发卡数(必传,>0)。
        tp: 模板静态 ``tensor_parallel_size``(**只读,绝不在此放大/臆造**)。

    Returns:
        ``(tp_eff, dp)``:生效 TP 与 DP。``tp_eff != tp`` 即发生了收缩。

    Raises:
        ValueError: ``device_count <= 0``;``>=tp`` 但非 tp 整数倍(不向下取整);
            ``<tp`` 但不是 2 的幂。
    """
    if device_count <= 0:
        raise ValueError(f"device-count={device_count} 非法(须为正整数)")
    if device_count >= tp:
        # 够卡:TP 静态,DP=cnt//tp(复用公共核整除校验)
        return tp, dp_local_from_device_count(device_count, tp)
    # 少卡:收缩 TP 到 device_count。2 的幂守卫(纯函数,可在此)
    if not _is_power_of_two(device_count):
        raise ValueError(
            f"device-count={device_count} < tensor_parallel_size={tp} 触发 TP 收缩,"
            f"但 {device_count} 不是 2 的幂(收缩守卫);请调整卡数或用 direct_vllm_serve。"
        )
    return device_count, 1


def check_capacity(
    tp_eff: int,
    gpu_mem_bytes: int,
    weight_bytes: int,
    multiplier: float = 1.5,
) -> None:
    """显存可行性硬闸:一份模型的 TP 张卡装不装得下它自己那份。

    判据 ``tp_eff × gpu_mem ≥ multiplier × weight_bytes``。用 ``tp_eff``(而非总卡数)是因为
    一份模型只摊在它的 TP 张卡上,每卡持 ``weight/TP`` 分片,能否装下取决于这 TP 张卡。
    **不乘 gpu_util**(当前配置链路不下发 util,用裸 gpu_mem;1.5× 已含裕量)。
    ``multiplier`` 默认 1.5 为经验下限(未计入 KV cache 增长)。

    Args:
        tp_eff: 生效 TP(收缩后=device_count;否则=模板 TP)。
        gpu_mem_bytes: 单卡显存(字节)。
        weight_bytes: 模型权重字节数。
        multiplier: 经验系数,默认 1.5。

    Raises:
        ValueError: 可用显存 ``tp_eff × gpu_mem < multiplier × weight_bytes``(装不下,报错指向逃生)。
    """
    avail = tp_eff * gpu_mem_bytes
    need = multiplier * weight_bytes
    if avail < need:
        raise ValueError(
            f"容量不足:TP_有效={tp_eff} × gpu_mem={gpu_mem_bytes}B = {avail:.0f}B "
            f"< {multiplier}×权重{weight_bytes}B = {need:.0f}B;这 {tp_eff} 张卡装不下一份模型。"
            "请增卡 / 换硬件;或 direct_vllm_serve。"
        )
