#!/usr/bin/env python3
# 规则导出脚本
# 读取 rules/ 目录下所有 JSON 文件，将每条规则格式化为字符串数组并输出。
# 格式: rule_id-lang-level-code-title
# 用法: python find_code_rules.py [--lang LANGUAGE] [--code CODE] [--level LEVEL] [--rule-id ID] [--output FILE]
# 规则目录默认相对于脚本所在目录: scripts/rules/

import json
import glob
import os
import argparse
import sys

# 规则目录默认相对于脚本所在目录
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_RULES_DIR = os.path.join(_SCRIPT_DIR, "rules")
_DEFAULT_RULES_DIR = os.path.abspath(_DEFAULT_RULES_DIR)


def load_rules(rules_dir: str) -> list[dict]:
    files = sorted(glob.glob(os.path.join(rules_dir, "*.json")))
    rules = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules.extend(data)
    return rules


def format_rule(rule: dict) -> str:
    rule_id = rule.get("rule_id", "")
    lang = rule.get("language", "")
    level = rule.get("level", "")
    code = rule.get("code", "")
    title = rule.get("title", "")
    return f"{rule_id}-{lang}-{level}-{code}-{title}"


def filter_rules(rules: list[dict], lang: str | None, code: str | None, level: str | None) -> list[dict]:
    result = []
    for rule in rules:
        if lang and rule.get("language", "").lower() != lang.lower():
            continue
        if code and rule.get("code", "").lower() != code.lower():
            continue
        if level and rule.get("level", "") != level:
            continue
        result.append(rule)
    return result


def find_rule_by_id(rules: list[dict], rule_id: str) -> dict | None:
    for rule in rules:
        if str(rule.get("rule_id", "")) == str(rule_id):
            return rule
    return None


def main():
    parser = argparse.ArgumentParser(description="导出规则为字符串数组")
    parser.add_argument("--rules-dir", default=_DEFAULT_RULES_DIR, help="规则文件目录（默认: 脚本所在目录的上一级/rules）")
    parser.add_argument("--lang", default=None, help="按语言过滤（如: C, Java, Python）")
    parser.add_argument("--code", default=None, help="按code过滤（如: G.ARR.01）")
    parser.add_argument("--level", default=None, help="按level过滤（如: 严重, 一般, 致命, 提示）")
    parser.add_argument("--rule-id", default=None, help="按rule_id查找单条规则的完整信息")
    parser.add_argument("--output", default=None, help="输出到文件（默认: 屏幕）")
    args = parser.parse_args()

    rules = load_rules(args.rules_dir)

    if args.rule_id is not None:
        rule = find_rule_by_id(rules, args.rule_id)
        if rule:
            output = json.dumps(rule, ensure_ascii=False, indent=2)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output)
                print(f"已导出 rule_id={args.rule_id} 的规则到 {args.output}")
            else:
                print(output)
        else:
            print(f"未找到 rule_id={args.rule_id} 的规则", file=sys.stderr)
            sys.exit(1)
    else:
        rules = filter_rules(rules, args.lang, args.code, args.level)
        strings = [format_rule(rule) for rule in rules]
        output = "[" + "\n".join(f'  "{s}"' for s in strings) + "\n]"

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"已导出 {len(strings)} 条规则到 {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
