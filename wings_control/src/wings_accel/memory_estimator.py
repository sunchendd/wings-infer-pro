"""
内存估算器 — 智能分配 KV 卸载容量(单常数最坏值模型,不查表)。

设计思路:完全不用查表,用实测最坏值兜底。
- 单 worker 实测最大占用:MiniMax-M2.5 TP16 full graph 均摊 ≈ 6.2G/worker
  (含 api/engine/coordinator 均摊)。取 7G/worker 留一档头,可罩住全部配置
  (含最重的 MiniMax TP16 graph、DeepSeek graph)。
- 一个常数覆盖所有情况,比查表干净;RSS/PSS 取舍不再纠结。

重要关键点:
- 估算只依赖 container_memory_gb、TP、DP 和少量经验常数,不读取模型/YAML 表。
- available_gb 向下取整且最小展示为 0;enabled 由 min_threshold_gb 判断。
- disable_reason 保留完整公式变量,供 yaml_loader 日志/audit 定位。
- 这是 CPU offload 容量估算,不处理 disk/QAT 资源。

公式(单常数,保守):
    worker_count    = tp_size × dp_size                       (vLLM V1 进程模型)
    engine_self_gb  = base_overhead_gb + worker_overhead_gb × worker_count
                      ≈ 3G + 7G × (TP × DP)
    margin_gb       = container_memory_gb × margin_ratio       (默认 10%)
    available_gb    = container_memory_gb − engine_self_gb − margin_gb

    swap_space      = 0   (启动设 swap_space=0,无 beam search 前提;见 offload.py)

    若 available_gb < min_threshold_gb  → enabled=False (关闭卸载)

设计要点:
- worker_overhead_gb(7)/ base_overhead_gb(3)/ margin_ratio(0.10) 都是经验常数,覆盖全部实测配置;
  margin 吸收 OS 预留与 RSS/PSS 波动,取代旧 os_reserved 固定值。
- 估算结果以 MemoryEstimate dataclass 返回,携带完整诊断字段。
- 调用方(yaml_loader)根据 enabled 决定是否真正开 KV offload,并把 disable_reason 写入 audit。
"""

from dataclasses import dataclass


@dataclass
class MemoryEstimate:
    """内存估算结果(诊断信息全部扁平化,便于 audit)。"""

    container_memory_gb: int       # 输入:MaaS 传的容器总内存
    worker_count: int              # 计算中间量:tp × dp
    worker_overhead_gb: float      # 输入:单 worker 最坏值常数(默认 7G)
    base_overhead_gb: float        # 输入:固定 api/engine/coordinator 基座(默认 3G)
    engine_self_gb: float          # 计算中间量:引擎自身占用 = base + per_worker × workers
    margin_ratio: float            # 输入:容器安全余量比例(默认 0.10)
    margin_gb: float               # 计算中间量:安全余量 = container × margin_ratio
    available_gb: int              # 计算结果:可用卸载内存(向下载断)
    enabled: bool                  # available >= min_threshold?
    min_threshold_gb: int          # 输入:启用阈值
    disable_reason: str = ""       # enabled=False 时填


def estimate_offload_memory(
    container_memory_gb: int,
    tp_size: int,
    dp_size: int = 1,
    *,
    worker_overhead_gb: float = 7.0,
    base_overhead_gb: float = 3.0,
    margin_ratio: float = 0.10,
    min_threshold_gb: int = 20,
) -> MemoryEstimate:
    """估算 KV 卸载可用 CPU 内存(单常数最坏值模型)。

    Args:
        container_memory_gb: 引擎容器总内存(GB),由 MaaS 传递
        tp_size: 张量并行度,从 scenarios.*.engine_config.tensor_parallel_size 读
        dp_size: 数据并行度,从 scenarios.*.engine_config.data_parallel_size 读(默认 1)
        worker_overhead_gb: 每个 worker 进程 CPU 内存占用(GB),实测最坏值常数,默认 7
            (覆盖 MiniMax TP16 graph ≈ 6.2G/worker + 头);vLLM V1 每个 worker 含
            CUDA context / NCCL buffer / KV transfer pipe
        base_overhead_gb: 不随 worker 数变化的固定基座(GB),含 api server / engine core /
            coordinator,默认 3
        margin_ratio: 容器安全余量比例(0~1),默认 0.10;margin = container × margin_ratio,
            吸收 OS 预留与 RSS/PSS 波动,取代旧 os_reserved 固定值
        min_threshold_gb: 启用阈值(GB),available 低于此值则关闭卸载,默认 20

    Returns:
        MemoryEstimate: 含 available_gb / enabled / disable_reason
    """
    worker_count = tp_size * dp_size
    engine_self = base_overhead_gb + worker_overhead_gb * worker_count
    margin = container_memory_gb * margin_ratio
    available = container_memory_gb - engine_self - margin

    if available < min_threshold_gb:
        return MemoryEstimate(
            container_memory_gb=container_memory_gb,
            worker_count=worker_count,
            worker_overhead_gb=worker_overhead_gb,
            base_overhead_gb=base_overhead_gb,
            engine_self_gb=engine_self,
            margin_ratio=margin_ratio,
            margin_gb=margin,
            available_gb=max(0, int(available)),
            enabled=False,
            min_threshold_gb=min_threshold_gb,
            disable_reason=(
                f"available {available:.1f}GB < threshold {min_threshold_gb}GB "
                f"(container={container_memory_gb}, engine_self={engine_self:.1f}="
                f"{base_overhead_gb:g}+{worker_overhead_gb:g}×{worker_count}, "
                f"margin={margin:.1f}={container_memory_gb}×{margin_ratio:g}, "
                f"workers={worker_count}=tp{tp_size}×dp{dp_size})"
            ),
        )
    return MemoryEstimate(
        container_memory_gb=container_memory_gb,
        worker_count=worker_count,
        worker_overhead_gb=worker_overhead_gb,
        base_overhead_gb=base_overhead_gb,
        engine_self_gb=engine_self,
        margin_ratio=margin_ratio,
        margin_gb=margin,
        available_gb=int(available),
        enabled=True,
        min_threshold_gb=min_threshold_gb,
    )
