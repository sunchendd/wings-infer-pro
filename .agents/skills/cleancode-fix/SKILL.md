---
name: cleancode-fix
description: 根据xfusion CleanCode系统的MR检视结果自动修复代码。当用户提供来自cleancode-issue.xfusion.com的MR扫描地址（如https://cleancode-issue.xfusion.com/#/check?versionId=xxx&mrid=xxx）、提及修复代码检视问题或需要处理xfusion平台的代码检视结果时，使用此skill。支持根据编程语言自动查找对应的编码规则文件进行修复。
---

# CleanCode代码修复Skill

根据xfusion CleanCode MR检视结果修复代码问题，支持多语言编码规则自动查找和引用。

## 工作流程

0. **自动确保规则库已解压**：运行`python scripts/cleancode_api.py`时会自动检查，未解压才解压，已解压则跳过
1. 从MR扫描地址中提取`versionId`和`mrId`
2. 使用本skill `scripts/`目录中的`cleancode_api.py`获取检视结果
3. **检测编程语言**：从问题数据中的`ext06`字段或文件扩展名识别编程语言
4. **查找编码规则文件**：根据语言和规则ID在`references/`目录中查找对应的规则文件
5. **参考规则文件修复**：阅读规则文件中的正确示例、错误示例和修复建议
6. 应用修复并报告修改内容

## 编程语言检测

从以下来源检测编程语言：
- **优先级1**：问题数据中的`ext06`字段（语言标识）
- **优先级2**：文件扩展名（`.py`→Python, `.java`→Java, `.cpp`→C++等）

支持的语言映射：
- `python` / `py` → `coding_rules_python`
- `java` → `coding_rules_java`
- `cpp` / `c++` → `coding_rules_c++`
- `c` → `coding_rules_c`
- `go` → `coding_rules_go`
- `js` / `javascript` → `coding_rules_javascript`
- `lua` → `coding_rules_lua`
- `rust` / `rs` → `coding_rules_rust`
- `shell` / `sh` / `bash` → `coding_rules_shell`
- `ts` / `typescript` → `coding_rules_typescript`

## 编码规则文件查找

规则文件默认以压缩包形式存放在本skill根目录：`references.zip`。

首次使用或`references/`目录不存在时，运行`python scripts/cleancode_api.py`会自动触发按需解压。

如需单独执行解压检查（可选），可运行：

```bash
python scripts/ensure_references.py
```

该脚本会自动执行以下逻辑：
- 如果`references/`已存在且包含规则文件：跳过解压
- 如果未解压且存在`references.zip`：自动解压到skill根目录

解压后规则文件位于`references/`目录下，按语言组织：

```
references/
├── coding_rules_python/
│   └── rules/
│       ├── G.FMT.02 行宽不超过120个字符.md
│       ├── G.CLS.01 如果子类和父类中都有__init__方法.md
│       └── ...
├── coding_rules_java/
│   └── rules/
│       └── ...
└── ...
```

**查找规则文件的步骤：**

1. 直接使用`ruleDesc`字段作为规则文档的文件名
2. 构建规则文件路径：`references/{language_dir}/rules/{ruleDesc}.md`
3. 例如：`ruleDesc: "G.CNS.01 魔鬼数字检测"` → `references/coding_rules_lua/rules/G.CNS.01 魔鬼数字检测.md`
4. 如果找不到精确匹配，才尝试模糊搜索（部分匹配规则ID或描述）

**规则文件结构：**
- 规则ID
- 问题级别（严重/一般）
- 描述
- 正确示例
- 错误示例
- 修复建议

## API使用

**重要说明：** `cleancode_api.py`脚本位于本skill的`scripts/`目录中。始终使用该位置的脚本 - 不要在其他位置搜索。

**自动解压说明：** 该脚本启动时会自动调用按需解压逻辑：
- 如果`references/`已存在且包含规则文件：跳过解压
- 如果未解压且存在`references.zip`：自动解压到skill根目录

**配置要求：** 使用前请填写cleancode-fix skill路径下`config.json`文件中的`username`和`password`字段，用于访问CleanCode API。

```bash
python scripts/cleancode_api.py "MR_URL" [--config CONFIG_PATH] [--output OUTPUT_FILE]
```

参数说明：
- `MR_URL`: MR扫描地址（例如：https://cleancode-issue.xfusion.com/#/check?versionId=3990646&mrid=154565_384875）
- `--config`: config.json文件路径（可选，默认为config.json）
- `--output`: 输出JSON文件路径（可选）

示例：
```bash
python scripts/cleancode_api.py "https://cleancode-issue.xfusion.com/#/check?versionId=3990646&mrid=154565_384875" --output results.json
```

**注意：** `results.json`是临时输出文件，修复完成后可以手动删除。

结果包含三个类别：`general`（通用）、`security`（安全）、`other`（其他）。

每个问题包含以下字段：
- `fileName`：文件名
- `lineNo`：行号
- `ruleId`：规则ID
- `ruleDesc`：规则描述
- `scanSrc`：扫描源代码片段
- `scanErrorDesc`：扫描错误描述
- `ext05`：规则标识（如G.FMT.05-03）
- `ext06`：编程语言

## 修复问题

**重要策略：按行号倒序修复**

当一个文件存在多个问题时，必须按行号从大到小的顺序修复。这样可以避免因为修复靠前的行导致后面的问题行号发生偏移。

**修复流程：**

1. **按文件分组问题**：将所有问题按`fileName`分组

2. **每组内按行号倒序排序**：对每个文件的问题，按`lineNo`从大到小排序

3. **对每个问题依次修复**：

   a. **验证文件存在**：
      - 检查`fileName`文件是否存在且可读
      - 如果文件不存在，跳过该问题并记录

   b. **分层读取源代码（避免整文件加载）**：
      - 默认只读取`lineNo`附近窗口：`lineNo-30`到`lineNo+30`
      - 若上下文不足以判断，再扩展到`lineNo-80`到`lineNo+80`
      - 只有在确实需要跨函数/跨类分析时，才按符号边界补读（函数、类、常量块）
      - **禁止默认读取整文件**；仅在用户明确要求或问题必须全局分析时才允许

   c. **验证代码位置**：
      - 检查`lineNo`是否在文件范围内
      - 检查该行代码是否与问题描述匹配（基于`ruleDesc`和`scanErrorDesc`）
      - 如果代码已变更导致无法定位问题代码，跳过该问题并记录

   d. **检测语言**：从`ext06`或文件扩展名确定编程语言

   e. **查找规则文件**：
      - 直接使用`ruleDesc`字段作为规则文档的文件名
      - 构建规则文件路径：`references/{language_dir}/rules/{ruleDesc}.md`
      - 读取规则文件内容

   f. **理解问题**：
      - 阅读规则文件的描述、错误示例和修复建议
      - 结合`ruleDesc`和`scanErrorDesc`理解具体问题

   g. **检查是否已修复**：
      - 检查当前代码是否符合规则要求
      - 如果代码已经符合规则（已修复），跳过该问题并记录
      - 只有确认代码存在问题时才进行修复

   h. **应用修复**：
      - 参考规则文件中的正确示例
      - 应用修复建议
      - 保持代码结构和风格一致

**常见修复类型：**
- 魔法数字 → 定义命名常量
- 未使用的参数 → 删除或使用`_`前缀
- 安全问题 → 遵循安全最佳实践
- 格式问题 → 遵循语言规范
- 类设计问题 → 参考面向对象最佳实践
- 命名问题 → 修改类名、对象名、方法名、变量名等

**重命名修复的特殊处理：**

当修复涉及重命名（类名、对象名、方法名、变量名等）时：

1. **识别重命名类型**：
   - 类名（class name）
   - 对象名（object/instance name）
   - 方法名（method/function name）
   - 变量名（variable name）
   - 常量名（constant name）

2. **搜索依赖引用**：
   - 在当前文件中搜索所有对该名称的引用
   - 在同一模块/包的其他文件中搜索引用
   - 使用Grep工具搜索项目范围内的引用

3. **更新所有引用**：
   - 更新所有找到的引用点
   - 确保更新后的代码保持语义一致
   - 注意区分同名但不同作用域的标识符

4. **验证更新**：
   - 确保没有遗漏的引用
   - 确保没有误更新同名但不同含义的标识符
   - 如果无法确定是否需要更新，询问用户

## 报告

```
## 修复摘要
修复了Y个文件中的X个问题，跳过了Z个问题：

### 文件：filename.py
- [规则ID] [问题描述] - 行号:行号
  - 参考规则：references/coding_rules_python/rules/G.XX.XX.md
  - 修复内容：[简要描述]

### 跳过的问题
- [规则ID] [问题描述] - 文件:filename.py, 行号:行号
  - 跳过原因：[文件不存在 / 代码已变更无法定位 / 已修复 / 其他原因]
```

## 注意事项

- **脚本位置：** 始终使用本skill `scripts/`目录中的`cleancode_api.py`。不要搜索或使用其他位置的脚本。
- **规则文件位置：** 编码规则默认存放在`references.zip`。运行`python scripts/cleancode_api.py`时会自动按需解压。
- **按需解压原则：** 如果已解压则不重复解压，避免不必要的I/O开销。
- **文件变更处理：** 当文件已发生变更导致无法定位问题代码时，跳过该问题并记录跳过原因
- **已修复检查：** 修复前检查代码是否已经符合规则要求，如果已修复则跳过
- **重命名修复：** 修改类名、对象名、方法名、变量名等时，必须搜索并更新所有依赖引用，避免编译报错
- **大文件上下文优化：**
   - 优先使用“问题行窗口读取”，不要预先读取整个文件
   - 单次读取建议不超过200行；超过时分块读取并按需拼接
   - 同文件多问题时，优先复用已读取窗口，避免重复读取
   - 如果只需验证规则（如格式/命名/魔法数字），不要扩大到全文件
- 保持代码结构和风格
- 优雅地处理错误
- 如果找不到对应的规则文件，基于`ruleDesc`和`scanErrorDesc`进行修复
- 如果问题不清楚，请询问用户