# Wings Infer Pro AI 开发准则

本文件适用于在本仓库中修改代码、测试、配置或正式文档的 AI 工具。这里只写长期适用的共性规则；具体接口和运行行为以 `wings_control/docs/` 中的对应文档为准。

## 开始前

- 主项目是 `wings_control/`，新实现放在 `wings_control/src/wings_ctl/`。
- 先阅读 `wings_control/README.md`、`wings_control/docs/README.md`，再阅读与任务相关的接口、能力、策略、运维或开发文档。
- 当前行为以代码、测试、实际命令输出和生成文件为准。发现文档与实现不一致时，先报告差异；未经确认，不要改变对外行为。
- 开始任务前查看相关文件和当前 Git 状态。不要覆盖、回退或清理用户和其他开发者的改动。
- 一个改动只解决一个问题。不要把功能变化、重命名、全仓格式化和无关清理放进同一 patch。

## 责任边界

- 不修改 legacy 生产实现，除非任务明确要求：`wings_control/config_loader.py`、`wings_control/wings_entry.py`、`wings_control/engine_manager.py`、`wings_control/model_utils.py`、`wings_control/version_util.py`、`wings_control/engines/*_adapter.py` 和现有 `wings_start.sh` 生产分支。
- `wings_control/config/` 由配置/工具责任方维护。`wings_control/src/wings_accel/` 和 smart-accel 资产由 Wings Accel 责任方维护。没有明确任务时，不要顺带重构、删除或合并这些范围的改动。
- `proxy/`、`rag_acc/`、`common/` 和 `wings_control.py` 不属于配置解析主流程。除非任务直接涉及这些目录，不要广泛清理。
- MindIE 支持 recipe standalone 和固定双节点路径，不支持 PD。`--config-file` 未接入完整特殊引擎生命周期，不是 MindIE 支持路径。
- `direct_vllm_serve` 尚未实现。不得在没有明确任务和独立安全评审时实现或放宽它的安全边界。

## 不可变规则

- 配置合并必须 trace-first。每个最终参数都要保留最终值、来源层、来源文件、来源路径和覆盖历史，并写入 `audit.json`。
- 嵌套配置递归深合并，列表整体替换。不得用浅层 `dict.update()` 替代深合并，也不得在合并后绕过 trace 修改最终参数。
- `default_model` 与匹配到的模型 scenario 互斥。无效配置、YAML 错误、歧义匹配和必填字段缺失不能伪装成 fallback。
- runtime `supported_params` 校验保持 warn-only：不删除参数，不阻止启动。
- `--device-count` 是当前 Pod 内一个 engine 实例可用的 GPU 数，不是集群总卡数。并行度规则见 `wings_control/docs/policies/parallelism-and-resolution.md`；不要新增通用动态并行规划器。
- 解析、策略、校验和渲染主流程不按引擎名称增加控制分支。引擎差异应放在已有参数映射、命令规格表或特殊引擎边界中处理。
- 同构数据映射使用普通 dict 表；少量、封闭的数据形状差异可用普通 `if/elif`。不要无必要引入 plugin、registry、DSL、反射或隐式注册。
- `param_mapping` 保持 Python dict 常量。禁止 `eval`、`exec` 和动态公式执行。

## 代码与安全

- CLI `main()` 只负责解析参数、构造请求、选择 dry-run 或正常执行，以及转换预期异常。环境回退、默认推导、拓扑判断和业务校验放入具名 helper。
- 公共接口和不明显的业务 helper 写有用的中文 docstring。注释说明原因、安全约束、副作用、数据形状或维护边界，不逐句复述代码，也不写 AI、审计编号或临时过程标签。
- 运行用户可见的日志、CLI 输出、脚本消息和错误必须使用英文。不要记录密钥、token、完整敏感环境或私有索引信息。
- CLI、环境变量、YAML、挂载文件、路径、模型名和版本都视为外部输入。使用安全 YAML loader，校验路径和数据形状，给出可定位的错误。
- engine 命令在最终渲染前保持 `list[str]`。不得对不可信输入使用 `shell=True`、`bash -c`、反引号、命令替换或手工拼接 shell 字符串。
- 当前 `--config-file` 的 `env` 是管理员自管的兼容入口，允许 `$(...)` 和反引号原样写入启动脚本。这个例外只适用于该 `env` 层。调用方及文件写入者必须具有命令执行权限，不能接收不可信租户内容。不得把例外扩展到其他输入路径；收紧或移除它也需要兼容性分析和独立安全评审。
- shell、环境变量渲染、原始 `pre_serve`、共享卷写入和 escape hatch 改动必须经过独立人工安全评审。
- 广泛捕获 `Exception` 只允许出现在明确的可选集成或进程边界，并保留原因：`raise ... from exc`。

## 兼容与文档

- 未经明确批准，不改变 CLI 选项和语义、环境变量和优先级、YAML schema、trace 层名和事件顺序、audit 字段、argv 顺序、脚本行为、日志、错误类型、退出码或输出文件名。
- 契约变化需要影响分析、文档更新和专门测试。不要通过修改测试或 golden 掩盖生产回归。
- 修改外部接口、支持边界、产物、策略或运维行为时，同步更新 `wings_control/docs/` 中唯一对应的精华文档。
- 大型设计稿、方案比较、历史评审和临时交接记录不进入正式 docs。它们应在公司项目目录或 issue 中维护。

## 测试与验证

- 新增行为必须在 `wings_control/tests/` 中补测试。
- 单个函数、解析规则、合并规则、异常和边界条件放 `tests/unit/`。
- 多模块协作、CLI、配置资产、生成脚本、audit 或完整启动流程放 `tests/integration/`。
- Wings Accel 包自身的行为放 `tests/wings_accel/`。
- 同时改变内部判定和最终产物时，单元测试与集成测试都要补：前者保护规则，后者保护 argv、脚本、audit、日志或退出码。
- 修复缺陷时，尽量补一条修复前失败、修复后通过的回归测试。纯可读性修改必须保持行为和产物不变。
- 有意义的代码改动前后，在可行时运行：

```bash
cd wings_control
pip install -e '.[dev]'
bash scripts/check.sh
```

- pytest 和 Ruff 是开发依赖。缺少它们导致 `check.sh` 失败时，如实报告依赖缺失和未完成验证，不要把它描述为通过。
- 完成前检查 `git diff --stat`、`git diff` 和 `git status --short --branch`。报告实际执行过的命令、真实结果、未验证项和剩余风险。

## Git 与协作

- 不提交、推送、创建 MR、删除分支或执行破坏性命令，除非用户明确要求。
- 不把“已编辑”“已提交”“已推送”“已合并”混为同一状态。只报告实际执行的操作和结果。
- 长任务在阶段切换前记录目标、改动、验证结果、未完成事项和下一步。新会话先读取本文件、当前 diff 和相关精华文档，不依赖旧对话记忆。
