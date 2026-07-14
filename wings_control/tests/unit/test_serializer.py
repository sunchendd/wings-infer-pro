"""Unit tests for rendering/serializer.py — 嵌套值 JSON 序列化。"""

from __future__ import annotations

import json

from wings_ctl.rendering.serializer import serialize_nested_value


class TestSerializeNestedValue:
    """嵌套值序列化测试。"""

    def test_compilation_config_roundtrip(self):
        """compilation_config 序列化后 json.loads 回来 == 原 dict。"""
        original = {
            "cudagraph_capture_sizes": [4, 8, 16, 32, 64, 128, 256],
            "cudagraph_mode": "FULL_DECODE_ONLY",
        }
        json_str = serialize_nested_value(original)
        assert json.loads(json_str) == original

    def test_speculative_config_roundtrip(self):
        """speculative_config 序列化后字段不多不少。"""
        original = {
            "method": "eagle3",
            "model": "lightseekorg/kimi-k2.5-eagle3",
            "num_speculative_tokens": 3,
        }
        json_str = serialize_nested_value(original)
        result = json.loads(json_str)
        assert result == original
        assert list(result.keys()) == ["method", "model", "num_speculative_tokens"]

    def test_list_roundtrip(self):
        """纯 list 序列化。"""
        original = [4, 8, 16, 32, 64]
        json_str = serialize_nested_value(original)
        assert json.loads(json_str) == original

    def test_compact_no_spaces(self):
        """输出紧凑,无空格。"""
        original = {"a": 1, "b": [1, 2]}
        json_str = serialize_nested_value(original)
        assert " " not in json_str
        assert json_str == '{"a":1,"b":[1,2]}'

    def test_no_sort_keys(self):
        """key 顺序保持 Python dict 插入顺序(不排序)。"""
        original = {"z_key": 1, "a_key": 2, "m_key": 3}
        json_str = serialize_nested_value(original)
        # 解析后 key 顺序保持
        keys = list(json.loads(json_str).keys())
        assert keys == ["z_key", "a_key", "m_key"]

    def test_nested_dict_with_unicode(self):
        """含 unicode 的值不被 ascii 转义。"""
        original = {"name": "模型名称"}
        json_str = serialize_nested_value(original)
        assert "模型名称" in json_str
        assert "\\u" not in json_str

    def test_kv_transfer_config_complex(self):
        """深层嵌套: kv_transfer_config。"""
        original = {
            "kv_connector": "MooncakeConnectorV1",
            "kv_role": "kv_producer",
            "kv_port": 30100,
            "engine_id": 1,
            "kv_connector_extra_config": {
                "prefill": {"dp_size": 2, "tp_size": 8},
                "decode": {"dp_size": 32, "tp_size": 1},
            },
        }
        json_str = serialize_nested_value(original)
        assert json.loads(json_str) == original
