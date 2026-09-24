# Wings Accel 接口说明

本文说明 Wings Accel 如何参与启动流程，以及维护时需要关注的边界。smart-accel YAML 的写法和加速方案选择由 Wings Accel 团队维护。文中的 engine 是实际运行推理服务的程序，例如 vLLM；Pod 是 Kubernetes 中承载该程序的运行单元。

## 一次启动如何经过 Accel

Wings Control 先读取模型配置、MaaS 输入和部署形态，再决定是否调用 Wings Accel。Accel 不负责拼接 `vllm serve` 命令，也不直接写启动脚本。它只返回结构化结果，Wings Control 负责把结果合入配置、写入文件并生成脚本。

```text
MaaS 开关 + 模型配置 / 部署上下文
    -> Wings Control 调用 Wings Accel
    -> AccelResult
    -> 合并 engine_config / env
    -> 正式启动时写文件、生成脚本
    -> engine 容器执行安装、启动前命令和 engine
```

是否启用只由 MaaS/CLI 下发的开关决定。YAML 中有 `smart_accel` 块，不等于加速已启用。

## Accel 返回什么

| 返回项 | 含义 | Wings Control 如何处理 |
| --- | --- | --- |
| `engine_config` | 要加到引擎命令中的参数 | 先合并到现有配置，再转成引擎实际接收的命令行参数。最终值可从 trace 中查到来源。 |
| `env` | 要导出的环境变量 | 在模型配置和 feature 已提供的环境变量基础上合并。变量同名时，Accel 替换旧值，最终脚本只导出一次；后续用户显式输入仍可覆盖 Accel。 |
| `packages` | 启动 engine 前可能需要额外安装的 Python 包 | 例如指定版本的 `lmcache`。Wings Control 将 `name:version` 格式的包名和版本交给 `/accel-volume/install.py` 安装。 |
| `generated_files` | 启动前要放到共享卷的文件内容 | 例如 LMCache 配置或启动 KV 服务的 shell 脚本。Accel 返回文件路径、内容、权限、在哪类 Pod 使用和来源；解析时不直接写盘。 |
| `pre_serve`、`pre_serve_master`、`pre_serve_client` | engine 命令执行前运行的 shell 命令 | 例如创建目录、启动 KV 后端服务或准备配置，分别在所有 Pod、master Pod、非 master Pod 执行。 |
| `scheme`、`diagnostics` | 选中的加速方案，以及未生效或降级的原因 | 写入 `audit.json` 中的 `wings_accel` 部分。 |

`engine_config` 和 `env` 会影响最终引擎命令和环境变量。`packages`、共享卷文件和 pre-serve 命令都属于启动前准备，不能当作引擎参数处理。

普通 recipe 的合并顺序为 recipe/feature、Accel、用户 CLI；自定义配置的顺序为 builtin/feature、Accel、`--config-file`、用户 CLI。`engine_config` 按嵌套字段合并。Accel 不得在 `build_argv()` 之后追加命令字符串，也不得绕开来源记录直接修改已解析配置。

## 正式启动时做什么

dry-run 会完成配置解析，并在终端打印本次准备使用的环境变量、引擎命令，以及节点或 PD 进程预览。它不写 `start_command.sh`、`audit.json` 或 Accel 文件，也不执行安装和启动前命令。

普通启动会先写入本次所需文件，再生成交给 engine 容器执行的启动脚本：

```text
写 advanced_features.json 和 Accel 返回的文件
    -> 生成 start_command.sh
       -> 导出环境变量
       -> 调用 /accel-volume/install.py 安装依赖
       -> 执行 all/master/client 三类启动前命令
       -> 清理 KV 磁盘缓存
       -> 执行特殊引擎自己的启动前动作
       -> 启动 engine
```

`advanced_features.json` 是 Wings Control 写入共享卷的加速状态文件，health 接口会读取它。Accel 返回的文件则可能是配置文件，也可能是辅助启动脚本。KV 指 engine 运行时使用的 Key-Value 缓存。

这些文件必须位于共享卷内。Wings Control 会原子替换单个文件并设置声明的权限；文件组、启动脚本和 audit 不是一个整体事务，后续步骤失败时，共享卷可能已经留下部分新文件。

pre-serve 是原样写入启动脚本的 shell 命令。当前只信任随包分发、且实际匹配到的 smart-accel YAML，不逐条审查命令内容。修改 smart-accel 资产或这部分渲染逻辑时，必须进行安全评审。

PD 是 Prefill/Decode 分离部署。PD 的 `ProcessPlan` 和 multi-node placeholder 不走上述通用写入流程，不要假定它们会执行相同的 Accel 动作。

## Mooncake standalone-store

vLLM 的 Mooncake standalone-store 仅支持 recipe `standalone` 与 DP-across-Pod `multi_node`。Kubernetes 负责启动
`mooncake_master`；每个 engine Pod 在 vLLM 前启动本机 `mooncake_client`，vLLM 通过
`MooncakeStoreConnector` 和 `127.0.0.1:50052` 访问它。该路径由
`ENABLE_DISTRIBUTED_KV_OFFLOAD` 单独控制，不能与本地 `ENABLE_KV_OFFLOAD` 同时开启。

启用时必须提供 `SERVING_CONFIG_ID`、`KV_PROTOCOL`、`KV_LOCAL_BUFFER_SIZE`，以及正的
`KV_MEM_OFFLOAD_SIZE` 和 `ENABLE_KV_MEM_OFFLOAD=true`。服务地址固定派生为
`mooncake-service-${SERVING_CONFIG_ID}:50051`，metadata URL 为
`http://mooncake-service-${SERVING_CONFIG_ID}:8080/metadata`。可选磁盘层继续使用
`ENABLE_KV_DISK_OFFLOAD`、`KV_DISK_OFFLOAD_PATH` 和 `KV_DISK_OFFLOAD_SIZE`。镜像必须预装与
vLLM connector 兼容的固定 Mooncake 版本及 `mooncake_client` 二进制。

Mooncake 的 `mooncake.json`、`start_mooncake_client.sh`、vLLM 环境变量和
`kv_transfer_config` 四个部件中，`kv_transfer_config` **必须**由匹配 SmartAccel YAML
提供——YAML 未声明时启动直接失败（不再脚本兜底）。其余三个部件缺失时逐项使用脚本兜底：
Wings Control 在正式产物阶段将包内 `src/wings_accel/distributed_offload/mooncake/` 复制到
`${SHARED_VOLUME_PATH}/mooncake/`。Mooncake client 所需环境变量集中定义在
`src/wings_accel/distributed_offload/mooncake/env.yaml`（带默认值）；Wings Control 解析期
加载该文件作默认值层，再由 MaaS 下发的同名 env 覆盖，渲染成 `export XXX=xxx` 形式写入同目录
`client.env`。engine Pod 在 wings-control 进程外执行，所以环境变量必须经 client.env
显式传递。`start_command.sh` 在 vLLM 前先
`source "${SHARED_VOLUME_PATH}/mooncake/client.env"`，再执行同目录的
`creat_mooncake_json.sh` 和 `start_mooncake_client.sh`。`engine_mooncake.env` 已由
env.yaml + client.env 取代并删除。脚本兜底使用 metadata `:10080`；其 Kubernetes master
必须与此端口保持一致。启动日志和 `audit.json` 的 `mooncake_component_sources` 会记录
四项实际来源。不开启 `ENABLE_DISTRIBUTED_KV_OFFLOAD` 时两条路线都不产生任何文件、环境或
启动前命令。

## 当前边界和错误

使用模型 recipe 的 PD 路径发现 Accel 已启用时会直接报错。`--config-file` 的 PD 路径目前会静默忽略这些开关，这是待修复的缺口。SGLang 首期不支持 Accel，收到相关开关后会告警并忽略。

以下问题应停止启动：package 格式错误、同一个规范化包名声明不同版本、KV offload 实际读取到原始 YAML `pre_serve` 字段，以及最终 pre-serve 命令的来源不在受信的包内资产中。

Wings Accel 模块不可用或普通调用失败时，Wings Control 会记录告警，再按未启用 Accel 继续。这不表示用户请求的加速已生效。YAML 匹配到多个候选，或多个返回文件使用同一路径时，当前会错误地降级；应改为抛出 `SmartAccelConfigurationError`，让启动直接失败。

安装依赖或执行 pre-serve 失败后，当前不会自动切回未加速参数。需要以无 Accel 方式启动时，应在启动前关闭 Accel，再重新解析和生成产物。

## 审计与分工

`audit.json` 已记录加速方案、诊断信息，以及 Accel 返回文件的路径、权限、适用范围、来源和内容 hash；尚未完整记录安装包、安装配置、pre-serve 命令和信任判断。

`src/wings_accel/` 和 smart-accel 资产由 Wings Accel 团队维护。Wings Control 负责调用接口、合并配置来源、校验共享卷路径、安排脚本顺序，并把必要信息写入 audit。修改返回字段、错误类型、文件写入时机或 pre-serve 语义时，两边都要评审。
