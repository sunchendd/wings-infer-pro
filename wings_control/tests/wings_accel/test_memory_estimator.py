"""memory_estimator 单元测试(单常数最坏值模型)。

公式: available = container − (base + worker_overhead × workers) − container × margin_ratio
      默认: base=3, worker_overhead=7, margin_ratio=0.10
"""

import pytest

from wings_accel.memory_estimator import estimate_offload_memory, MemoryEstimate


class TestEstimateOffloadMemory:
    def test_normal_enable_high_memory_container(self):
        """256G 容器, TP=8, DP=1 → engine_self=59, margin=25.6 → available=171,enabled"""
        est = estimate_offload_memory(
            container_memory_gb=256, tp_size=8, dp_size=1,
        )
        assert est.enabled is True
        assert est.worker_count == 8
        assert est.engine_self_gb == pytest.approx(3 + 7 * 8)  # 59
        assert est.margin_gb == pytest.approx(25.6)
        assert est.available_gb == int(256 - 59 - 25.6)  # 171

    def test_disable_below_threshold(self):
        """128G 容器, TP=8 → available=56.2 < 100G,disabled"""
        est = estimate_offload_memory(
            container_memory_gb=128, tp_size=8, dp_size=1,
        )
        assert est.enabled is False
        assert est.available_gb == 56  # int(128 - 59 - 12.8)
        assert est.min_threshold_gb == 100
        assert "56" in est.disable_reason
        assert "threshold 100GB" in est.disable_reason

    def test_dp_doubles_worker_count(self):
        """DP=2 → worker_count 翻倍,engine_self 翻倍(每 worker 7G)"""
        est_tp_only = estimate_offload_memory(
            container_memory_gb=512, tp_size=8, dp_size=1,
        )
        est_tp_dp = estimate_offload_memory(
            container_memory_gb=512, tp_size=8, dp_size=2,
        )
        assert est_tp_only.worker_count == 8
        assert est_tp_dp.worker_count == 16
        assert est_tp_dp.engine_self_gb == pytest.approx(3 + 7 * 16)  # 115
        # available 相差 56G(8 个 worker × 7G);margin 相同(container 不变)
        assert est_tp_only.available_gb - est_tp_dp.available_gb == 56

    def test_custom_base_overhead(self):
        """覆盖固定基座默认值(base 3 → 8)"""
        est = estimate_offload_memory(
            container_memory_gb=256, tp_size=8, base_overhead_gb=8,
        )
        # engine_self 多 5G → available 少 5G
        assert est.engine_self_gb == pytest.approx(8 + 7 * 8)  # 64
        assert est.available_gb == int(256 - 64 - 25.6)  # 166
        assert est.base_overhead_gb == 8

    def test_custom_worker_overhead(self):
        """覆盖单 worker 最坏值常数(7 → 8)"""
        est = estimate_offload_memory(
            container_memory_gb=256, tp_size=8, worker_overhead_gb=8,
        )
        # engine_self = 3 + 8*8 = 67
        assert est.engine_self_gb == pytest.approx(67)
        assert est.available_gb == int(256 - 67 - 25.6)  # 163

    def test_custom_margin_ratio(self):
        """覆盖容器安全余量比例(0.10 → 0.20)"""
        est = estimate_offload_memory(
            container_memory_gb=256, tp_size=8, margin_ratio=0.20,
        )
        # margin = 256 × 0.20 = 51.2 (默认 25.6,多扣 25.6)
        assert est.margin_gb == pytest.approx(51.2)
        assert est.margin_ratio == 0.20
        assert est.available_gb == int(256 - 59 - 51.2)  # 145

    def test_custom_min_threshold(self):
        """覆盖启用阈值"""
        # 默认阈值 100 → enabled,改为 250 → disabled
        est_default = estimate_offload_memory(
            container_memory_gb=256, tp_size=4, dp_size=1,
        )
        assert est_default.available_gb == int(256 - (3 + 7 * 4) - 25.6)  # 199
        assert est_default.enabled is True

        est_high_threshold = estimate_offload_memory(
            container_memory_gb=256, tp_size=4, dp_size=1,
            min_threshold_gb=250,
        )
        assert est_high_threshold.enabled is False
        assert est_high_threshold.min_threshold_gb == 250

    def test_available_clamped_to_zero(self):
        """极端场景:容器内存极小,available 不会负数"""
        est = estimate_offload_memory(
            container_memory_gb=10, tp_size=8, dp_size=1,
        )
        assert est.enabled is False
        assert est.available_gb == 0  # clamped
        # 10 - 59 - 1.0 = -50 → max(0, -50) = 0

    def test_dp_only_no_tp(self):
        """TP=1, DP=4 → 4 个独立 worker"""
        est = estimate_offload_memory(
            container_memory_gb=256, tp_size=1, dp_size=4,
        )
        assert est.worker_count == 4
        assert est.engine_self_gb == pytest.approx(3 + 7 * 4)  # 31
        assert est.available_gb == int(256 - 31 - 25.6)  # 199

    def test_disable_reason_contains_breakdown(self):
        """disable_reason 含完整调试信息(container/engine_self/margin/workers)"""
        est = estimate_offload_memory(
            container_memory_gb=100, tp_size=8, dp_size=1,
        )
        assert est.enabled is False
        reason = est.disable_reason
        assert "container=100" in reason
        assert "engine_self=" in reason
        assert "margin=" in reason
        assert "workers=8=tp8" in reason

    def test_dataclass_fields_complete(self):
        """MemoryEstimate 所有字段都被填充,无 None"""
        est = estimate_offload_memory(
            container_memory_gb=256, tp_size=8,
        )
        for field in ("container_memory_gb", "worker_count",
                      "worker_overhead_gb", "base_overhead_gb", "engine_self_gb",
                      "margin_ratio", "margin_gb",
                      "available_gb", "enabled", "min_threshold_gb"):
            assert getattr(est, field) is not None
        # enabled 时 disable_reason 为空字符串
        assert est.disable_reason == ""
