"""port_plan 默认 backend 端口回归(backlog #3:消除 "17000" 双写)。

锁定:port_plan 不再硬编码 "17000",而是复用 core.constants.DEFAULT_ENGINE_PORT,
与 config_resolver 单点同源;默认端口仍为 17000(零行为变化)。
config_resolver 侧的 17000 兜底另由 tests/unit/test_builtin_defaults.py::test_builtin_default_constant 覆盖。
"""

from __future__ import annotations

from wings_ctl.core.config_resolver import DEFAULT_ENGINE_PORT as RESOLVER_PORT
from wings_ctl.core.constants import DEFAULT_ENGINE_PORT
from wings_ctl.core.port_plan import derive_port_plan


def test_default_engine_port_value_is_17000():
    """验证:唯一常量值仍为 17000。"""
    assert DEFAULT_ENGINE_PORT == 17000


def test_config_resolver_reexports_same_constant():
    """验证:config_resolver 的 DEFAULT_ENGINE_PORT 就是 constants 的同一常量(单一来源)。"""
    assert RESOLVER_PORT == DEFAULT_ENGINE_PORT == 17000


def test_port_plan_backend_defaults_to_constant(monkeypatch):
    """验证:ENGINE_PORT 未设置时 derive_port_plan 的 backend_port 落到 DEFAULT_ENGINE_PORT(17000)。"""
    monkeypatch.delenv("ENGINE_PORT", raising=False)
    plan = derive_port_plan(port=18000, enable_reason_proxy=True)
    assert plan.backend_port == DEFAULT_ENGINE_PORT == 17000


def test_port_plan_backend_env_override_unchanged(monkeypatch):
    """验证:ENGINE_PORT 覆盖行为不变(设 17001 → backend_port=17001)。"""
    monkeypatch.setenv("ENGINE_PORT", "17001")
    plan = derive_port_plan(port=18000, enable_reason_proxy=True)
    assert plan.backend_port == 17001
