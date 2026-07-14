from __future__ import annotations

import logging

from wings_ctl.core.config_resolver import _select_scenario
from wings_ctl.core.topology import Topology


def test_select_scenario_direct_engine_config_no_warning(caplog):
    """旧格式 direct engine_config 分支不告警。"""
    model_data = {
        "scenarios": {
            "standalone": {
                "engine_config": {"model": "foo/model", "port": 8088},
                "env": {"A": "1"},
            }
        }
    }

    with caplog.at_level(logging.WARNING):
        scenario = _select_scenario(model_data, Topology.STANDALONE)

    assert scenario["engine_config"]["model"] == "foo/model"
    assert scenario["engine_config_source_prefix"] == "scenarios.standalone.engine_config"
    assert not any("检测到多策略 strategies 格式" in r.message for r in caplog.records)


def test_select_scenario_strategies_selects_single_default_without_warning(caplog):
    """新格式 strategies: 恰好一个 default_strategy=true 时选中且不告警。"""
    model_data = {
        "scenarios": {
            "standalone": {
                "strategies": {
                    "first_dep": {
                        "engine_config": {"model": "first/model", "port": 8001},
                        "env": {"A": "1"},
                    },
                    "second_tp": {
                        "default_strategy": True,
                        "engine_config": {"model": "second/model", "port": 8002},
                        "env": {"B": "2"},
                    },
                }
            }
        }
    }

    with caplog.at_level(logging.WARNING):
        scenario = _select_scenario(model_data, Topology.STANDALONE)

    assert scenario["engine_config"]["model"] == "second/model"
    assert scenario["engine_config_source_prefix"] == (
        "scenarios.standalone.strategies.second_tp.engine_config"
    )
    assert scenario["selected_strategy"] == "second_tp"
    assert scenario["strategy_selection_source"] == "default_strategy"
    assert scenario["strategy_default_candidates"] == ["second_tp"]
    assert not caplog.records


def test_select_scenario_strategies_no_default_fallbacks_to_first_with_warning(caplog):
    """新格式 strategies: 无 default_strategy=true 时告警并按插入序取第一个。"""
    model_data = {
        "scenarios": {
            "standalone": {
                "strategies": {
                    "first_dep": {
                        "engine_config": {"model": "first/model", "port": 8001},
                        "env": {"A": "1"},
                    },
                    "second_tp": {
                        "engine_config": {"model": "second/model", "port": 8002},
                        "env": {"B": "2"},
                    },
                }
            }
        }
    }

    with caplog.at_level(logging.WARNING):
        scenario = _select_scenario(model_data, Topology.STANDALONE)

    assert scenario["engine_config"]["model"] == "first/model"
    assert scenario["engine_config_source_prefix"] == (
        "scenarios.standalone.strategies.first_dep.engine_config"
    )
    assert scenario["selected_strategy"] == "first_dep"
    assert scenario["strategy_selection_source"] == "fallback_first_no_default"
    assert scenario["strategy_default_candidates"] == []
    assert any(
        "无 default_strategy=true,按顺序取第一个策略 'first_dep'" in r.message
        for r in caplog.records
    )


def test_select_scenario_strategies_multiple_defaults_fallbacks_to_first_default_with_warning(caplog):
    """新格式 strategies: 多个 default_strategy=true 时告警并取第一个 default。"""
    model_data = {
        "scenarios": {
            "standalone": {
                "strategies": {
                    "first_dep": {
                        "default_strategy": True,
                        "engine_config": {"model": "first/model", "port": 8001},
                        "env": {"A": "1"},
                    },
                    "second_tp": {
                        "default_strategy": True,
                        "engine_config": {"model": "second/model", "port": 8002},
                        "env": {"B": "2"},
                    },
                    "third_extra": {
                        "engine_config": {"model": "third/model", "port": 8003},
                        "env": {"C": "3"},
                    },
                }
            }
        }
    }

    with caplog.at_level(logging.WARNING):
        scenario = _select_scenario(model_data, Topology.STANDALONE)

    assert scenario["engine_config"]["model"] == "first/model"
    assert scenario["engine_config_source_prefix"] == (
        "scenarios.standalone.strategies.first_dep.engine_config"
    )
    assert scenario["selected_strategy"] == "first_dep"
    assert scenario["strategy_selection_source"] == "fallback_first_multiple_defaults"
    assert scenario["strategy_default_candidates"] == ["first_dep", "second_tp"]
    assert any(
        "存在多个 default_strategy=true (first_dep,second_tp),按顺序取第一个 default 'first_dep' (官网数据异常)"
        in r.message
        for r in caplog.records
    )
