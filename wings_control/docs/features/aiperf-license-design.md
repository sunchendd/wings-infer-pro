# AIPerf License 详细设计

## 1. US需求

### 需求背景

AIPerf 当前没有 License 控制，无法进行商业化销售交付。

### 需求价值

License 用来向客户授权业务功能和容量。我司按合同签发与客户设备一一对应的数字签名 License 文件；设备上验签通过、序列号一致，才按授权信息激活相应功能，否则只能使用软件默认配置。以此打通交付、授权、管控、续期的闭环。

### 需求详情

在 Wings-control 启动流程中嵌入 License 运行时校验引擎，覆盖 ESN 获取、License 文件加载与验证、业务功能容量控制和 License 维护。

## 2. 需求设计

| 仓库              | 职责                                                         |
| ----------------- | ------------------------------------------------------------ |
| `wings-infer-pro` | 构建 License 镜像、调用 AdaptiveLM 验签、执行启动门禁、生成引擎启动脚本、随示例包分发宿主机查询工具（`ai_perf/license/`，交付归一为 License 模式后统一分发） |
| `AIPerf`          | compose 内置挂载证书与宿主机信息（`example/docker-compose-{gpu,npu}/`）、打包交付文件                               |

- 用户在宿主机 `/etc/aiperf/license/` 放置一个 License XML。
- wings-control 启动时验签一次，通过后才生成引擎启动脚本。
- License 校验只在启动时执行；已运行的引擎继续运行，不受后续证书变化影响。
- 证书目录挂载由 AIPerf Compose 完成；`license show` 查询工具由 wings-infer-pro 随 `AIPerf_SDK_example.zip` 分发；验签由 wings-control 完成。

`LRA4AIPERF01` 定义为本物理机上 wings-control 拉起实例合计可用的最大卡数：已用卡数 + 本次启动卡数 ≤ 授权卡数，超出即拒绝启动。已用卡数在启动前由 AIPerf control 入口实时统计，统计对象是本机运行中的 `aiperf-engine` 服务容器，统计方式见 §6，只统计 wings-control 拉起的实例。

## 3. AIPerf License 整体流程

1. 用户将唯一 License XML 放入宿主机 `/etc/aiperf/license/`。
2. AIPerf Compose（`example/docker-compose-{gpu,npu}/docker-compose.yaml` 已内置 License 挂载）把证书目录、SafeTime 状态、docker.sock 与宿主机 DMI 挂入 control 容器。
3. control 入口在拉起 wings-control 之前，统计本机已被占用的卡数。
4. wings-control 先删除共享卷中残留的旧 `start_command.sh`
5. `wings_ctl/license.py` 检查证书唯一性并调用验签工具。
6. 验签工具完成签名、产品、版本、容量键、有效期、设备序列号和时钟校验。
7. wings-control 校验“已用 + 本次 ≤ 授权卡数”，超出则拒绝启动。
8. 全部校验通过后写入 `start_command.sh`

## 4. 模块

| 仓库            | 模块                   | 职责                                                         |
| --------------- | ---------------------- | ------------------------------------------------------------ |
| wings-infer-pro | `wings_ctl/license.py` | License 门禁实现：证书唯一性检查、调用验签程序、卡数配额校验、删除旧启动脚本（仅 License 镜像携带） |
| wings-infer-pro | `wings_ctl/license_gate.py` | 门禁统一入口（所有镜像常驻）：`LicenseGate` 协议、Null 空实现、按构建声明选择的 fail-closed 工厂；pipeline 仅经 `get_license_gate()` 接触门禁 |
| wings-infer-pro | `license_sdk/`     | C 侧实现：验签程序 checker、编译脚本、产品 Key 构建期加密，基于 AdaptiveLM 静态库；`README.md` 为 License 资产地图 |
| wings-infer-pro | `Dockerfile.license`   | License 叠加层（FROM 普通镜像）：打入验签程序、AdaptiveLM 产物和产品 Key，产出独立 tag `wings-control:<版本>-license`，与非 License 版物理隔离 |
| wings-infer-pro | `ai_perf/license/`     | 宿主机工具 `aiperf.py`（模块化入口，命令注册于 `commands.py`）：`license show` 查询证书路径、证书内容和宿主机 ESN，配置见 `aiperf.json`；License 挂载已内置 example compose；随示例包统一分发 |
| AIPerf          | `deployment/`          | 部署样例与交付打包:Compose 挂载证书与宿主机信息、License 交付模式选择 |

AdaptiveLM 当前以 C 静态库交付，并依赖 C 结构和回调，因此 checker 保留为 C；Python 只负责流程编排。

## 5. 接口

AIPerf 查询接口：

```bash
./aiperf.py license show              # 证书路径 + 内容 + 宿主机 ESN
./aiperf.py license show --esn-only   # 仅 ESN(脚本友好)
```

按 `aiperf.json` 配置（默认 `/etc/aiperf/license/`，可用 `--config` 覆盖）读取唯一 XML，同时输出证书路径、原始内容和宿主机 ESN；签名校验由 wings-control 启动流程负责。

## 6. 校验规则

启动时做两组检查：先验证书，再算卡数。任何一项不过都不生成启动脚本。

证书检查由验签程序完成：

- 证书唯一：目录 `/etc/aiperf/license/` 里放且只放一份 XML 证书。多于一份时无法确定用哪份，列出文件名后拒绝启动。
- 核对项全部一致：验签核对签名、产品、版本、容量键、有效期和设备序列号，任何一项不符都拒绝启动，其中有效期已过按宽限期规则处理。
- 时钟正常：设备时钟被回拨会破坏有效期判断。例如今天把系统时间从 9 月 4 日改回去年 8 月 1 日，证书就会"还没到期"无限续命，SafeTime 机制记录上次运行时间，检测到回拨即拒绝启动。
- 验签结果为有效或在宽限期内，检查通过。

失败原因不进 audit.json（License 不做审计），只以一行结构化日志 `[AIPERF-LICENSE] code=… status=… license_file=… authorized=… used=… requested=… reason=… hint=…` 输出并抛错终止启动，可按 code 直接检索。状态取值包括 `missing`、`multiple_licenses`、`invalid`、`expired`、`checker_unavailable`、`device_count_unknown`、`capacity_exceeded` 等，与代码中 `wings_ctl/license.py` 的返回值一一对应，排查时按字段值对号。每个状态同时对应一个稳定数字错误码（`2001` missing、`2002` multiple_licenses、`2003` invalid、`2004` not_yet_valid、`2005` expired、`2006` clock_rolled_back、`2007` esn_unavailable、`2008` product_mismatch、`2009` node_mismatch、`2010` capacity_key_invalid、`2011` checker_unavailable、`2012` checker_timeout、`2013` checker_error、`2014` runtime_error、`2016` device_count_unknown、`2017` capacity_exceeded）。

卡数检查由 wings-control 完成。配额公式：

```
已用卡数+ 本次卡数≤ 证书授权卡数
```

- 本次卡数取自参数 `device_count`，即本 Pod 申请的卡数，按物理卡计。910C 这类单芯多卡的机型要按实际占用的物理卡数下发，例如 8 卡 910C 要传 16。该参数必填，缺失或不是正整数直接拒绝启动。强校验前移到 CLI 参数解析之后、任何依赖 `device_count` 的校验（尤其 TP-shrink 前置闸）之前执行（`cli.py` 经 `license_gate.validate_device_count_early`，仅 License 构建）：缺失或非正整数输出 `code=2016 status=device_count_unknown` 结构化日志并退出，避免 `device_count` 缺失落入 TP-shrink 逻辑后报出指向 hardware_family 的误导性错误。`--device-count` 传入非整数（如 `abc`）由 argparse 报 `invalid int value`，属用法错误、信息准确，保留 argparse 自身报错，不映射到 2016。相比旧版"缺省即跳过配额比较"，这是不兼容变化：AIPerf 部署由 control 入口自动下发，升级零改动；绕过入口直接调用 wings-control 的存量调用方，升级时必须显式传 `--device-count` 或设置 `DEVICE_COUNT` 环境变量，否则启动会被拦截。该强校验只在 License 构建（`LICENSE_ENABLED=True`）生效，普通构建维持 device_count 可选的现状。
- 已用卡数由 wings-control 容器内自查（`wings_ctl/license.py` 的 `count_used_devices`，随代码一起编译加密交付，不在任何明文脚本/环境变量中出现，无法用 env 伪造）：经只读挂载的 `/var/run/docker.sock` 枚举本机全部运行中的 `aiperf-engine` 服务容器（按 compose service label 过滤，只统计本框架拉起的实例），从容器配置读取可见卡号并计数。卡号来源依次为容器环境变量 `ASCEND_RT_VISIBLE_DEVICES`、`ASCEND_VISIBLE_DEVICES`、`NVIDIA_VISIBLE_DEVICES`，回退到直通设备 `/dev/davinci*` 计数或 GPU `DeviceRequests`；支持 `"10,12"` 与 `"0-3"` 两种写法，值为 `all` 时该 env 来源无法计数，回落到直穿设备/`DeviceRequests` 计数（"all" 即全部物理卡，若按 0 计多实例可借 env 规避配额）。自身 compose project 内正在等待授权的 engine 不计入已用——它的卡数就是本次 `device_count`，重复计入会导致首启部署恒超容；control 侧的自身容器 ID 从 `/proc/self/cgroup`（cgroup v1 `docker/<id>`、cgroup v2 `docker-<id>.scope`）解析，cgroup 私有 namespace 场景回退 `/proc/self/mountinfo`（Docker bind 的 hosts/hostname 源路径含 `containers/<id>/`），HOSTNAME 仅在为 12-64 位 hex（默认桥接网络的容器短 ID）时兜底——host 网络模式下容器继承宿主机名，不能当容器 ID 用；再以自身容器与 engine 容器携带相同的 `com.docker.compose.project` label 判同 project，识别失败（非容器环境、非 compose 部署、API 异常）时不剔除任何人，朝多计方向保守。sock 不可达（独立部署/未挂载）时按 0 处理，配额退化为单次校验。容器退出后即从 running 列表消失，计数即时归零。
- 已用卡数与本次卡数由 wings-control 传给验签工具，比较在验签工具二进制内部完成：`已用 + 本次 > 授权数` 时返回独立退出码，授权卡数取自证书容量键 `LRA4AIPERF01` 的值，比较逻辑不经过任何明文脚本或环境变量。

已用卡数要统计准确，有一个前提：

- control 服务要只读挂载 `/var/run/docker.sock`。缺了它时统计不到已用卡数，按 0 处理，配额退化成只比较本次申请卡数；同机并发启动时，统计与占卡之间存在时间窗，两个实例可能同时通过校验。同 project 内等待授权的 engine 已被剔除，整组 compose 重启不会误判超授权；但其他 project 的 engine 仍在统计范围内，跨 project 并发启动依然存在该时间窗。
- 风险边界与接受声明：`:ro` 只约束 bind 挂载自身，不约束 sock 上的 Docker API——持有 `/var/run/docker.sock` 的容器可以创建特权容器、挂载宿主机根文件系统，能力上等同宿主机 root。部署形态接受该风险的前提是 control 容器由管理员部署、与管理员同信任域，卡数统计逻辑随镜像编译加密交付；需要收敛的部署方应在 control 前置 docker socket proxy，只放行容器列表与检查接口，这属于部署侧可选加固，不是当前交付形态的组成部分。

多机与 PD 部署时配额按物理机隔离：每个 Pod 的 control 各管本机，检测基于 docker.sock 只能看到本机容器，各节点独立执行"已用 + 本次 ≤ 授权数"校验，互不感知、不跨机汇总。

ESN 即设备序列号，从 `/host-sys/class/dmi/id/board_serial` 读取，去掉首尾空白并转为大写。读取前验签工具会校验 DMI 防伪：对实际可能读到的每条 board_serial 路径（host bind 的 class 拼写、容器本地 class 拼写及其符号链接解析目标 devices 拼写），在 mountinfo 中取最长祖先挂载点，要求其 fstype 为 sysfs，任一路径不满足即拒绝。祖先方向是判定正确的关键——标准容器里 `/sys/class/dmi/id` 不是独立挂载点（被整树 `/sys` sysfs 挂载覆盖），要求"挂载点在目标之下"会恒落空；祖先方向上 `/` 必然存在，匹配必然终止。伪造的目录 bind（tmpfs/ext4）或单文件 bind 恰是更长的祖先匹配，fstype 不是 sysfs，同样被拦下。

## 7. 构建模式

- 分层构建：普通 `Dockerfile` 是单一事实源（零 License 逻辑）；`Dockerfile.license` `FROM` 普通镜像只叠加 License 差异（checker、license 模块、加密产品 Key、`/etc/aiperf/license` 挂载点），重复内容不双维护。`build_wings_control.sh` 先出基础 tag 再叠加出 `-license` tag；`build/build.sh` 保留两套镜像构建，由 `--enable-license` / `--disable-license` 选择（默认关闭产出无门禁镜像，仅供内部使用），门禁镜像与无门禁镜像 tag 物理隔离。
- example 与 License 部署归一：`example/docker-compose-{gpu,npu}/docker-compose.yaml` 直接内置证书目录/SafeTime 状态/docker.sock/DMI 四个只读挂载，单 compose 一条命令部署，不再维护独立的 license override 叠加文件。
- License 资产导航见 `wings_control/license_sdk/README.md`（代码/SDK/文档/测试/构建入口的文件地图）。
- AdaptiveLM 与 libboundscheck 第三方源码不入库，license 构建阶段从内部制品仓库按需下载；归档已存在时直接复用，也可预先拷入归档实现离线构建。license 构建机需能访问 `artifactrepo.wux-g.tools.xfusion.com`。
- 产品 Key 在构建期加密，镜像内只保存密文；解密仅发生在 checker 内存中。
- 交付归一为带 License 的一套：example 内置 License 挂载、`IMAGE_CONTROL` 指向 `-license` 后缀 tag、宿主机查询工具随示例包分发；`--ai_perf` 打包须与 `--enable-license` 组合，无门禁镜像不进入 AIPerf 交付。

## 8. 用例设计

申请测试机器ESN对应的lincense，测试证书授权 6 卡：

| #  | 场景                         | 结果                                                        |
| -- | ---------------------------- | ----------------------------------------------------------- |
| 1  | 单卡启动，证书有效           | `license.status=valid`，引擎拉起，推理成功                  |
| 2  | 证书目录为空时启动           | `missing: no license file (*.xml)`，拒绝启动                |
| 3  | 单次申请 8 卡，超过授权 6 卡 | `capacity_exceeded: requested 8 ... authorized 6`，拒绝启动 |
| 4  | 同机第二个实例申请 4 卡      | 检测到已用 1 卡，合计 5 卡未超授权，放行                    |
| 5  | 同机第三个实例申请 4 卡      | 检测到已用 5 卡，合计 9 卡超授权，拒绝                      |
| 6  | `aiperf.py license show`     | 输出证书路径、证书内容、宿主机 ESN                          |
| 7  | 一次性 `up -d` 整组启动（engine 与 control 同 project 同时起，engine 先持有 4 卡等待授权） | 门禁日志 `used=0 requested=4`（等待中的自家 engine 已剔除），`license.status=valid`，`start_command.sh` 生成、引擎拉起。回归点：宿主机名非 hex（如 `cp0`，host 网络下被容器继承）时自身容器 ID 必须走 cgroup/mountinfo 解析，HOSTNAME 兜底不得命中 |
## 9. 威胁模型与防护边界

离线部署下客户持有宿主机 root，任何跑在客户环境内的校验都只能提高绕过成本，不存在绝对防绕过；绝对防护只有硬件信任根（加密狗/TPM）或在线激活。本设计的防护目标是把常见篡改从"改一个明文文件"抬升到"逆向二进制/伪造容器运行时"的量级，并明确剩余风险。

| 攻击面 | 防护 |
| ------ | ---- |
| 替换/删除明文校验脚本（entrypoint、aiperf.py） | 校验逻辑全部在 wings-control 镜像内的加密代码与 C 二进制中；entrypoint 只是环境准备，aiperf.py 只是查询工具，改它们不影响门禁 |
| compose 注入 `USED_DEVICE_COUNT=0` 伪造已用数 | 环境变量通道已删除：已用卡数由容器内代码经 docker.sock 自查，不读任何 env |
| 替换 wings-control 镜像为历史无门禁版本 | License 构建使用独立 tag（`-license` 后缀）与无门禁版物理隔离，且无门禁镜像不进入 AIPerf 交付；AIPerf 交付时校验镜像 label 并输出镜像 ID 清单，客户可核对 |
| bind-mount 伪目录伪造 board_serial（ESN 顶替/证书拷机） | 验签工具读取 ESN 前检查 DMI 目录挂载来源，非真 sysfs 挂载直接拒绝启动 |
| 篡改比较逻辑（放行超容） | 已用+本次与授权数的比较在验签工具二进制内部完成，编排层只传参 |
| 时钟回拨续命 | SafeTime 水印（见 §6） |

剩余风险（明示不防护）：客户逆向二进制深度篡改、完全绕开 AIPerf 手工拉起引擎（无 label 不入统计）、宿主机层面伪装整个容器运行时。这些超出离线软件校验的能力边界，如需强保证需引入硬件信任根或在线激活，属商务决策。
