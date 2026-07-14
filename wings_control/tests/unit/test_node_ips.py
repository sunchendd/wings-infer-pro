"""NODE_IPS 解析统一回归测试(backlog #2)。

锁定修复:cli 侧 `_parse_runtime_context_from_env` 旧实现只 `split(",")` 不去方括号,
MaaS 下发 `"[ip1,ip2]"` 时首尾 IP 会粘上 `[` / `]` → multi_node 按 IP 选节点失配。
现统一走 `env_utils.parse_node_ips`(先剥方括号再切分),与 `get_node_ips` 的方括号口径同源。
"""

from __future__ import annotations

import pytest

from wings_ctl.cli import _parse_runtime_context_from_env
from wings_ctl.utils.env_utils import get_node_ips, parse_node_ips


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ip1,ip2,ip3", ["ip1", "ip2", "ip3"]),          # 裸逗号分隔
        ("[ip1,ip2,ip3]", ["ip1", "ip2", "ip3"]),        # 带方括号(MaaS 形态)→ 剥掉
        ("[ip1, ip2 , ip3]", ["ip1", "ip2", "ip3"]),     # 方括号 + 段内空格 → strip
        (" ip1 ,ip2 ", ["ip1", "ip2"]),                  # 前后空格 → strip
        ("ip1,,ip2", ["ip1", "ip2"]),                    # 空段丢弃
        ("ip1", ["ip1"]),                                # 单 IP
    ],
)
def test_parse_node_ips_variants(raw, expected):
    """验证:parse_node_ips 对带/不带方括号、含空格/空段的输入都归一到干净 IP 列表。"""
    assert parse_node_ips(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "[]", "[ , ]"])
def test_parse_node_ips_empty_returns_none(raw):
    """验证:未设置 / 空串 / 纯空白 / 方括号空壳 → None(不返回空列表)。"""
    assert parse_node_ips(raw) is None


def test_parse_node_ips_strips_brackets_not_left_on_edges():
    """验证:回归 bug —— 首尾 IP 不再残留 `[` / `]`。"""
    result = parse_node_ips("[10.0.0.1,10.0.0.2]")
    assert result == ["10.0.0.1", "10.0.0.2"]
    assert not any("[" in ip or "]" in ip for ip in result)


def test_get_node_ips_string_contract_unchanged(monkeypatch):
    """验证:get_node_ips 仍返回逗号字符串(仅去方括号),契约不变。"""
    monkeypatch.setenv("NODE_IPS", "[ip1,ip2]")
    assert get_node_ips() == "ip1,ip2"
    monkeypatch.setenv("NODE_IPS", "ip1,ip2")
    assert get_node_ips() == "ip1,ip2"
    monkeypatch.delenv("NODE_IPS", raising=False)
    assert get_node_ips() is None


def test_cli_runtime_context_debrackets_node_ips(monkeypatch):
    """验证:cli._parse_runtime_context_from_env 对带方括号的 NODE_IPS 产出干净列表。"""
    monkeypatch.setenv("RANK_IP", "10.0.0.2")
    monkeypatch.setenv("MASTER_IP", "10.0.0.1")
    monkeypatch.setenv("NODE_IPS", "[10.0.0.1,10.0.0.2]")
    rank_ip, master_ip, node_ips = _parse_runtime_context_from_env()
    assert rank_ip == "10.0.0.2"
    assert master_ip == "10.0.0.1"
    assert node_ips == ["10.0.0.1", "10.0.0.2"]
    # rank_ip 能在解析后的列表里匹配到(多机选节点的前提)。
    assert rank_ip in node_ips


def test_cli_runtime_context_node_ips_unset(monkeypatch):
    """验证:NODE_IPS 未设置 → node_ips=None(走占位视图,默认语义不变)。"""
    monkeypatch.delenv("NODE_IPS", raising=False)
    monkeypatch.delenv("RANK_IP", raising=False)
    monkeypatch.delenv("MASTER_IP", raising=False)
    rank_ip, master_ip, node_ips = _parse_runtime_context_from_env()
    assert (rank_ip, master_ip, node_ips) == (None, None, None)


def _normalize_get_node_ips(value):
    """把 get_node_ips 的字符串结果归一为 IP 列表,用于与 cli 路径对齐比较。

    get_node_ips 返回逗号字符串(仅去方括号、不 strip/过滤),这里补上 strip/过滤,
    使两条路径可在"解析出的 IP 集合"层面直接比较(锁定 backlog #2 的一致性不变量)。
    """
    if not value:
        return []
    return [ip.strip() for ip in value.split(",") if ip.strip()]


@pytest.mark.parametrize(
    "raw",
    ["10.0.0.1,10.0.0.2", "[10.0.0.1,10.0.0.2]", "[ 10.0.0.1, 10.0.0.2 ]", "", "[]"],
)
def test_cli_and_get_node_ips_consistent(monkeypatch, raw):
    """验证:cli 路径(_parse_runtime_context_from_env)与 env_utils.get_node_ips 归一后结果一致。

    二者返回类型不同(list vs 字符串),但去方括号已收敛到同一 _strip_ip_brackets;
    归一后 IP 列表必须一致——这是本 backlog 要保证的核心不变量。
    """
    monkeypatch.setenv("NODE_IPS", raw)
    monkeypatch.setenv("MASTER_IP", "10.0.0.1")
    _, _, cli_node_ips = _parse_runtime_context_from_env()
    cli_list = cli_node_ips or []
    assert cli_list == _normalize_get_node_ips(get_node_ips())


def test_cli_and_get_node_ips_consistent_when_unset(monkeypatch):
    """验证:NODE_IPS 未设置时两条路径也一致(cli→None、get_node_ips→None,归一均为空列表)。"""
    monkeypatch.delenv("NODE_IPS", raising=False)
    monkeypatch.setenv("MASTER_IP", "10.0.0.1")
    _, _, cli_node_ips = _parse_runtime_context_from_env()
    assert (cli_node_ips or []) == _normalize_get_node_ips(get_node_ips()) == []
