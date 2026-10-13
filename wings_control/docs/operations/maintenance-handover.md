# 运行维护手册

本文用于部署检查、排障、验收和跨团队交接。确认参数来源时，以 `audit.json` 为准；日志和生成文件的说明见[配置、产物与日志](../contracts/configuration-artifacts-and-logs.md)。

## 启动前检查

1. 核对模型路径、硬件信息、引擎名和 `ENGINE_VERSION` 是否对应目标 recipe。
2. `--device-count` 填当前 Pod 分给该 engine 实例的 GPU 数，不填集群总卡数。
3. 多机部署时，核对 `MASTER_IP`、`RANK_IP`、`NODE_IPS` 的成员和顺序。PD 部署还要核对 `PD_ROLE`。大 EP 必须完整下发六个 topology 字段；旧 `derived_1p1d` 不下发这些字段，应使用匹配的 recipe 和单 Pod placement。
4. 先执行 dry-run，查看环境变量、引擎命令和进程预览。若需检查完整来源记录和脚本，在隔离输出目录执行正常写入模式。dry-run 成功只说明配置可以解析，不说明 engine 能启动。
5. 镜像、驱动、CANN/CUDA、硬件、模型量化、拓扑或 recipe 变更后，按[支持边界](../capabilities/support-boundaries.md)重新验收。

## 排障顺序

### GLM-5.3：vLLM 0.31.0 / RTX PRO 5000 72GB

配置使用 `config/v2/vllm/v0.31.0/rtx_pro_5000_72G/GLM-5.3/` 下的合一资产，
只保留 `GLM-5.3.yaml`，同时包含原生 FP8 基础参数和 SmartAccel；模型名使用 `GLM-5.3`。
审计结果应显示 `asset_source=v2`，模型来源指向对应合一 YAML。

- 单机 TP16 / EP，原生 FP8 权重、FP8 KV、`FLASHINFER_MLA_SPARSE_SM120`。
- 调度参数为 `max_model_len=auto`、`max_num_seqs=128`、`max_num_batched_tokens=8192`。
- 投机开关启用内置 MTP5；CPU 卸载开关启用 `LMCacheMPConnector` 和
  `lmcache:0.5.5+sm120.mp`，chunk 为1024，检索在 forward 前同步。
- 图模式为 `FULL_DECODE_ONLY`，主模型 prefill 使用 eager；捕获档位为
  `n` 与 `6*n` 的并集（n=1..16，最大96），超出档位的请求不能据此宣称进入图。
- 派生镜像须包含 FlashInfer SM120 包的 H4 prefill 与无效候选 gather 修复；
  仅安装社区 FlashInfer 0.7.0.post1 不能代表包含这些修复。
- 生成文件 `start_kv_serve.sh` 写入共享卷，启动脚本在 master 启动该服务。
  配置解析通过不代表整模型生成、长上下文并发或 LMCache 回读通过。

GLM-5.3-Flash 只保留 `GLM-5.3-Flash-fp8-kv-nvfp4.yaml`，模型名
`GLM-5.3-Flash` 精确匹配该文件，使用 FP8 权重、`nvfp4_ds_mla` KV、TP4/DP2/EP。

### 通用排障

vLLM 0.31.0 / RTX PRO 5000 72GB 派生镜像统一预装
`flashinfer-sm120:0.7.0.post1+sm120.1`。DeepSeek V4/V4.1、GLM-5.2、
GLM-5.3 和 GLM-5.3-Flash 的 v2 资产在投机、卸载及稀疏 scheme 中显式声明
该版本，特性开启时安装清单按包去重。关闭全部特性时不会从 scheme 收集包，
这些模型的基础稀疏 MLA 路径仍要求镜像预装该定制 wheel。
其他收编模型不因这些稀疏 MLA 补丁而增加 scheme 包依赖，继续使用统一派生镜像。

vLLM 0.31.0 / RTX PRO 5000 72GB 的 `Qwen3.5-397B-A17B-NVFP4`、
`MiniMax-M2.7-NVFP4`、`MiniMax-M2.5-NVFP4` 各只维护一份 `-nvfp4.yaml` 合一资产。
调用方使用完整模型变体名匹配 `profile.model`；该名称与 `model.variant_name` 一致，
默认权重指向对应 NVFP4 checkpoint。

1. 先看 Pod state、Last State、退出码、events 和 `kubectl logs --previous`，判断是镜像、资源、节点还是应用问题。
2. 在 standalone 或 master/head Pod 中查看 `engine.log`。worker Pod 不落盘 engine 日志，直接执行 `kubectl logs -c engine <worker-pod>`。两类日志都要检查 traceback、OOM、HCCL/CANN、依赖和参数错误。
3. 查看 `wings_start.log`，确认本次启动使用的硬件、引擎版本、模型和配置入口。
4. 用 `audit.json`、`start_command.sh` 和 `repro.sh` 核对最终环境变量、命令和覆盖来源。
5. 出现 502、health 或 proxy 问题时，再看 `wings_control.log`。它记录的是外部表现，根因仍可能在 engine 日志或 Pod 状态。
6. 多机或 PD 问题不能只看一个 Pod。应收集每个相关 Pod 的 placement、audit 和 engine 证据：master/head 收集 `engine.log`，worker 收集 `kubectl logs -c engine` 的输出。

| 现象 | 首要证据 | 常见方向 |
| --- | --- | --- |
| 启动 traceback 或参数非法 | master/head 的 `engine.log` 或 worker 的 `kubectl logs -c engine`，再结合 `audit.json` | 配置、版本、模型路径或参数映射 |
| OOM、退出码 137、OOMKilled | Pod state/events + master/head 的 `engine.log` 或 worker 的 `kubectl logs -c engine` | 显存/内存、并行度、KV 配置或资源限制 |
| HCCL、通信超时、连接失败 | master/head 的 `engine.log` + 所有 worker 的 `kubectl logs -c engine` | rank、IP、端口、设备通信或网络 |
| proxy 502 或 health 失败 | `wings_control.log` + engine 健康状态 | backend 监听、engine 崩溃或 proxy 配置 |
| PD 解析失败 | CLI stderr 和退出码 | `PD_ROLE`；大 EP 的六个 topology 字段与 placement；旧 `derived_1p1d` 的 recipe 与单 Pod placement |
| Accel 安装或启动前命令失败 | master/head 的 `engine.log` 或 worker 的 `kubectl logs -c engine`，再结合启动脚本和 audit | 加速资产、安装包、启动前命令、共享卷文件或版本匹配 |

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

跨团队交接至少提供复现命令或 `repro.sh`，并附上 `audit.json`、相关日志、Pod events、版本信息和已完成的排查结论。
