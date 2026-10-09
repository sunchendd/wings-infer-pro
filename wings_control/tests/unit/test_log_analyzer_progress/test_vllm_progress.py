"""TC-vLLM-OK / TC-vLLM-Ascend-OK — vLLM 引擎部署进度匹配测试。

验证 vLLM CUDA 和 vLLM Ascend 的日志模式匹配能正确产出阶段进度序列，
各阶段的 progress 值符合插件定义的预期值，最终到达 ready 阶段且 progress=100。
"""

from __future__ import annotations

import re

from wings_ctl.log_analyzer.plugins.vllm_single import VLLMSingleGPUPlugin

from .conftest import (
    extract_phase_codes,
    get_final_progress,
    get_first_progress_for_phase,
    get_max_progress_for_phase,
    has_status,
    make_config,
    run_progress_analysis,
)


class TestVLLMProgress:
    """vLLM 引擎进度匹配测试。"""

    @staticmethod
    def test_model_loading_patterns_cover_multithread_loader():
        """通用 vLLM 插件应覆盖 prefetch 多线程 loader 的分片进度与收尾日志。"""
        plugin = VLLMSingleGPUPlugin({})
        patterns = plugin.get_log_patterns()
        compiled_patterns = [(re.compile(entry["pattern"]), entry) for entry in patterns]

        def progress_for(line: str) -> int:
            for pattern, entry in compiled_patterns:
                match = pattern.search(line)
                if match:
                    calc = entry["progress_calc"]
                    return calc(match, 32) if callable(calc) else calc
            raise AssertionError(f"未匹配日志: {line}")

        assert progress_for("Multi-thread loading shards: 53% Completed | 20/38") == 48
        assert progress_for("Loading weights took 18.79 seconds") == 60
        assert progress_for("Loading model weights took 12.7741 GB") == 60

    @staticmethod
    def test_vllm_cuda_tp1_progress(data_dir, tmp_path):
        """TC-vLLM-OK: vLLM CUDA TP1 完整部署日志的进度匹配。

        日志: vllm_cuda_tp1.log (vLLM v0.17.1, Qwen3-32B, CUDA, OpenAI API)

        验证点：
        1. 各阶段依次触发: engine_booting → model_loading → model_compiling
           → cuda_graph_capturing → server_checking → ready
        2. 各阶段首次出现的 progress 值符合插件定义的预期值
        3. 进度单调递增（max(progress, current_progress) 保证）
        4. 最终 progress=100, is_completed=True
        5. 所有进度行 status 均为 running（无 failed）
        """
        log_path = data_dir / "vllm_cuda_tp1.log"
        config = make_config(engine="vllm", hardware="nvidia", mode="single")

        analyzer, captured = run_progress_analysis(log_path, config, tmp_path)

        phase_codes = extract_phase_codes(captured)

        # 验证关键阶段被触发
        expected_phases = [
            "engine_booting",
            "model_loading",
            "model_compiling",
            "cuda_graph_capturing",
            "server_checking",
            "ready",
        ]
        for phase in expected_phases:
            assert phase in phase_codes, f"阶段 {phase} 未被触发，实际阶段序列: {phase_codes}"

        # 验证各阶段首次出现的 progress 值（对应插件中定义的 progress_calc）
        # vllm_single.py: engine_booting 首个模式 progress_calc=22
        assert get_first_progress_for_phase(captured, "engine_booting") == 22, "engine_booting 首次 progress 应为 22"
        # model_loading 首个模式 "Starting to load model" progress_calc=32
        assert get_first_progress_for_phase(captured, "model_loading") == 32, "model_loading 首次 progress 应为 32"
        # model_compiling 首个模式 "Using cache directory" progress_calc=62
        assert get_first_progress_for_phase(captured, "model_compiling") == 62, "model_compiling 首次 progress 应为 62"
        # cuda_graph_capturing 首个模式 "Available KV cache" progress_calc=75
        assert get_first_progress_for_phase(captured, "cuda_graph_capturing") == 75, (
            "cuda_graph_capturing 首次 progress 应为 75"
        )
        # server_checking progress_calc=99
        assert get_first_progress_for_phase(captured, "server_checking") == 99, "server_checking 首次 progress 应为 99"
        # ready progress_calc=100
        assert get_first_progress_for_phase(captured, "ready") == 100, "ready 首次 progress 应为 100"

        # 验证 model_loading 阶段 progress 范围（safetensors 百分比 lambda: 36~60）
        max_model_loading = get_max_progress_for_phase(captured, "model_loading")
        assert max_model_loading == 60, f"model_loading 最大 progress 应为 60，实际为 {max_model_loading}"

        # 验证 cuda_graph_capturing 阶段 progress 范围（75~98）
        max_cuda = get_max_progress_for_phase(captured, "cuda_graph_capturing")
        assert max_cuda == 98, f"cuda_graph_capturing 最大 progress 应为 98，实际为 {max_cuda}"

        # 验证最终进度
        final_progress = get_final_progress(captured)
        assert final_progress == 100, f"最终进度应为 100，实际为 {final_progress}"

        # 验证 is_completed
        assert analyzer.is_completed, "analyzer.is_completed 应为 True"

        # 验证无 failed 状态
        assert not has_status(captured, "failed"), "进度行中不应出现 status=failed"

    @staticmethod
    def test_vllm_ascend_tp4_progress(data_dir, tmp_path):
        """TC-vLLM-Ascend-OK: vLLM Ascend TP4 完整部署日志的进度匹配。

        日志: vllm_ascend_tp4.log (vLLM v0.17.0, Qwen3-Next-80B, Ascend NPU, TP4)

        验证点：
        1. Ascend 特有模式 "Platform plugin ascend is activated" 被匹配
           （engine_booting 首次 progress=20，低于 CUDA 的 22）
        2. 各阶段依次触发
        3. 各阶段 progress 值符合预期
        4. 最终 progress=100, is_completed=True
        """
        log_path = data_dir / "vllm_ascend_tp4.log"
        config = make_config(engine="vllm-ascend", hardware="ascend", mode="single")

        analyzer, captured = run_progress_analysis(log_path, config, tmp_path)

        phase_codes = extract_phase_codes(captured)

        # 验证 engine_booting 阶段被触发
        assert "engine_booting" in phase_codes, f"engine_booting 阶段未被触发，实际阶段序列: {phase_codes}"

        # Ascend 特有模式 progress_calc=20（低于 CUDA 的 22）
        first_engine_booting = get_first_progress_for_phase(captured, "engine_booting")
        assert first_engine_booting == 20, (
            f"Ascend engine_booting 首次 progress 应为 20（Platform plugin ascend），实际为 {first_engine_booting}"
        )

        # 验证关键阶段
        expected_phases = [
            "engine_booting",
            "model_loading",
            "server_checking",
            "ready",
        ]
        for phase in expected_phases:
            assert phase in phase_codes, f"阶段 {phase} 未被触发，实际阶段序列: {phase_codes}"

        # 验证各阶段 progress 值
        assert get_first_progress_for_phase(captured, "model_loading") == 32, "model_loading 首次 progress 应为 32"
        assert get_first_progress_for_phase(captured, "server_checking") == 99, "server_checking 首次 progress 应为 99"
        assert get_first_progress_for_phase(captured, "ready") == 100, "ready 首次 progress 应为 100"

        # 验证最终进度
        final_progress = get_final_progress(captured)
        assert final_progress == 100, f"最终进度应为 100，实际为 {final_progress}"

        # 验证 is_completed
        assert analyzer.is_completed, "analyzer.is_completed 应为 True"

        # 验证无 failed 状态
        assert not has_status(captured, "failed"), "进度行中不应出现 status=failed"
