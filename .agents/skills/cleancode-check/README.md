# CleanCode Check

## 概述

本技能通过本地规则引擎检查代码是否符合 CleanCode 编码规范，输出结构化检查报告。支持多种编程语言，覆盖安全、逻辑、设计、格式四大类检查维度。

## 配合使用

**推荐与 `codehub-diff-cli` 配合使用**：先通过 `codehub-diff-cli` 获取 MR 的代码变更 Diff，再交给本技能对变更代码进行 CleanCode 规范检查，实现 MR 合入前的自动化代码质量门禁。

典型工作流：
```
codehub-diff-cli 获取 MR Diff
        │
        ▼
  提取变更文件列表 & 代码片段
        │
        ▼
  cleancode-check 逐文件/逐语言检查
        │
        ▼
  输出 CleanCode 检查报告
```

## 工作原理

### 核心流程

```
用户输入代码（文件 / Diff / 代码片段）
        │
        ▼
Step 1: 识别可疑点
  ├── 安全类（硬编码密钥、SQL 注入、命令注入等）
  ├── 逻辑类（不可达代码、异常吞没、资源未释放等）
  ├── 设计类（函数过长、魔法数字、嵌套过深等）
  └── 格式类（命名规范、注释缺失、行过长等）
        │
        ▼
Step 2: 获取对应语言的规则列表
  └── python3 scripts/find_code_rules.py --lang <语言>
        │
        ▼
Step 3: 可疑点与规则匹配
  ├── 直接匹配（关键词对应）
  ├── 语义匹配（规则描述覆盖可疑点场景）
  └── 分类映射（安全→G.EDV/ G.DSP，逻辑→G.CTL/ G.ERR 等）
        │
        ▼
Step 4: 获取匹配规则详情并分析
  ├── 确认匹配度（完全/部分/弱匹配）
  ├── 评估严重性（规则级别 vs 实际风险）
  ├── 检查修复建议
  └── 排除误报
        │
        ▼
Step 5: 输出结构化报告
  ├── 有确认问题 → 详细问题列表 + 修复建议
  ├── 无问题 → 简洁结论
  └── 可疑点全部排除 → 排除原因说明
```

### 规则引擎

规则存储在 `scripts/rules/*.json` 中（每种语言一个 JSON 文件），每条规则包含：

| 字段 | 说明 |
|------|------|
| `rule_id` | 规则唯一 ID |
| `code` | 规则编码（如 `G.CLS.01`） |
| `title` | 规则标题 |
| `language` | 适用语言 |
| `level` | 严重级别（致命/严重/一般/提示） |
| `description` | 规则详细描述 |
| `fix_suggestion` | 修复建议 |

规则按类别前缀组织：

| 类别前缀 | 含义 | 示例 |
|----------|------|------|
| `G.VAR.*` | 变量相关 | 硬编码、命名规范 |
| `G.CLS.*` | 类设计 | 继承、方法签名 |
| `G.CMT.*` | 注释规范 | 文档字符串、TODO/FIXME |
| `G.CTL.*` | 控制流 | 循环、条件、返回值 |
| `G.DSP.*` | 数据安全 | 加密、随机数 |
| `G.EDV.*` | 安全开发 | SQL 注入、命令注入 |
| `G.ERR.*` | 异常处理 | 异常捕获、抛出 |
| `G.EXP.*` | 表达式 | lambda、推导式 |
| `G.FIO.*` | 文件 IO | 文件权限、路径 |
| `G.FMT.*` | 代码格式 | 缩进、行宽 |

## 支持的编程语言

`Python`, `Java`, `Go`, `C`, `C++`, `JavaScript`, `TypeScript`, `Rust`, `Lua`, `Shell`

## 使用方式

### 基本用法

```bash
# 获取某语言所有规则列表
python3 scripts/find_code_rules.py --lang Python

# 获取单条规则详情
python3 scripts/find_code_rules.py --rule-id 870

# 按规则编码过滤
python3 scripts/find_code_rules.py --code G.VAR.S.097

# 按严重级别过滤
python3 scripts/find_code_rules.py --lang Python --level 严重
```

### 配合 codehub-diff-cli 使用

```bash
# 1. 获取 MR Diff
python3 scripts/get-diff.py --url "https://codehub.xfusion.com/path/project/merge_requests/42"

# 2. 将 Diff 中的代码片段交给 cleancode-check 检查
#    （直接粘贴 Diff 内容或指定变更文件路径）
```

## 输出报告格式

### 发现问题的报告

```markdown
# CleanCode 检查报告

## 检查概要
- **检查语言**: Python
- **检查文件**: file1.py, file2.py
- **确认问题数**: K

## 问题统计
| 级别 | 数量 |
|------|------|
| 严重 | 2 |
| 一般 | 1 |

## 详细问题
### 问题 1: 硬编码密码
- **文件**: xxx.py
- **行号**: L42
- **规则ID**: 870 | **规则编码**: G.VAR.S.097
- **级别**: 一般
- **问题描述**: ...
- **可疑代码**: (代码片段)
- **匹配依据**: ...
- **修复建议**: ...
- **匹配度**: 完全匹配
```

### 未发现问题的报告

```markdown
# CleanCode 检查报告

## 检查概要
- **检查语言**: Python
- **检查文件**: file1.py
- **确认问题数**: 0

## 结论
未发现 CleanCode 问题。
```

### 严格原则

- **有则报，无则不报** — 零噪音，不输出通过项
- **问题按严重级别排序** — 致命 > 严重 > 一般 > 提示
- **同一文件相邻问题合并** — 避免重复
- **可疑代码只展示问题行** — 不展示完整函数/文件

## 文件结构

```
cleancode-check/
├── SKILL.md         # 技能定义（触发描述、完整工作流）
├── README.md        # 本文件（原理与用法详解）
└── scripts/
    ├── find_code_rules.py  # 规则查询脚本
    └── rules/
        ├── Python.json
        ├── Java.json
        ├── Go.json
        └── ...
```
