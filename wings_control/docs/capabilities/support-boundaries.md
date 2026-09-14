# 支持边界

本表列出当前的维护范围和限制。“支持”表示功能已纳入维护范围，不表示所有模型、硬件和拓扑组合都已完成产品准入。仓库中存在模型配置、dry-run 成功或脚本生成成功，都不等于对应镜像、硬件和拓扑已通过运行验收。

`--config-file` 是自定义 JSON 配置入口，不是模型 recipe YAML。它可用于 standalone、multi-node 和 PD；各场景的限制见下表。

| 能力 | 是否支持 | 范围与限制 |
| --- | --- | --- |
| vLLM / vLLM-Ascend | 是 | 支持按版本解析 recipe，并可生成 standalone 和普通 multi-node 的启动脚本。具体模型、版本、硬件和拓扑以 recipe 和验收记录为准。未知硬件可使用引擎级、跨版本共享的 `_generic` 资产尽力生成 standalone 或固定双 Pod multi-node 命令；该回退不代表硬件已通过准入。 |
| SGLang v0.5.10 | 是 | 支持 standalone 和固定的双 Pod multi-node。要求显式 v0.5.10；不支持 DPA 和 PD。未知硬件可使用引擎级、跨版本共享的 `_generic` 资产尽力生成命令。Wings Accel 开关会告警后忽略。 |
| PD 分离 | 是 | 支持输入解析、精确 recipe 选择、`ProcessPlan`、脚本和 audit。普通 `derived_1p1d` 是旧 PD 兼容路径：MaaS 未启用大 EP 时不会下发六个 topology 字段。只有 recipe 明确声明该策略，才按 `--device-count` 派生 1P1D。大 EP 则由 MaaS 一次下发六个 topology 字段。具体组合仍需运行验收。 |
| `--config-file`：standalone / multi-node | 是 | 自定义 JSON 是主要参数来源，不读取模型 recipe；仍会解析配置根、硬件和引擎版本，并执行别名归一、黑名单、CLI 和运行时派生规则。它不是任意参数的原样透传。 |
| `--config-file`：PD | 是 | 仅支持 vLLM / vLLM-Ascend。并行度优先取自定义 JSON，缺失时使用 MaaS PD 字段；不保证像 recipe 一样完成精确的组合校验，Accel 开关当前会被忽略。 |
| Wings Accel | 是 | Day0 新增或修改模型配置时，必须同步提供匹配且已验证的 SmartAccel 资产；缺少资产或使用空占位资产不得合入。共享卷文件、安装包和启动前命令仍受专门的接口和安全边界约束。 |
| MindIE | 是 | 支持 recipe 驱动的 standalone 和固定双节点路径，包括配置、启动计划、health/progress；不支持 PD。`--config-file` 未接入完整特殊引擎生命周期，不属于支持路径。 |

未知硬件回退仅在普通 recipe 的 standalone/multi-node 路径生效，并在日志和 audit 中标记；PD、MindIE 以及缺少 `_generic/models/default_model.yaml` 文件的引擎仍直接失败。`_generic` 位于引擎根目录并明确跨引擎版本兼容。回退时 Wings Accel 被禁用。Wings Control 不阻止 engine 与 `hardware.device` 的不一致组合，而是输出包含两者的明确 warning；调用方负责保证所选 engine、镜像和设备兼容。通用 multi-node 资产采用现有固定双 Pod TP-across 形态，因此仍受现有卡数、二次幂和 placement 校验约束。

## dry-run 的边界

dry-run 只做启动前推演。它使用与正常启动相同的输入、配置选择和参数计算规则，但会在写入产物前停止。

正常启动会写入启动脚本、审计文件和所需的共享卷文件。随后，engine 容器按启动脚本安装依赖、执行启动前命令并启动 engine。使用 `--dry-run` 时，Wings Control 只计算正常启动将使用的参数，不写这些文件，也不触发后续安装和 engine 启动。

可在真正启动前用 dry-run 检查模型配置是否命中、参数是否按预期合并，以及多机或 PD 的进程安排是否符合预期。它会验证配置能否解析，并打印本次将使用的环境变量、engine 命令和节点或 PD 进程预览。它不生成 `start_command.sh`、`repro.sh`、`audit.json`、`wings_start.log` 或 Accel 文件，也不安装依赖或执行启动前命令。

因此，dry-run 成功只能说明该输入能通过当前解析和渲染路径，不能证明：

- 目标镜像已具备所需依赖；
- engine 命令在目标硬件上可以启动；
- 多机网络、端口、rank 或 PD placement 正确；
- Accel 安装、共享卷文件和启动前命令可以执行；
- 性能、稳定性或生产可用性已经验收。

## 使用本表

- 单个模型通过验收，不自动推广到同一模型族、硬件、引擎或拓扑的其他组合。
- 新增或调整支持声明时，同时更新本表，并补充对应配置、测试和运行验收记录。
- 代码行为与本表不一致时，不要直接扩大支持声明；先判断是缺陷、能力未完成，还是组合尚未验收。
