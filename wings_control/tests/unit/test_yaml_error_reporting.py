"""Unit tests for locator YAML error reporting improvement."""

from __future__ import annotations


import pytest

from wings_ctl.loaders.locator import load_model_config


class TestYamlErrorReporting:
    """YAML 解析错误时 FileNotFoundError 包含详细信息。"""

    def test_yaml_error_included_in_message(self, tmp_path):
        """YAML 语法错误的文件路径和错误信息出现在 FileNotFoundError 中。"""
        # 构造目录结构
        models_dir = tmp_path / "engines" / "eng" / "v1.0.0" / "hw" / "models"
        model_subdir = models_dir / "broken-model"
        model_subdir.mkdir(parents=True)

        # 写一个有语法错误的 YAML
        bad_yaml = model_subdir / "broken.yaml"
        bad_yaml.write_text('invalid: [unclosed bracket\n  no_close: true\n')

        with pytest.raises(FileNotFoundError) as exc_info:
            load_model_config(tmp_path, "hw", "eng", "1.0.0", "SomeModel")

        msg = str(exc_info.value)
        assert "YAML parse errors" in msg
        assert "broken.yaml" in msg

    def test_yaml_flow_sequence_braces_error_in_message(self, tmp_path):
        """YAML flow sequence 内花括号导致的解析错误,文件名和错误类型出现在信息中。

        复现 DeepSeek-V4-Flash-fp8.yaml L45 的语法错误:
        args: [--flag, "{"key":"val"}"]
        YAML 将 "{"key" 解析为字符串,后续 ":val" 导致 flow sequence 解析失败。
        """
        models_dir = tmp_path / "engines" / "eng2" / "v2.0.0" / "hw2" / "models"
        model_subdir = models_dir / "flow-error"
        model_subdir.mkdir(parents=True)

        bad_yaml = model_subdir / "flow_error.yaml"
        bad_yaml.write_text("""model:
  name: FlowModel
  match:
    - name_pattern: "(?i)flow"
scenarios:
  standalone:
    engine_config:
      model: org/FlowModel
      args: [--speculative_config, "{"method":"mtp","num":2}"]
    env: {}
""")

        with pytest.raises(FileNotFoundError) as exc_info:
            load_model_config(tmp_path, "hw2", "eng2", "2.0.0", "SomeModel")

        msg = str(exc_info.value)
        assert "YAML parse errors" in msg
        assert "flow_error.yaml" in msg
        # 关键: 错误信息里出现了 YAML 解析器的具体报错,而不仅是笼统的"parsing failed"
        assert ("expected" in msg.lower() or "flow sequence" in msg.lower())

    def test_valid_yaml_no_match_no_error_detail(self, tmp_path, caplog):
        """有效 YAML 但不匹配 model_name 时,返回 no-match 而非 YAML 错误。"""
        models_dir = tmp_path / "engines" / "eng" / "v1.0.0" / "hw" / "models"
        model_subdir = models_dir / "other-model"
        model_subdir.mkdir(parents=True)

        # 写一个有效但不匹配的 YAML
        valid_yaml = model_subdir / "other.yaml"
        valid_yaml.write_text("""
model:
  name: OtherModel
  match:
    - name_pattern: "(?i)other"
scenarios:
  standalone:
    engine_config:
      model: org/OtherModel
    env: {}
""")

        data, yaml_path, matched_pattern = load_model_config(
            tmp_path, "hw", "eng", "1.0.0", "NoMatch"
        )

        assert data is None
        assert yaml_path is None
        assert matched_pattern == ""
        assert "YAML parse errors" not in caplog.text

    def test_invalid_name_pattern_skipped_not_crash(self, tmp_path):
        """F7 修复:某 recipe 的 name_pattern 是非法正则 → warn-skip 不崩 re.error;同目录合法 recipe 仍命中。"""
        models_dir = tmp_path / "engines" / "eng" / "v1.0.0" / "hw" / "models"
        bad = models_dir / "bad-pat"
        bad.mkdir(parents=True)
        bad.joinpath("bad.yaml").write_text(
            'model:\n  name: Bad\n  match:\n    - name_pattern: "(?i)["\n'  # 非法正则
            "scenarios:\n  standalone:\n    engine_config:\n      model: org/Bad\n    env: {}\n"
        )
        good = models_dir / "good"
        good.mkdir(parents=True)
        good.joinpath("good.yaml").write_text(
            'model:\n  name: Good\n  match:\n    - name_pattern: "(?i)good"\n'
            "scenarios:\n  standalone:\n    engine_config:\n      model: org/Good\n    env: {}\n"
        )
        # 非法 pattern 不应崩(旧行为是 re.error 崩整个扫描);合法 recipe 正常命中。
        data, path, pattern = load_model_config(tmp_path, "hw", "eng", "1.0.0", "GoodModel")
        assert data is not None and path.name == "good.yaml"

    def test_invalid_name_pattern_only_reports_gracefully(self, tmp_path):
        """F7 修复:仅有非法 pattern 且无命中 → 优雅 FileNotFoundError(含 invalid name_pattern),而非 re.error。"""
        models_dir = tmp_path / "engines" / "eng" / "v1.0.0" / "hw" / "models"
        bad = models_dir / "bad-pat"
        bad.mkdir(parents=True)
        bad.joinpath("bad.yaml").write_text(
            'model:\n  name: Bad\n  match:\n    - name_pattern: "(?i)["\n'
            "scenarios:\n  standalone:\n    engine_config:\n      model: org/Bad\n    env: {}\n"
        )
        with pytest.raises(FileNotFoundError, match="invalid name_pattern"):
            load_model_config(tmp_path, "hw", "eng", "1.0.0", "Whatever")

    def test_malformed_structures_skipped_no_crash(self, tmp_path):
        """结构非法的 recipe(data/model/match/rule 类型不对、空 pattern)逐一跳过,不崩,返回 no-match。"""
        models_dir = tmp_path / "engines" / "eng" / "v1.0.0" / "hw" / "models"
        cases = {
            "list-top": "[1, 2, 3]\n",                                    # data 非 dict
            "model-not-dict": "model:\n  - a\n  - b\n",                    # model 非 dict
            "match-not-list": "model:\n  match:\n    a: 1\n",              # match 非 list
            "rule-not-dict": "model:\n  match:\n    - justastring\n",      # rule 非 dict
            "empty-pattern": 'model:\n  match:\n    - name_pattern: ""\n',  # 空 pattern
        }
        for name, content in cases.items():
            d = models_dir / name
            d.mkdir(parents=True)
            d.joinpath(f"{name}.yaml").write_text(content)
        data, path, pattern = load_model_config(tmp_path, "hw", "eng", "1.0.0", "Anything")
        assert data is None and path is None and pattern == ""
