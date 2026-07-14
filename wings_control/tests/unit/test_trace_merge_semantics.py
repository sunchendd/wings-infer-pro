from __future__ import annotations

from wings_ctl.core.config_resolver import MergeLayer, trace_merge

# 注:旧的"四列长度不一致 → raise"专测已随 trace_merge 结构化(list[MergeLayer])下线——
# 四条平行列表已合并为具名结构,"下标错位/漏列"从源头消失,不再有该失败模式。


def test_trace_merge_one_level_merge_list_replace_and_trace_semantics():
    """锁定基础语义:一级 dict 合并 / list 整体替换 / 标量覆盖 + 完整 events 链。

    (深合并是其超集——一级 case 结果不变,见 test_trace_merge_deep_merges_nested_dicts。)
    """
    merged = trace_merge([
        MergeLayer("layer1", {"cfg": {"a": 1, "common": 1}, "items": [1, 2, 3], "port": 8000},
                   "layer1.yaml", "low"),
        MergeLayer("layer2", {"cfg": {"common": 9, "b": 2}, "items": [9], "port": 9000},
                   "layer2.yaml", "high"),
    ])

    assert merged["cfg"].final_value == {"a": 1, "common": 9, "b": 2}
    assert merged["items"].final_value == [9]

    port = merged["port"]
    assert port.final_value == 9000
    assert port.final_layer == "layer2"
    assert len(port.events) == 2
    assert port.events[0].action == "set"
    assert port.events[0].layer == "layer1"
    assert port.events[0].source_file == "layer1.yaml"
    assert port.events[1].action == "override"
    assert port.events[1].layer == "layer2"
    assert port.events[1].source_file == "layer2.yaml"


def test_trace_merge_deep_merges_nested_dicts():
    """I3:同一嵌套键跨层出现 → 内层键**递归合并**,而非第二层整块替换。"""
    merged = trace_merge([
        MergeLayer("base", {"additional_config": {"a": {"x": 1, "keep": 1}, "top": 1}},
                   "base.yaml", "base"),
        MergeLayer("override", {"additional_config": {"a": {"x": 9, "new": 2}, "top2": 3}},
                   "override.yaml", "override"),
    ])
    # a.keep 来自 base、未被第二层覆盖 → 证明递归深合并(浅合并会整块替换掉 a)
    assert merged["additional_config"].final_value == {
        "a": {"x": 9, "keep": 1, "new": 2},
        "top": 1,
        "top2": 3,
    }
    assert merged["additional_config"].final_layer == "override"
    assert len(merged["additional_config"].events) == 2  # trace 链不变


def test_trace_merge_list_still_whole_replace_under_deep_merge():
    """深合并下 list 仍整体替换(守 E3),不逐元素合并。"""
    merged = trace_merge([
        MergeLayer("a", {"items": [1, 2, 3]}, "a.yaml", "a"),
        MergeLayer("b", {"items": [9]}, "b.yaml", "b"),
    ])
    assert merged["items"].final_value == [9]
