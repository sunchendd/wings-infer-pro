"""memory_estimator 单元测试(单常数最坏值模型)。

公式: available = container − (base + worker_overhead × workers) − container × margin_ratio
      默认: base=3, worker_overhead=7, margin_ratio=0.10
"""

import pytest

from wings_accel.memory_estimator import estimate_offload_memory, MemoryEstimate


class TestEstimateOffloadMemory:
    def test_normal_enable_high_memory_container(self):
        """256G 容器, 8 worker → engine_self=59, margin=25.6 → available=171,enabled"""
        est = estimate_offload_memory(
            container_memory_gb=256, worker_count=8,
        )
        assert est.enabled is True
        assert est.worker_count == 8
        assert est.engine_self_gb == pytest.approx(3 + 7 * 8)  # 59
        assert est.margin_gb == pytest.approx(25.6)
        assert est.available_gb == int(256 - 59 - 25.6)  # 171

    def test_disable_below_threshold(self):
        """50G 容器, 4 worker → available=14 < 20G(默认阈值),disabled"""
        est = estimate_offload_memory(
            container_memory_gb=50, worker_count=4,
        )
        assert est.enabled is False
        assert est.available_gb == 14  # int(50 - 31 - 5)
        assert est.min_threshold_gb == 20
        assert "14" in est.disable_reason
        assert "threshold 20GB" in est.disable_reason

    def test_worker_count_scales_overhead(self):
        """worker 数翻倍 → engine_self 随之翻倍(每 worker 7G)"""
        est_w8 = estimate_offload_memory(
            container_memory_gb=512, worker_count=8,
        )
        est_w16 = estimate_offload_memory(
            container_memory_gb=512, worker_count=16,
        )
        assert est_w8.worker_count == 8
        assert est_w16.worker_count == 16
        assert est_w16.engine_self_gb == pytest.approx(3 + 7 * 16)  # 115
        # available 相差 56G(8 个 worker × 7G);margin 相同(container 不变)
        assert est_w8.available_gb - est_w16.available_gb == 56

    def test_custom_base_overhead(self):
        """覆盖固定基座默认值(base 3 → 8)"""
        est = estimate_offload_memory(
            container_memory_gb=256, worker_count=8, base_overhead_gb=8,
        )
        # engine_self 多 5G → available 少 5G
        assert est.engine_self_gb == pytest.approx(8 + 7 * 8)  # 64
        assert est.available_gb == int(256 - 64 - 25.6)  # 166
        assert est.base_overhead_gb == 8

    def test_custom_worker_overhead(self):
        """覆盖单 worker 最坏值常数(7 → 8)"""
        est = estimate_offload_memory(
            container_memory_gb=256, worker_count=8, worker_overhead_gb=8,
        )
        # engine_self = 3 + 8*8 = 67
        assert est.engine_self_gb == pytest.approx(67)
        assert est.available_gb == int(256 - 67 - 25.6)  # 163

    def test_custom_margin_ratio(self):
        """覆盖容器安全余量比例(0.10 → 0.20)"""
        est = estimate_offload_memory(
            container_memory_gb=256, worker_count=8, margin_ratio=0.20,
        )
        # margin = 256 × 0.20 = 51.2 (默认 25.6,多扣 25.6)
        assert est.margin_gb == pytest.approx(51.2)
        assert est.margin_ratio == 0.20
        assert est.available_gb == int(256 - 59 - 51.2)  # 145

    def test_custom_min_threshold(self):
        """覆盖启用阈值"""
        # 默认阈值 20 → enabled(available=199 远超阈值),改为 250 → disabled
        est_default = estimate_offload_memory(
            container_memory_gb=256, worker_count=4,
        )
        assert est_default.available_gb == int(256 - (3 + 7 * 4) - 25.6)  # 199
        assert est_default.enabled is True

        est_high_threshold = estimate_offload_memory(
            container_memory_gb=256, worker_count=4,
            min_threshold_gb=250,
        )
        assert est_high_threshold.enabled is False
        assert est_high_threshold.min_threshold_gb == 250

    def test_available_clamped_to_zero(self):
        """极端场景:容器内存极小,available 不会负数"""
        est = estimate_offload_memory(
            container_memory_gb=10, worker_count=8,
        )
        assert est.enabled is False
        assert est.available_gb == 0  # clamped
        # 10 - 59 - 1.0 = -50 → max(0, -50) = 0

    def test_disable_reason_contains_breakdown(self):
        """disable_reason 含完整调试信息(container/engine_self/margin/workers)"""
        # 60G/8 worker → available=clamp(60-59-6)=0 < 20(默认阈值) → disabled
        est = estimate_offload_memory(
            container_memory_gb=60, worker_count=8,
        )
        assert est.enabled is False
        reason = est.disable_reason
        assert "container=60" in reason
        assert "engine_self=" in reason
        assert "margin=" in reason
        assert "workers=8" in reason

    def test_dataclass_fields_complete(self):
        """MemoryEstimate 所有字段都被填充,无 None"""
        est = estimate_offload_memory(
            container_memory_gb=256, worker_count=8,
        )
        for field in ("container_memory_gb", "worker_count",
                      "worker_overhead_gb", "base_overhead_gb", "engine_self_gb",
                      "margin_ratio", "margin_gb",
                      "available_gb", "enabled", "min_threshold_gb"):
            assert getattr(est, field) is not None
        # enabled 时 disable_reason 为空字符串
        assert est.disable_reason == ""
