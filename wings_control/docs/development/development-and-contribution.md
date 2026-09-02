# 开发、验证与提交要求

本文说明修改 wings-control 时应遵守的开发、验证和提交规则。接口和运行行为的细节，请按任务查阅对应文档。

## 修改前

- 先看改动是否会影响 CLI、环境变量、YAML、参数来源、`audit.json`、命令顺序、脚本、日志、错误类型、退出码或输出文件名。这些内容可能已被调用方或运维流程依赖。
- 一个提交只解决一类问题，便于评审和回退。不要把行为修改、全仓格式化、重命名和无关清理混在一起。
- `src/wings_ctl/` 是重构主流程。legacy 生产实现、配置资产和 Wings Accel 分别由不同责任方维护；没有明确授权时，不要顺带修改。
- 配置必须递归合并，并记录每个最终值的来源。合并完成后，不能绕开 trace 悄悄改参数。
- 公共解析和编排层不要按引擎名添加控制分支。引擎差异放在已有命令规格、参数映射或特殊引擎边界中处理。
- 用户会看到的日志、CLI 输出、脚本消息和错误必须使用英文。不要记录密钥或完整敏感环境。
- 修改输入处理、YAML、路径、shell 渲染、原始 `pre_serve` 或 escape hatch 前，需要独立人工安全评审。

## 代码要求

- 新实现放在 `src/wings_ctl/`。没有明确任务时，不修改 legacy 生产路径、`config/` 或 `src/wings_accel/`。
- 配置必须递归深合并，并通过 trace 保存最终值、来源层、来源文件、来源路径和覆盖历史。列表整体替换。
- `default_model` 与匹配到的模型 scenario 互斥。YAML 错误、歧义匹配、必填字段缺失等配置错误不能伪装成 fallback。
- runtime `supported_params` 校验只告警，不删除参数，也不阻止启动。
- `--device-count` 是当前 Pod 内一个 engine 实例可用的 GPU 数。不要新增通用动态并行规划器；现有规则见[TP/DP 并行策略](../policies/parallelism-and-resolution.md)。
- engine 命令在最终渲染前保持 `list[str]`。不得对不可信输入使用 `shell=True`、`bash -c`、反引号、命令替换、`eval`、`exec` 或手工拼接 shell 字符串。
- 同构数据映射使用普通 dict 表；少量、封闭的数据形状差异可用普通 `if/elif`。不要无必要引入 plugin、registry、DSL、反射或隐式注册。
- 公共接口和不明显的业务 helper 使用有用的中文 docstring。注释解释原因、安全约束、副作用、数据形状或维护边界，不逐句翻译代码。

## 测试与产物检查

新增行为必须在 `wings_control/tests/` 中补测试：

- 单个函数、解析规则、合并规则、异常和边界条件放 `tests/unit/`。
- 多模块协作、CLI、配置资产、生成脚本、audit 或完整启动流程放 `tests/integration/`。
- Wings Accel 包自身的行为放 `tests/wings_accel/`。
- 同时改变内部判定和最终产物时，两类测试都要补：单元测试保护判定规则，集成测试保护 argv、脚本、audit、日志或退出码。
- 修复缺陷时，条件允许就补一条修复前失败、修复后通过的回归测试。纯可读性修改必须保持行为和生成产物不变。

涉及输出或兼容行为时，除 pytest 外，还要核对受影响的命令行参数、`start_command.sh`、`repro.sh`、`audit.json`、`wings_start.log`、告警、错误和退出码。

不要为了通过测试而修改 golden 或期望值，掩盖生产回归。更新 golden 前，先确认输入、预期产物和兼容原因。

## 本地验证

运行门禁前先安装开发依赖：

```bash
cd wings_control
pip install -e '.[dev]'
```

这会安装项目依赖，包括 pytest 和 Ruff。缺少 pytest 或 Ruff 时，`check.sh` 会失败；未执行检查或依赖缺失，都不能写成门禁通过。

```bash
cd wings_control
bash scripts/check.sh
```

命令最后出现以下内容，表示基础门禁通过：

```text
================  check OK  ================
```

`check.sh` 会运行 Ruff lint、重构主流程中的字面 `engine ==` 检查和核心 pytest。它不能代替真机验收、性能稳定性验证或生产资格确认。

`test_wings_start_sh` 和 `ruff format --check` 是软检查。即使它们失败，脚本仍可能输出 `check OK`。因此，不能把 `check OK` 写成“所有检查均已通过”。

## 提交前

```bash
git diff --stat
git diff
git status --short --branch
```

确认没有无关格式变动、生成文件、归档、本地路径、凭据、配置资产误改或越过责任边界的修改。公共接口、支持边界、策略或运维行为变更时，同步更新对应文档。

`git commit` 只创建本地提交，`git push` 才会修改远端。创建或合并 MR 是单独的服务端操作。没有执行过对应命令、没有拿到结果时，不要把编辑、提交、推送和合并混写成同一种状态。
