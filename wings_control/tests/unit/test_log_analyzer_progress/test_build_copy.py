"""TC-BUILD-1/2 — 构建流程中 log_analyzer 模块拷贝检查。

验证 Dockerfile 在 pyc 编译前将 log_analyzer 拷贝到 /opt/log_analyzer，
以及 wings_start.sh 在运行时将 /opt/log_analyzer 拷贝到共享卷。
"""

from __future__ import annotations

import re


class TestBuildCopyLogAnalyzer:
    """构建层：log_analyzer 模块拷贝链路验证。"""

    def test_dockerfile_copies_log_analyzer_before_pyc(
        self,
        dockerfile_path,
    ):
        """TC-BUILD-1: Dockerfile 在 compile_wings.sh 加密前 COPY log_analyzer。

        验证点：
        1. Dockerfile 中存在 COPY log_analyzer → /opt/log_analyzer 的指令
        2. 该 COPY 出现在 compile_wings.sh 调用之前（pyc 编译前）
        3. 注释说明拷贝原因（pyc 兼容性）
        """
        content = dockerfile_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # 查找 COPY log_analyzer 行
        copy_line_idx = None
        for i, line in enumerate(lines):
            if re.search(
                r"COPY\s+\S*log_analyzer\s+/opt/log_analyzer",
                line,
            ):
                copy_line_idx = i
                break

        assert copy_line_idx is not None, "Dockerfile 中未找到 COPY log_analyzer → /opt/log_analyzer 指令"

        # 查找 compile_wings.sh 调用行
        compile_line_idx = None
        for i, line in enumerate(lines):
            if "compile_wings" in line and ("RUN" in line or "bash" in line):
                compile_line_idx = i
                break

        # 如果存在 compile_wings.sh 调用，验证 COPY 在其之前
        if compile_line_idx is not None:
            assert copy_line_idx < compile_line_idx, (
                f"COPY log_analyzer (行 {copy_line_idx + 1}) 必须在 compile_wings.sh (行 {compile_line_idx + 1}) 之前"
            )

        # 验证上方有注释说明拷贝原因
        comment_lines = lines[max(0, copy_line_idx - 3) : copy_line_idx]
        comment_text = " ".join(comment_lines)
        assert any(kw in comment_text for kw in ["pyc", "magic", "加密", "编译", "兼容"]), (
            f"COPY log_analyzer 上方缺少注释说明拷贝原因（pyc 兼容性），实际注释: {comment_lines}"
        )

    def test_wings_start_copies_log_analyzer_to_shared_volume(
        self,
        wings_start_path,
    ):
        """TC-BUILD-2: wings_start.sh 将 /opt/log_analyzer 拷贝到共享卷。

        验证点：
        1. wings_start.sh 中存在 cp -r /opt/log_analyzer → /shared-volume/ 的操作
        2. 拷贝前有目录存在性判断 (if [ -d ... ])
        3. 使用环境变量默认值（DEFAULT_LOG_ANALYZER / SHARED_VOLUME_PATH）
        """
        content = wings_start_path.read_text(encoding="utf-8")

        # 验证 cp 命令存在
        assert re.search(
            r"cp\s+-r\s+.*log_analyzer.*shared.?volume",
            content,
            re.IGNORECASE,
        ), "wings_start.sh 中未找到 cp -r log_analyzer → shared-volume 操作"

        # 验证目录存在性判断
        assert re.search(
            r"if\s+\[\s+-d\s+.*log_analyzer",
            content,
        ), "wings_start.sh 中未找到 log_analyzer 目录存在性判断"

        # 验证使用环境变量默认值
        assert "DEFAULT_LOG_ANALYZER" in content, "wings_start.sh 中未使用 DEFAULT_LOG_ANALYZER 环境变量"
        assert "SHARED_VOLUME_PATH" in content, "wings_start.sh 中未使用 SHARED_VOLUME_PATH 环境变量"
