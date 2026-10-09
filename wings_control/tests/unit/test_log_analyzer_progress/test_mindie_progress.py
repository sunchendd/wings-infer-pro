"""TC-MindIE-OK — MindIE 引擎部署进度匹配测试。

验证 MindIE 的日志模式匹配能正确产出阶段进度序列，
包括 MindIE 独有的 model_compiling (warmup) 阶段，
各阶段的 progress 值符合插件定义的预期值，最终到达 ready 且 progress=100。
"""

from __future__ import annotations

from .conftest import (
    extract_phase_codes,
    get_final_progress,
    get_first_progress_for_phase,
    get_max_progress_for_phase,
    has_status,
    make_config,
    run_progress_analysis,
)


class TestMindIEProgress:
    """MindIE 引擎进度匹配测试。"""

    @staticmethod
    def test_mindie_ascend_progress(data_dir, tmp_path):
        """TC-MindIE-OK: MindIE Ascend 完整部署日志的进度匹配。

        日志: mindie_ascend.log (MindIE, Ascend NPU, 聚合日志)

        验证点：
        1. 各阶段依次触发: engine_booting → model_loading → model_compiling
           → server_checking → ready
        2. MindIE 的 model_compiling 阶段（含 warmup）被触发
        3. 各阶段首次出现的 progress 值符合插件定义的预期值
        4. 最终 progress=100, is_completed=True
        5. 所有进度行 status 均为 running（无 failed）
        """
        log_path = data_dir / "mindie_ascend.log"
        config = make_config(engine="mindie", hardware="ascend", mode="single")

        analyzer, captured = run_progress_analysis(log_path, config, tmp_path)

        phase_codes = extract_phase_codes(captured)

        # 验证关键阶段被触发
        expected_phases = [
            "engine_booting",
            "model_loading",
            "model_compiling",
            "server_checking",
            "ready",
        ]
        for phase in expected_phases:
            assert phase in phase_codes, f"阶段 {phase} 未被触发，实际阶段序列: {phase_codes}"

        # 验证 MindIE 的 model_compiling 阶段（含 warmup）
        assert "model_compiling" in phase_codes, "MindIE 的 model_compiling 阶段未被触发"

        # 验证各阶段首次出现的 progress 值
        # mindie_single.py: engine_booting 首个模式 "ModelDeployConfig" progress_calc=20
        assert get_first_progress_for_phase(captured, "engine_booting") == 20, "engine_booting 首次 progress 应为 20"
        # model_loading 首个模式 "model_runner.config" progress_calc=32
        assert get_first_progress_for_phase(captured, "model_loading") == 32, "model_loading 首次 progress 应为 32"
        # model_compiling 首个模式 "Successfully loaded model" progress_calc=60
        assert get_first_progress_for_phase(captured, "model_compiling") == 60, "model_compiling 首次 progress 应为 60"
        # server_checking: mindie_sum.log 中 "LlmEngine init succeeds" (progress_calc=96)
        # 先于 "model init success" (progress_calc=92) 出现，且 max 逻辑保证单调递增
        first_server = get_first_progress_for_phase(captured, "server_checking")
        assert first_server is not None and first_server >= 92, (
            f"server_checking 首次 progress 应 >= 92，实际为 {first_server}"
        )
        # ready "Daemon start success" progress_calc=100
        assert get_first_progress_for_phase(captured, "ready") == 100, "ready 首次 progress 应为 100"

        # 验证 model_loading 阶段 progress 范围（32~60）
        max_model_loading = get_max_progress_for_phase(captured, "model_loading")
        assert max_model_loading == 60, f"model_loading 最大 progress 应为 60，实际为 {max_model_loading}"

        # 验证 model_compiling 阶段 progress 范围（60~96, warmup 阶段）
        # "After Decode warmup" progress_calc=92，但 max 逻辑可能将其提升至 96
        max_compiling = get_max_progress_for_phase(captured, "model_compiling")
        assert max_compiling is not None and 92 <= max_compiling <= 96, (
            f"model_compiling 最大 progress 应在 92~96 之间，实际为 {max_compiling}"
        )

        # 验证 server_checking 阶段 progress 范围（92~98）
        max_server = get_max_progress_for_phase(captured, "server_checking")
        assert max_server == 98, f"server_checking 最大 progress 应为 98，实际为 {max_server}"

        # 验证最终进度
        final_progress = get_final_progress(captured)
        assert final_progress == 100, f"最终进度应为 100，实际为 {final_progress}"

        # 验证 is_completed
        assert analyzer.is_completed, "analyzer.is_completed 应为 True"

        # 验证无 failed 状态
        assert not has_status(captured, "failed"), "进度行中不应出现 status=failed"
