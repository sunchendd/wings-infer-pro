# 配置、产物与日志

本文说明配置如何定位、正常启动会留下哪些文件，以及各类日志该怎么使用。字段来源和配置合并规则见[TP/DP 并行策略](../policies/parallelism-and-resolution.md)。

## 配置定位

配置资产目录由配置责任方维护，本文件不重复列出。配置根依次取自 `--config-root`、`WINGS_CTL_CONFIG_ROOT`；在开发安装环境中，最后才尝试仓库下的 `config/`。`--config-file` 是自定义 JSON，不是 recipe YAML；其中的 `params` 和 `env` 必须是对象。

## 输出文件

`start_command.sh`、`repro.sh` 和 `audit.json` 都写入 `output_dir`。该目录依次取自显式 `--output-dir`、已存在的 `/shared-volume` 和当前工作目录。

| 文件 | 用途 | 何时生成 |
| --- | --- | --- |
| `start_command.sh` | 当前 Pod 实际执行的启动脚本，包含环境变量、必要前置步骤和 engine 命令。运行上下文不完整时，可能是退出码 3 的占位脚本。 | 非 dry-run 启动 |
| `repro.sh` | 用于复现或核对启动参数。执行前先查看内容，它可能设置环境变量、执行启动前命令或清理 KV 磁盘文件。 | 非 dry-run 启动 |
| `audit.json` | 本次解析的完整记录，包括最终参数、参数来源、配置文件、版本判断和进程/节点计划。追查参数来源时以它为准。 | 非 dry-run 启动 |

`--dry-run` 只打印解析后的环境变量、命令和进程预览，不生成上述文件、`wings_start.log`、`advanced_features.json` 或 Accel 文件。不过 CLI 初始化时仍可能写入 `wings_control.log`。

## 日志

`wings_start.log` 与 `wings_control.log` 都由 control 进程写入，但记录的内容不同。二者都不能替代 `audit.json`，也都不是 engine 的 stdout/stderr。

| 文件或目录 | 用途与位置 |
| --- | --- |
| `wings_start.log` | 每次正常启动时都会追加一段 `[STARTUP]` 摘要，记录硬件、引擎版本、模型、配置和产物上下文。默认路径是 `/var/log/wings/wings_start.log`，可用 `WINGS_START_LOG` 覆盖；默认位置不可写时回退到 `output_dir/wings_start.log`。不轮转，dry-run 不写。 |
| `wings_control.log` | wings-control、proxy 和 health 的持续 Python 日志，例如后端连接、健康检查、502 和重启。默认路径是 `/var/log/wings/wings_control.log`，只能用 `LOG_FILE_PATH` 覆盖；无法创建时关闭文件日志，不回退到 `output_dir`。使用轮转，dry-run 也可能产生。 |
| `prometheus_multiproc/` | 多进程 Prometheus 指标目录。启动 proxy/health 前重建，proxy worker 写入其中的指标文件。 |
| `engine-full.log` | 仅 standalone 或多 Pod 的 master/head engine 容器生成。启动脚本在该 Pod 中用 `tee` 保存完整 stdout/stderr；worker Pod 不生成此文件。 |
| `engine.log` | 仅 standalone 或 master/head 生成。它从完整日志中过滤部分健康检查和调度噪声，并供 log analyzer 跟踪；worker Pod 不生成此文件。 |

`engine-full.log` 和 `engine.log` 的写入方是 master/head 启动脚本中的 shell `tee`。log analyzer 只读取 `engine.log` 用于进度分析，并写入 `progress.jsonl`；它不直接写这两份 engine 日志。worker Pod 不启动 log analyzer，也没有这两份本地 engine 日志。

排障时，先用 `wings_start.log` 确认生成上下文；参数为何生效看 `audit.json`；master/head 的引擎异常优先看 `engine-full.log`；worker 引擎异常直接使用 `kubectl logs -c engine <worker-pod>`，重启后的上一实例使用 `--previous`。proxy、health 或 backend 连通性问题看 `wings_control.log`。

## Accel 文件

非 dry-run 的正常启动会尝试写入 `/shared-volume/advanced_features.json`。PD 的 `ProcessPlan` 和没有运行时上下文的多机占位流程不写该文件；已注入运行时上下文的多机节点仍会尝试写入。文件记录加速状态，health 接口会读取；可用 `SHARED_VOLUME_PATH` 或 `ADVANCED_FEATURES_FILE` 调整路径。写入失败只告警，不会阻止启动脚本生成。

Wings Accel 还可能返回配置文件或辅助脚本。它们必须写入共享卷；路径越界、写入失败或无法设置权限都会直接失败。详细规则见[Wings Accel 接口](wings-accel-interface.md)。

这些文件、启动脚本和 audit 不构成一个整体事务。后续步骤失败时，目录中可能已经留下部分新文件或旧文件。

## 兼容要求

文件名、命令参数顺序、脚本行为、`audit.json` 字段和列表顺序、告警/错误类别及退出码都可能被外部系统依赖。修改前必须评估兼容性、更新文档并补充回归测试。
