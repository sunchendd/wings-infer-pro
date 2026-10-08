"""TC-Accel-OK — wings-accel 加速特性安装进度匹配测试。

对齐 wings-accel MR#39 (commit 4d29fda, "add install.py progress logs) 引入的
stdout 进度日志：install.py 通过 log_config 输出 ``[wings-accel] <msg>`` 行到
engine.log，供 log_analyzer 的 accel_enabling 阶段模式匹配。

日志: data/wings_accel_install.log (真实 install.py 进度流,含 start→version→
package→applied→complete 全阶段)。

验证点：
1. 首次触发即进入 accel_enabling 阶段,首个 progress=10
2. 进度单调递增,安装完成时达到 accel_enabling 最大值 20
3. 无 failed 状态
"""

from __future__ import annotations

from .conftest import (
    extract_phase_codes,
    get_first_progress_for_phase,
    get_max_progress_for_phase,
    has_status,
    make_config,
    run_progress_analysis,
)


class TestAccelProgress:
    """wings-accel 加速特性安装进度匹配测试。"""

    @staticmethod
    def test_accel_install_progress(data_dir, tmp_path):
        """TC-Accel-OK: install.py 进度日志的 accel_enabling 阶段匹配。

        验证 accel_enabling 阶段被触发,且进度从 10 单调递增至 20。
        """
        log_path = data_dir / "wings_accel_install.log"
        config = make_config(engine="vllm", hardware="nvidia", mode="single")

        analyzer, captured = run_progress_analysis(log_path, config, tmp_path)

        phase_codes = extract_phase_codes(captured)

        # accel_enabling 阶段必须被触发
        assert "accel_enabling" in phase_codes, (
            f"accel_enabling 阶段未被触发,实际阶段序列: {phase_codes}"
        )

        # 首次触发 progress=10（Installing patches from /accel-volume）
        first = get_first_progress_for_phase(captured, "accel_enabling")
        assert first == 10, f"accel_enabling 首次 progress 应为 10,实际为 {first}"

        # 安装完成时达到 accel_enabling 最大值 20（wings-accel installation complete）
        max_progress = get_max_progress_for_phase(captured, "accel_enabling")
        assert max_progress == 20, f"accel_enabling 最大 progress 应为 20,实际为 {max_progress}"

        # 进度单调递增（_check_progress_patterns 中 max(progress, current_progress) 保证）
        accel_values = [int(e["progress"]) for e in captured if e.get("phase_code") == "accel_enabling"]
        assert accel_values == sorted(accel_values), f"accel_enabling 进度应单调递增,实际为 {accel_values}"

        # 无 failed 状态
        assert not has_status(captured, "failed"), "进度行中不应出现 status=failed"
