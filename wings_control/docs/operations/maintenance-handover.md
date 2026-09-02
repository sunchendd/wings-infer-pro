# 运行维护手册

本文用于部署检查、排障、验收和跨团队交接。确认参数来源时查看 `audit.json`；日志和生成文件说明见[配置、产物与日志](../contracts/configuration-artifacts-and-logs.md)。

## 启动前检查

1. 核对模型路径、硬件信息、引擎名和 `ENGINE_VERSION` 是否对应目标 recipe。
2. `--device-count` 填当前 Pod 分给该 engine 实例的 GPU 数，不填集群总卡数。
3. 多机部署时，核对 `MASTER_IP`、`RANK_IP`、`NODE_IPS` 的成员和顺序。PD 部署还要核对 `PD_ROLE` 和 topology 字段是否完整。
4. 先执行 dry-run，查看环境变量、引擎命令和进程预览。若需检查完整来源记录和脚本，在隔离输出目录执行正常写入模式。dry-run 成功只说明配置可以解析，不说明 engine 能启动。
5. 镜像、驱动、CANN/CUDA、硬件、模型量化、拓扑或 recipe 变更后，按[支持边界](../capabilities/support-boundaries.md)重新验收。

## 排障顺序

1. 先看 Pod state、Last State、退出码、events 和 `kubectl logs --previous`，判断是镜像、资源、节点还是应用问题。
2. 再看 `engine-full.log` 和容器 stdout/stderr，查 traceback、OOM、HCCL/CANN、依赖和参数错误。
3. 查看 `wings_start.log`，确认本次启动使用的硬件、引擎版本、模型和配置入口。
4. 用 `audit.json`、`start_command.sh` 和 `repro.sh` 核对最终环境变量、命令和覆盖来源。
5. 出现 502、health 或 proxy 问题时，再看 `wings_control.log`。它记录的是外部表现，根因仍可能在 engine 日志或 Pod 状态。
6. 多机或 PD 问题要收集每个相关 Pod 的 placement、audit 和 engine 日志，不能只看单个 Pod。

| 现象 | 首要证据 | 常见方向 |
| --- | --- | --- |
| 启动 traceback 或参数非法 | `engine-full.log` + `audit.json` | 配置、版本、模型路径或参数映射 |
| OOM、退出码 137、OOMKilled | Pod state/events + `engine-full.log` | 显存/内存、并行度、KV 配置或资源限制 |
| HCCL、通信超时、连接失败 | 所有相关 Pod 的完整引擎日志 | rank、IP、端口、设备通信或网络 |
| proxy 502 或 health 失败 | `wings_control.log` + engine 健康状态 | backend 监听、engine 崩溃或 proxy 配置 |
| PD 解析失败 | CLI stderr 和退出码 | `PD_ROLE`、六字段完整性、placement 或 recipe 策略 |
| Accel 安装或启动前命令失败 | `engine-full.log`、启动脚本和 audit | 加速资产、安装包、启动前命令、共享卷文件或版本匹配 |

## 验收与回退

- dry-run 只证明配置能够解析并生成预览，不证明脚本能执行、真机能启动或满足生产性能。
- 每次验收都记录代码修订、镜像和引擎版本、驱动、硬件、模型、量化、拓扑、关键配置和产物摘要。
- 升级前保留已验证组合的 `audit.json`、`repro.sh`、镜像版本和验收结果。升级失败时按这组信息回退。
- `emptyDir` 中的日志会在 Pod 删除后丢失。重大故障要在删除前导出日志、audit、脚本和 events。

## 责任边界

| 范围 | 默认责任 |
| --- | --- |
| `src/wings_ctl/`、CLI、解析、策略、渲染和 audit | wings-control 维护团队 |
| `config/` recipe 与版本化模型资产 | 配置/工具责任方 |
| `src/wings_accel/` 和 smart-accel 资产 | Wings Accel 责任方 |
| 镜像、驱动、CANN/CUDA、Kubernetes 网络与资源 | 平台或运行环境责任方 |
| MaaS 输入、跨 Pod 资源和全局拓扑预检 | MaaS/编排责任方 |

跨团队交接至少附复现命令或 `repro.sh`、`audit.json`、相关日志、Pod events、版本信息和已完成的排查结论。
