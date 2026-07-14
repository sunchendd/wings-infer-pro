"""Unit tests for rendering/env_renderer.py — env 安全渲染。"""

from __future__ import annotations

import pytest

from wings_ctl.rendering.env_renderer import render_env_export


class TestEnvRendererLiteral:
    """纯字面值(不含 $)的渲染测试。"""

    def test_int_value(self):
        """整数值渲染为字面 shlex.quote。"""
        result = render_env_export("HCCL_INTRA_PCIE_ENABLE", 1)
        assert result == "export HCCL_INTRA_PCIE_ENABLE=1"

    def test_string_with_colon(self):
        """含冒号的字符串 — shlex.quote 认为冒号安全,不加引号。"""
        result = render_env_export("PYTORCH_NPU_ALLOC_CONF", "expandable_segments:True")
        assert result == "export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True"

    def test_simple_string(self):
        """简单字符串(无特殊字符)渲染为字面。"""
        result = render_env_export("HCCL_OP_EXPANSION_MODE", "AIV")
        assert result == "export HCCL_OP_EXPANSION_MODE=AIV"

    def test_string_with_spaces(self):
        """含空格的字符串用 shlex.quote。"""
        result = render_env_export("MY_VAR", "hello world")
        assert result == "export MY_VAR='hello world'"

    def test_empty_string(self):
        """空字符串渲染为 ''。"""
        result = render_env_export("EMPTY", "")
        assert result == "export EMPTY=''"

    def test_python_false_string(self):
        """字符串 'False' 渲染为字面。"""
        result = render_env_export("OMP_PROC_BIND", "False")
        assert result == "export OMP_PROC_BIND=False"


class TestEnvRendererVariableRef:
    """含合法变量引用($ 开头)的渲染测试。"""

    def test_simple_var_ref(self):
        """$LD_PRELOAD 作为合法变量引用,用双引号。"""
        result = render_env_export("LD_PRELOAD", "/path/lib.so:$LD_PRELOAD")
        assert result == 'export LD_PRELOAD="/path/lib.so:$LD_PRELOAD"'

    def test_braced_var_ref(self):
        """${HOME} 花括号形式也放行。"""
        result = render_env_export("MY_PATH", "${HOME}/bin")
        assert result == 'export MY_PATH="${HOME}/bin"'

    def test_multiple_var_refs(self):
        """/path:$A:$B 多变量引用放行。"""
        result = render_env_export("PATH_LIKE", "/path:$A:$B")
        assert result == 'export PATH_LIKE="/path:$A:$B"'

    def test_value_with_quote_in_var(self):
        """含双引号的变量引用值,双引号被转义。"""
        result = render_env_export("MY_VAR", '/path/"file":$HOME')
        assert result == 'export MY_VAR="/path/\\"file\\":$HOME"'


class TestEnvRendererRejection:
    """不安全 $ 构造被拒绝的测试。"""

    def test_command_substitution_dollar_paren(self):
        """$(...) 命令替换被拒绝。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("EVIL", "$(rm -rf /)")

    def test_command_substitution_in_path(self):
        """路径中嵌入 $(...) 被拒绝。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("EVIL", "/safe/path:$(evil)")

    def test_backtick(self):
        """反引号命令替换被拒绝。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("EVIL", "hello `cmd` world")

    def test_trailing_dollar(self):
        """尾随孤立 $ 被拒绝。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("EVIL", "value$")

    def test_dollar_number(self):
        """$1 等位置参数不是合法变量引用(不匹配 [A-Za-z_])被拒绝。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("EVIL", "arg$1")

    def test_var_with_default_syntax(self):
        """${VAR:-$(evil)} 被拒绝(移除 ${VAR} 后剩余含 $(...))。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("EVIL", "${VAR:-$(evil)}")

    def test_braced_var_with_colon_dash_accepted(self):
        """${VAR:-default} 参数扩展默认值被接受(安全:无命令替换)。

        2026-07-02 改:此前误拒;`${VAR:-literal}` / `${VAR:+:$VAR}` 是合法 bash 参数扩展、
        无命令执行,应放行(LD_PRELOAD 条件追加即此形态)。命令替换 `${VAR:-$(evil)}` 仍拒
        (见 test_var_with_default_syntax)。
        """
        assert render_env_export("MY", "${VAR:-default}") == 'export MY="${VAR:-default}"'

    def test_braced_var_with_subst_in_default(self):
        """${VAR:-$(evil)} — default 部分含 $(...),被拒。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("MY", "${VAR:-$(evil)}")

    def test_dollar_open_brace_no_close(self):
        """${incomplete 不匹配完整变量引用,$ 残留被拒。"""
        with pytest.raises(ValueError, match="unsafe shell constructs"):
            render_env_export("BAD", "${incomplete")
