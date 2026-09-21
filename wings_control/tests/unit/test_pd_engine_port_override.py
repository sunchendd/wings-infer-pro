"""PD engine backend 端口基座覆盖(--engine-port / ENGINE_PORT env)的单元测试。

覆盖范围:
- ``_resolve_pd_engine_port_base_override`` 的三级优先级与非法 env 拒绝;
- ``_build_pd_process_plan`` 在显式覆盖下的端口展开、范围校验和审计 notes;
- 覆盖端口与 DP RPC/KV listener 区间冲突时在脚本生成前失败。
未覆盖(不传参)的路径由既有 ``test_process_plan_rejects_ambient_engine_port`` 保护。
"""

from __future__ import annotations

import pytest

from wings_ctl.core.config_resolver import (
    _build_pd_process_plan,
    _resolve_pd_engine_port_base_override,
)
from wings_ctl.core.models import UserInput

from tests.unit.test_pd_process_plan import _resolved, _runtime


def _argv_value(argv: list[str], option: str) -> str:
    """返回结构化 engine argv 中指定选项的值。"""
    return argv[argv.index(option) + 1]


class TestResolvePdEnginePortBaseOverride:
    """``_resolve_pd_engine_port_base_override`` 的优先级与来源判定。"""

    @staticmethod
    def test_cli_engine_port_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
        """--engine-port 与 ENGINE_PORT 同时存在时,显式传参优先。"""
        monkeypatch.setenv("ENGINE_PORT", "17600")

        override, source = _resolve_pd_engine_port_base_override(UserInput(engine_port=17500))

        assert (override, source) == (17500, "--engine-port")

    @staticmethod
    def test_env_used_when_cli_absent(monkeypatch: pytest.MonkeyPatch) -> None:
        """未传 --engine-port 时,ambient ENGINE_PORT 作为覆盖来源。"""
        monkeypatch.setenv("ENGINE_PORT", "17600")

        override, source = _resolve_pd_engine_port_base_override(UserInput())

        assert (override, source) == (17600, "ENGINE_PORT env")

    @staticmethod
    def test_no_input_keeps_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
        """--engine-port 与 ENGINE_PORT 均未提供时保持 recipe 端口,不产生覆盖。"""
        monkeypatch.delenv("ENGINE_PORT", raising=False)

        assert _resolve_pd_engine_port_base_override(UserInput()) == (None, "recipe")

    @staticmethod
    def test_invalid_env_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
        """ambient ENGINE_PORT 非整数时以可定位的错误拒绝。"""
        monkeypatch.setenv("ENGINE_PORT", "not-a-port")

        with pytest.raises(ValueError, match="PD ENGINE_PORT must be an integer"):
            _resolve_pd_engine_port_base_override(UserInput())


class TestBuildPdProcessPlanWithPortOverride:
    """显式端口基座覆盖下进程计划的端口展开与校验。"""

    @staticmethod
    def test_override_expands_process_ports_and_records_notes() -> None:
        """覆盖 17500 时 decode Pod(2 进程)端口为 17500/17501,并写入审计 notes。"""
        notes: dict[str, str] = {}

        plan = _build_pd_process_plan(
            _resolved(),
            _runtime(),
            device_count=2,
            port_base_override=17500,
            port_base_source="--engine-port",
            post_merge_notes=notes,
        )

        assert plan.endpoints == ["10.0.0.2:17500", "10.0.0.2:17501"]
        assert [_argv_value(process.argv, "--port") for process in plan.processes] == ["17500", "17501"]
        assert notes["pd.engine_port_base"] == "17500"
        assert notes["pd.engine_port_base_source"] == "--engine-port"

    @staticmethod
    def test_override_beats_recipe_base() -> None:
        """覆盖生效时 recipe 的 backend_port_base 不再参与端口计算。"""
        runtime = _runtime()
        assert runtime.backend_port_base != 18000

        plan = _build_pd_process_plan(
            _resolved(),
            runtime,
            device_count=2,
            port_base_override=18000,
            port_base_source="ENGINE_PORT env",
        )

        assert plan.endpoints == ["10.0.0.2:18000", "10.0.0.2:18001"]

    @staticmethod
    def test_override_conflicting_with_rpc_listener_rejected() -> None:
        """覆盖端口与 DP RPC listener 区间重叠时,在脚本生成前失败。"""
        runtime = _runtime(rpc_port=17500)

        with pytest.raises(ValueError, match="PD listener conflict"):
            _build_pd_process_plan(
                _resolved(head=True),
                runtime,
                device_count=2,
                port_base_override=17500,
                port_base_source="--engine-port",
            )

    @pytest.mark.parametrize("base", [0, -1, 65535, 70000])
    @staticmethod
    def test_override_out_of_range_rejected(base: int) -> None:
        """覆盖基座使端口越出 1..65535 时,以包含来源的错误拒绝。"""
        with pytest.raises(ValueError, match="port base override"):
            _build_pd_process_plan(
                _resolved(),
                _runtime(),
                device_count=2,
                port_base_override=base,
                port_base_source="--engine-port",
            )

    @staticmethod
    def test_no_override_keeps_ambient_strict_check(monkeypatch: pytest.MonkeyPatch) -> None:
        """未显式覆盖时,ambient ENGINE_PORT 与 profile 不一致仍被拒绝(行为不变)。"""
        monkeypatch.setenv("ENGINE_PORT", "17999")

        with pytest.raises(ValueError, match="ENGINE_PORT"):
            _build_pd_process_plan(_resolved(), _runtime(), device_count=2)

    @staticmethod
    def test_no_override_writes_no_port_notes(monkeypatch: pytest.MonkeyPatch) -> None:
        """未覆盖时不产生 pd.engine_port_base 审计 notes,保持既有 audit 形状。"""
        monkeypatch.delenv("ENGINE_PORT", raising=False)
        notes: dict[str, str] = {}

        _build_pd_process_plan(_resolved(), _runtime(), device_count=2, post_merge_notes=notes)

        assert "pd.engine_port_base" not in notes
        assert "pd.engine_port_base_source" not in notes
