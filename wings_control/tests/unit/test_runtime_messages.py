"""Runtime message locale regression tests."""

from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_CALLS = {
    "debug",
    "info",
    "warning",
    "error",
    "exception",
    "critical",
    "print",
}
_CLI_TEXT_KEYWORDS = {"help", "description", "epilog"}


def _contains_chinese(node: ast.AST) -> bool:
    """检查 AST 子树中的字符串常量是否包含中文字符。

    Args:
        node: 待检查的语法树节点。

    Returns:
        字符串常量中包含中文字符时返回 True。
    """
    for item in ast.walk(node):
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            continue
        if any("\u4e00" <= char <= "\u9fff" for char in item.value):
            return True
    return False


def _runtime_message_nodes(source_path: Path) -> list[int]:
    """收集文件中包含中文的用户可见运行时消息行。

    Args:
        source_path: 待扫描的 Python 源文件。

    Returns:
        含中文的 raise、logger 或 print 调用行号列表。
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None and _contains_chinese(node.exc):
            lines.append(node.lineno)
            continue
        if not isinstance(node, ast.Call) or not _contains_chinese(node):
            continue
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        else:
            name = ""
        if name in _RUNTIME_CALLS:
            lines.append(node.lineno)
            continue
        if any(keyword.arg in _CLI_TEXT_KEYWORDS for keyword in node.keywords):
            lines.append(node.lineno)
    return lines


def test_wings_ctl_runtime_messages_are_english() -> None:
    """验证 wings_ctl 的异常、日志和标准输出不包含中文运行时文本。"""
    source_root = Path(__file__).resolve().parents[2] / "src" / "wings_ctl"
    violations: list[str] = []
    for source_path in sorted(source_root.rglob("*.py")):
        lines = _runtime_message_nodes(source_path)
        if lines:
            violations.append(f"{source_path.relative_to(source_root)}:{lines}")
    assert not violations, "Chinese runtime messages found: " + "; ".join(violations)


def test_wings_ctl_runtime_shell_assets_are_english() -> None:
    """验证可执行 Shell 脚本和模板的非注释运行时文本不包含中文。"""
    source_root = Path(__file__).resolve().parents[2] / "src" / "wings_ctl"
    violations: list[str] = []
    shell_assets = [*source_root.rglob("*.sh"), *source_root.rglob("*.tmpl")]
    for source_path in sorted(shell_assets):
        lines: list[int] = []
        for line_number, line in enumerate(source_path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if any("\u4e00" <= char <= "\u9fff" for char in line):
                lines.append(line_number)
        if lines:
            violations.append(f"{source_path.relative_to(source_root)}:{lines}")
    assert not violations, "Chinese runtime shell text found: " + "; ".join(violations)
