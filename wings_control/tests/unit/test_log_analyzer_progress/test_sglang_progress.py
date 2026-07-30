"""TC-SGLang-OK — SGLang 引擎部署进度匹配测试。

验证 SGLang 的日志模式匹配能正确产出阶段进度序列，
包括 SGLang 独有的 kv_cache_allocating 阶段，
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


class TestSGLangProgress:
    """SGLang 引擎进度匹配测试。"""

    def test_sglang_cuda_tp1_progress(self, data_dir, tmp_path):
        """TC-SGLang-OK: SGLang CUDA TP1 完整部署日志的进度匹配。

        日志: sglang_cuda_tp1.log (SGLang, Qwen3-32B, CUDA, TP1)

        验证点：
        1. 各阶段依次触发: engine_booting → model_loading → kv_cache_allocating
           → cuda_graph_capturing → server_checking → ready
        2. SGLang 独有的 kv_cache_allocating 阶段被触发
        3. 各阶段首次出现的 progress 值符合插件定义的预期值
        4. 最终 progress=100, is_completed=True
        5. 所有进度行 status 均为 running（无 failed）
        """
        log_path = data_dir / "sglang_cuda_tp1.log"
        config = make_config(engine="sglang", hardware="nvidia", mode="single")

        analyzer, captured = run_progress_analysis(log_path, config, tmp_path)

        phase_codes = extract_phase_codes(captured)

        # 验证关键阶段被触发
        expected_phases = [
            "engine_booting",
            "model_loading",
            "kv_cache_allocating",
            "cuda_graph_capturing",
            "server_checking",
            "ready",
        ]
        for phase in expected_phases:
            assert phase in phase_codes, f"阶段 {phase} 未被触发，实际阶段序列: {phase_codes}"

        # 验证 SGLang 独有阶段
        assert "kv_cache_allocating" in phase_codes, "SGLang 独有的 kv_cache_allocating 阶段未被触发"

        # 验证各阶段首次出现的 progress 值
        # sglang_single.py: engine_booting 首个模式 progress_calc=22
        assert get_first_progress_for_phase(captured, "engine_booting") == 22, "engine_booting 首次 progress 应为 22"
        # model_loading 首个模式 "Load weight begin" progress_calc=32
        assert get_first_progress_for_phase(captured, "model_loading") == 32, "model_loading 首次 progress 应为 32"
        # kv_cache_allocating 首个模式 "Using KV cache dtype" progress_calc=62
        assert get_first_progress_for_phase(captured, "kv_cache_allocating") == 62, (
            "kv_cache_allocating 首次 progress 应为 62"
        )
        # cuda_graph_capturing 首个模式 "Capture cuda graph begin" progress_calc=72
        assert get_first_progress_for_phase(captured, "cuda_graph_capturing") == 72, (
            "cuda_graph_capturing 首次 progress 应为 72"
        )
        # server_checking progress_calc=99
        assert get_first_progress_for_phase(captured, "server_checking") == 99, "server_checking 首次 progress 应为 99"
        # ready progress_calc=100
        assert get_first_progress_for_phase(captured, "ready") == 100, "ready 首次 progress 应为 100"

        # 验证 model_loading 阶段 progress 范围（safetensors lambda: 36~60）
        max_model_loading = get_max_progress_for_phase(captured, "model_loading")
        assert max_model_loading == 60, f"model_loading 最大 progress 应为 60，实际为 {max_model_loading}"

        # 验证 kv_cache_allocating 阶段 progress 范围（62~70）
        max_kv = get_max_progress_for_phase(captured, "kv_cache_allocating")
        assert max_kv == 70, f"kv_cache_allocating 最大 progress 应为 70，实际为 {max_kv}"

        # 验证 cuda_graph_capturing 阶段 progress 范围（72~98）
        max_cuda = get_max_progress_for_phase(captured, "cuda_graph_capturing")
        assert max_cuda == 98, f"cuda_graph_capturing 最大 progress 应为 98，实际为 {max_cuda}"

        # 验证最终进度
        final_progress = get_final_progress(captured)
        assert final_progress == 100, f"最终进度应为 100，实际为 {final_progress}"

        # 验证 is_completed
        assert analyzer.is_completed, "analyzer.is_completed 应为 True"

        # 验证无 failed 状态
        assert not has_status(captured, "failed"), "进度行中不应出现 status=failed"
