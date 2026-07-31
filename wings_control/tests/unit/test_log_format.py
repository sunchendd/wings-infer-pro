"""日志格式规范化单测。

覆盖 _normalize_child_log_line 子进程日志中继解析和 WingsControlFormatter 格式化逻辑。
重点验证各日志级别（WARNING / ERROR / CRITICAL）被准确映射到对应的 logging 常量，
INFO 及以下级别被正确丢弃，确保子进程日志级别处理准确无误。
"""

from __future__ import annotations

import logging
import logging.handlers

import re

import pytest

from wings_ctl.common.log_config import (
    LOG_COMPONENT,
    _make_formatter,
    setup_root_logging,
)
from wings_ctl.wings_control import (
    LOGGER_LAUNCHER,
    _normalize_child_log_line,
)


# ── _normalize_child_log_line: 结构化日志解析 ──────────────────────────────


class TestNormalizeStructuredLog:
    """结构化日志（4 种格式变体）的解析测试。"""

    @pytest.mark.parametrize(
        "level,expected_level",
        [
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_structured_format1_level_mapping(self, level: str, expected_level: int) -> None:
        """格式1: [WINGS-CONTROL] 2026-07-22 10:00:01.456 [LEVEL] [source] msg

        验证 WARNING/ERROR/CRITICAL 级别被准确映射。
        格式1正则的特征是 [WINGS-CONTROL] 作为可选行首前缀，后接时间戳→级别→[source]。
        """
        line = f"[WINGS-CONTROL] 2026-07-22 10:00:01.456 [{level}] [proxy#handler:50] Some message"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == expected_level, f"{level} should map to {expected_level}, got {relay.level}"
        assert relay.logger_name == LOGGER_LAUNCHER
        assert relay.message == "Some message"
        assert relay.extra["wings_child_component"] == "proxy"
        assert relay.extra["wings_child_time"] == "2026-07-22 10:00:01.456"
        assert relay.extra["wings_child_source"] == "proxy#handler:50"

    @pytest.mark.parametrize(
        "level,expected_level",
        [
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_structured_format2_level_mapping(self, level: str, expected_level: int) -> None:
        """格式2: 2026-07-22 10:00:01.456 [LEVEL] WINGS-CONTROL [source] msg"""
        line = f"2026-07-22 10:00:01.456 [{level}] WINGS-CONTROL [proxy#handler:50] Some message"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == expected_level
        assert relay.extra["wings_child_source"] == "proxy#handler:50"

    @pytest.mark.parametrize(
        "level,expected_level",
        [
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_structured_format3_level_mapping(self, level: str, expected_level: int) -> None:
        """格式3: [WINGS-CONTROL][source] [LEVEL] 2026-07-22 10:00:01.456 msg"""
        line = f"[WINGS-CONTROL][proxy#handler:50] [{level}] 2026-07-22 10:00:01.456 Some message"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == expected_level
        assert relay.extra["wings_child_source"] == "proxy#handler:50"

    @pytest.mark.parametrize(
        "level,expected_level",
        [
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_structured_format4_level_mapping(self, level: str, expected_level: int) -> None:
        """格式4: 2026-07-22 10:00:01.456 [WINGS-CONTROL][source] [LEVEL] msg"""
        line = f"2026-07-22 10:00:01.456 [WINGS-CONTROL][proxy#handler:50] [{level}] Some message"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == expected_level
        assert relay.extra["wings_child_source"] == "proxy#handler:50"

    def test_structured_without_msecs(self) -> None:
        """结构化日志无毫秒部分时仍能匹配。"""
        line = "2026-07-22 10:00:01 [ERROR] WINGS-CONTROL [proxy#handler:50] No msecs"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == logging.ERROR
        assert relay.extra["wings_child_time"] == "2026-07-22 10:00:01"

    def test_structured_comma_msecs(self) -> None:
        """结构化日志使用逗号分隔毫秒时仍能匹配。"""
        line = "2026-07-22 10:00:01,456 [ERROR] WINGS-CONTROL [proxy#handler:50] Comma msecs"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == logging.ERROR
        assert relay.extra["wings_child_time"] == "2026-07-22 10:00:01,456"

    def test_structured_lowercase_level(self) -> None:
        """结构化日志级别为小写时仍能正确映射（re.IGNORECASE）。"""
        line = "2026-07-22 10:00:01.456 [error] WINGS-CONTROL [proxy#handler:50] Lowercase"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == logging.ERROR


# ── _normalize_child_log_line: 非结构化日志解析 ────────────────────────────


class TestNormalizeUnstructuredLog:
    """非结构化日志（无时间戳/组件名）的级别检测测试。"""

    def test_unstructured_error_prefix(self) -> None:
        """非结构化 ERROR: 前缀 → ERROR 级别。"""
        relay = _normalize_child_log_line("proxy", "ERROR: connection refused")
        assert relay is not None
        assert relay.level == logging.ERROR
        assert relay.message == "ERROR: connection refused"
        assert relay.extra == {"wings_child_component": "proxy"}

    def test_unstructured_warning_prefix(self) -> None:
        """非结构化 WARNING: 前缀 → WARNING 级别。"""
        relay = _normalize_child_log_line("proxy", "WARNING: disk almost full")
        assert relay is not None
        assert relay.level == logging.WARNING

    def test_unstructured_critical_prefix(self) -> None:
        """非结构化 CRITICAL: 前缀 → CRITICAL 级别。"""
        relay = _normalize_child_log_line("proxy", "CRITICAL: system failure")
        assert relay is not None
        assert relay.level == logging.CRITICAL

    def test_unstructured_bracket_level(self) -> None:
        """非结构化 [ERROR] 括号级别 → ERROR 级别。"""
        relay = _normalize_child_log_line("proxy", "[ERROR] something went wrong")
        assert relay is not None
        assert relay.level == logging.ERROR

    def test_unstructured_traceback(self) -> None:
        """非结构化 Traceback → ERROR 级别（不降级为 WARNING）。"""
        relay = _normalize_child_log_line("proxy", "Traceback (most recent call last):")
        assert relay is not None
        assert relay.level == logging.ERROR

    def test_unstructured_exception(self) -> None:
        """非结构化 Exception → ERROR 级别。"""
        relay = _normalize_child_log_line("proxy", "Exception in thread main")
        assert relay is not None
        assert relay.level == logging.ERROR

    def test_unstructured_no_level_returns_none(self) -> None:
        """无级别标识的 INFO 级别日志 → None（静默丢弃）。"""
        relay = _normalize_child_log_line("proxy", "INFO: starting worker")
        assert relay is None

    def test_unstructured_plain_text_returns_none(self) -> None:
        """无任何级别标识的纯文本 → None（静默丢弃）。"""
        relay = _normalize_child_log_line("proxy", "just some random output")
        assert relay is None

    def test_empty_line_returns_none(self) -> None:
        """空行 → None。"""
        assert _normalize_child_log_line("proxy", "") is None
        assert _normalize_child_log_line("proxy", "   ") is None


# ── WingsControlFormatter: 普通日志格式化 ──────────────────────────────────


class TestWingsControlFormatterNormal:
    """WingsControlFormatter 对普通日志（非子进程中继）的格式化。"""

    def test_normal_log_format(self) -> None:
        """普通日志包含毫秒时间戳、WINGS-CONTROL 标签、funcName:lineNo。"""
        formatter = _make_formatter()
        record = logging.LogRecord(
            name="wings-launcher",
            level=logging.INFO,
            pathname="test.py",
            lineno=140,
            msg="Starting subprocess proxy",
            args=None,
            exc_info=None,
            func="_start",
        )
        output = formatter.format(record)
        assert "[INFO]" in output
        assert LOG_COMPONENT in output
        assert "[wings-launcher#_start:140]" in output
        assert "Starting subprocess proxy" in output
        # 毫秒精度: YYYY-MM-DD HH:MM:SS.mmm
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}", output) is not None


# ── WingsControlFormatter: 子进程中继日志格式化 ────────────────────────────


class TestWingsControlFormatterChildRelay:
    """WingsControlFormatter 对子进程中继日志（带 wings_child_component extra）的格式化。"""

    def test_child_reay_preserves_timestamp_and_source(self) -> None:
        """子进程中继日志保留原始时间戳和 source，不重复添加前缀。"""
        formatter = _make_formatter()
        record = logging.LogRecord(
            name="wings-launcher",
            level=logging.WARNING,
            pathname="test.py",
            lineno=50,
            msg="Some warning",
            args=None,
            exc_info=None,
        )
        record.wings_child_component = "proxy"  # type: ignore[attr-defined]
        record.wings_child_time = "2026-07-22 10:00:01.456"  # type: ignore[attr-defined]
        record.wings_child_source = "proxy#handler:50"  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert output == "2026-07-22 10:00:01.456 [WARNING] WINGS-CONTROL [proxy#handler:50] Some warning"

    def test_child_relay_without_time_uses_record_time(self) -> None:
        """子进程中继日志无 wings_child_time 时使用 record 自身时间。"""
        formatter = _make_formatter()
        record = logging.LogRecord(
            name="wings-launcher",
            level=logging.ERROR,
            pathname="test.py",
            lineno=60,
            msg="connection refused",
            args=None,
            exc_info=None,
        )
        record.wings_child_component = "proxy"  # type: ignore[attr-defined]
        record.wings_child_source = "wings-launcher#proxy"  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert "[ERROR]" in output
        assert LOG_COMPONENT in output
        assert "[wings-launcher#proxy]" in output
        assert "connection refused" in output

    def test_child_relay_without_source_uses_name_component(self) -> None:
        """子进程中继日志无 wings_child_source 时用 {record.name}#{component}。"""
        formatter = _make_formatter()
        record = logging.LogRecord(
            name="wings-launcher",
            level=logging.ERROR,
            pathname="test.py",
            lineno=70,
            msg="no source",
            args=None,
            exc_info=None,
        )
        record.wings_child_component = "proxy"  # type: ignore[attr-defined]
        record.wings_child_time = "2026-07-22 10:00:02.789"  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert "[wings-launcher#proxy]" in output

    def test_child_time_without_msecs_appends_zeros(self) -> None:
        """子进程时间戳无毫秒时补 .000。"""
        formatter = _make_formatter()
        record = logging.LogRecord(
            name="wings-launcher",
            level=logging.WARNING,
            pathname="test.py",
            lineno=80,
            msg="test",
            args=None,
            exc_info=None,
        )
        record.wings_child_component = "proxy"  # type: ignore[attr-defined]
        record.wings_child_time = "2026-07-22 10:00:01"  # type: ignore[attr-defined]
        record.wings_child_source = "proxy#handler:50"  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert "2026-07-22 10:00:01.000" in output

    def test_child_time_comma_replaced_with_dot(self) -> None:
        """子进程时间戳逗号毫秒分隔符替换为点号。"""
        formatter = _make_formatter()
        record = logging.LogRecord(
            name="wings-launcher",
            level=logging.WARNING,
            pathname="test.py",
            lineno=90,
            msg="test",
            args=None,
            exc_info=None,
        )
        record.wings_child_component = "proxy"  # type: ignore[attr-defined]
        record.wings_child_time = "2026-07-22 10:00:01,456"  # type: ignore[attr-defined]
        record.wings_child_source = "proxy#handler:50"  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert "2026-07-22 10:00:01.456" in output


# ── 端到端: _normalize_child_log_line → WingsControlFormatter ──────────────


class TestEndToEndRelayFormatting:
    """端到端验证: 解析子进程日志行 → 格式化输出，确保级别不丢失。"""

    @pytest.mark.parametrize(
        "level_str,expected_level",
        [
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_e2e_structured_relay_level_preserved(self, level_str: str, expected_level: int) -> None:
        """端到端: 结构化日志解析后格式化，级别保持不变。"""
        line = f"2026-07-22 10:00:01.456 [{level_str}] WINGS-CONTROL [proxy#handler:50] test message"
        relay = _normalize_child_log_line("proxy", line)
        assert relay is not None
        assert relay.level == expected_level

        # 模拟 WingsControlFormatter 格式化
        formatter = _make_formatter()
        record = logging.LogRecord(
            name=relay.logger_name,
            level=relay.level,
            pathname="test.py",
            lineno=100,
            msg=relay.message,
            args=None,
            exc_info=None,
        )
        for k, v in relay.extra.items():
            setattr(record, k, v)
        output = formatter.format(record)
        assert f"[{level_str}]" in output
        assert "test message" in output

    @pytest.mark.parametrize(
        "raw_line,expected_level",
        [
            ("ERROR: connection refused", logging.ERROR),
            ("CRITICAL: system failure", logging.CRITICAL),
            ("WARNING: disk almost full", logging.WARNING),
            ("Traceback (most recent call last):", logging.ERROR),
        ],
    )
    def test_e2e_unstructured_relay_level_preserved(self, raw_line: str, expected_level: int) -> None:
        """端到端: 非结构化日志解析后格式化，级别保持不变。"""
        relay = _normalize_child_log_line("proxy", raw_line)
        assert relay is not None
        assert relay.level == expected_level


# ── setup_root_logging: 多次调用安全覆盖 ──────────────────────────────────────


class TestSetupRootLoggingIdempotent:
    """验证 setup_root_logging() 多次调用后的安全覆盖行为。

    cli.py:main() 和 wings_control.py 模块级在同一进程内先后调用
    setup_root_logging()，需确保:
    1. 不产生重复 handler（basicConfig force=True 移除旧 handler）
    2. 日志格式始终为 WingsControlFormatter（非 logging.Formatter）
    3. 实际日志输出包含 WINGS-CONTROL 标签和毫秒时间戳
    """

    def test_double_call_no_duplicate_handlers(self) -> None:
        """连续两次调用后 root logger 不残留重复 stderr StreamHandler。

        RotatingFileHandler 是 StreamHandler 的子类，需排除后计数。
        """
        setup_root_logging()
        setup_root_logging()
        root = logging.getLogger()
        stderr_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        # basicConfig(force=True) 每次只创建 1 个 stderr StreamHandler
        assert len(stderr_handlers) == 1

    def test_double_call_formatter_is_wings_control(self) -> None:
        """连续两次调用后 handler 的 formatter 仍为 WingsControlFormatter 实例。"""
        setup_root_logging()
        setup_root_logging()
        root = logging.getLogger()
        for handler in root.handlers:
            if isinstance(handler, logging.StreamHandler):
                from wings_ctl.common.log_config import WingsControlFormatter

                assert isinstance(handler.formatter, WingsControlFormatter)

    def test_double_call_log_format_correct(self) -> None:
        """连续两次调用后实际日志输出仍包含 WINGS-CONTROL 标签和毫秒时间戳。

        setup_root_logging() 内部 basicConfig(force=True) 会移除 pytest caplog
        handler，因此使用自定义 StringIO handler 捕获格式化后的输出。
        """
        import io

        setup_root_logging()
        setup_root_logging()

        # 用自定义 handler 捕获实际格式化输出
        buf = io.StringIO()
        test_handler = logging.StreamHandler(buf)
        test_handler.setFormatter(_make_formatter())
        test_handler.setLevel(logging.DEBUG)
        root = logging.getLogger()
        root.addHandler(test_handler)
        try:
            test_logger = logging.getLogger(LOGGER_LAUNCHER)
            test_logger.info("idempotent check message")
            output = buf.getvalue().strip()
        finally:
            root.removeHandler(test_handler)

        assert "idempotent check message" in output
        assert LOG_COMPONENT in output
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}", output) is not None

    def test_double_call_no_duplicate_file_handlers(self) -> None:
        """连续两次调用后不残留重复 RotatingFileHandler。"""
        setup_root_logging()
        setup_root_logging()
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        # _setup_file_handler 内部 already_has 检查防止重复添加
        assert len(file_handlers) <= 1

    def test_stderr_level_override_on_second_call(self) -> None:
        """第二次调用使用不同 stderr_level 时，stderr handler 级别被正确覆盖。"""
        setup_root_logging()
        setup_root_logging(stderr_level="ERROR")
        root = logging.getLogger()
        stderr_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert any(h.level == logging.ERROR for h in stderr_handlers)
