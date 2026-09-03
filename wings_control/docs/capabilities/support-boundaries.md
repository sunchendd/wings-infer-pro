# 支持边界

本表说明当前代码和维护支持的范围。它不表示所有模型、硬件和拓扑组合都已完成产品准入。存在模型配置、dry-run 成功或脚本生成成功，也不等于对应镜像、硬件和拓扑已通过运行验收。

| 能力 | 是否支持 | 范围与限制 |
| --- | --- | --- |
| vLLM / vLLM-Ascend | 是 | 支持版本化 recipe 的解析、脚本生成、standalone 和普通 multi-node。具体模型、版本、硬件和拓扑以 recipe 和验收记录为准。 |
| SGLang v0.5.10 | 是 | 支持 standalone 和固定双 Pod multi-node。要求显式 v0.5.10；不支持 DPA 和 PD。Wings Accel 开关会告警后忽略。 |
| PD 分离 | 是 | 支持输入解析、exact recipe、`ProcessPlan`、脚本和 audit。普通 `derived_1p1d` 只在 recipe 明确指定时根据 `--device-count` 派生；大 EP 由 MaaS 一次下发六个 topology 字段。具体组合仍需运行验收。 |
| `--config-file`：standalone / multi-node | 是 | 自定义 JSON 是参数主源，不读取模型 recipe；仍会解析配置根、硬件和引擎版本，并执行别名归一、黑名单、CLI 和运行时派生规则。它不是任意参数的原样透传。 |
| `--config-file`：PD | 是 | 仅支持 vLLM / vLLM-Ascend。并行度优先取自定义 JSON，缺失时使用 MaaS PD 字段；不具备 exact recipe 的完整闭合保证，Accel 开关当前会被忽略。 |
| Wings Accel | 是 | 通过结构化接口合并引擎参数、环境变量和 audit。共享卷文件、安装包和启动前命令受专门的接口和安全边界约束。 |
| MindIE | 是 | 支持 recipe standalone 和固定双节点路径，包括配置、启动计划、health/progress；不支持 PD。`--config-file` 未接入完整特殊引擎生命周期，不属于支持路径。 |

## dry-run 的边界

dry-run 只做启动前推演。它与正常启动使用相同的输入、配置选择和参数计算规则，但在生成产物前结束。

正常启动会写入启动脚本、审计文件和所需的共享卷文件。随后，engine 容器按启动脚本安装依赖、执行启动前命令并启动 engine。使用 `--dry-run` 时，Wings Control 只计算正常启动将使用的参数，不写这些文件，也不触发后续安装和 engine 启动。

可用 dry-run 在真正启动前检查模型配置是否命中、参数是否按预期合并、引擎命令是否合理，以及多机或 PD 的进程安排是否符合预期。

它会验证配置能否解析，并打印本次准备使用的环境变量、engine 命令和节点或 PD 进程预览。它不生成 `start_command.sh`、`repro.sh`、`audit.json`、`wings_start.log` 或 Accel 文件，也不安装依赖或执行启动前命令。

因此，dry-run 成功只能说明该输入能通过当前解析和渲染路径，不能证明：

- 目标镜像已具备所需依赖；
- engine 命令在目标硬件上可以启动；
- 多机网络、端口、rank 或 PD placement 正确；
- Accel 安装、共享卷文件和启动前命令可以执行；
- 性能、稳定性或生产可用性已经验收。

## 使用本表

- 单个模型通过验收，不自动推广到同一模型族、硬件、引擎或拓扑的其他组合。
- 新增能力前，先更新本表并补充对应配置、测试和运行验收记录。
- 代码行为与本表不一致时，不要直接扩大支持声明；先确认是缺陷、未完成能力，还是尚未验收的组合。
