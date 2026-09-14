# AIPerf 环境安装部署指导（离线版）

本目录面向**全新未安装环境**，仅凭本文件与同目录的 `install_docker.sh` 两个文件，
即可完成整套 AIPerf 运行环境部署。

- 加速卡驱动 / 固件 / FabricManager / 容器运行时：按本文件「手动安装」部分操作
- Docker + Docker Compose：由 `install_docker.sh` 一键完成

---

## 一、场景与加速卡型号

| 场景 | 含义 | 硬件 |
|------|------|------|
| `A+K` | Ascend NPU + Kunpeng CPU（ARM） | 910B / 910C / 310P |
| `A+X` | Ascend NPU + X86 CPU | 910B / 310P |
| `N+X` | Nvidia GPU + X86 CPU | H20 / L20 / A100 |

> NPU 场景下不同加速卡系列对应不同驱动/固件包前缀（见下文「文件下载」），请按实际硬件选择。

---

## 二、支持的操作系统

| 操作系统 | 架构 | 包管理 |
|----------|------|--------|
| FusionOS 23.2.20 / 23.3.10 | aarch64 / x86_64 | yum |
| Ubuntu 22.04.5 | aarch64 / x86_64 | apt |
| KyLin V11 / V10 SP3 | aarch64 / x86_64 | yum |

> 以下命令默认在 FusionOS  / KyLin（RPM 系，root 用户）环境执行；Ubuntu 22.04 的对应
> `apt` / `dpkg` 命令已在各步骤单独给出（标注「Ubuntu 22.04」），用 `linux-headers-$(uname -r)`
> 替代 `kernel-devel`，用 `apt-mark hold` 替代 `yum versionlock`。

---

## 三、文件下载

先把所需安装包下载到服务器同一目录 `/home/install_pkg`（后续安装均在此目录操作）。
`<arch>` 取 `aarch64` 或 `x86_64`，与目标机 `uname -m` 一致——**按实际场景只下载一种架构对应的包**。

### 3.1 NPU 场景（A+K / A+X）

**Ascend NPU 驱动 / 固件（Ascend HDK 26.1.1，cann 9.0.0）** —— 按加速卡系列选择：

```bash
# A2 (910B) 系列 —— aarch64
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Ascend-hdk-910b-npu-driver_26.1.1_linux-aarch64.run"
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Ascend-hdk-910b-npu-firmware_9.0.0.9.220.run"

# A2 (910B) 系列 —— x86_64（固件同上，驱动换 x86-64）
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Ascend-hdk-910b-npu-driver_26.1.1_linux-x86-64.run"

# A3 (Atlas A3) 系列 —— 仅 aarch64
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Atlas-A3-hdk-npu-driver_26.1.1_linux-aarch64.run"
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Atlas-A3-hdk-npu-firmware_9.0.0.9.220.run"

# 300I Duo (310P) 系列 —— aarch64
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Ascend-hdk-310p-npu-driver_26.1.1_linux-aarch64.run"
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Ascend-hdk-310p-npu-firmware_9.0.0.9.220.run"

# 300I Duo (310P) 系列 —— x86_64（固件同上，驱动换 x86-64）
wget "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Ascend%20HDK/Ascend%20HDK%2026.1.1/Ascend-hdk-310p-npu-driver_26.1.1_linux-x86-64.run"
```

> 也可在华为昇腾官方固件/驱动下载页获取：https://www.hiascend.com/hardware/firmware-drivers

**Ascend Docker Runtime（26.1.0）**

```bash
wget "https://gitcode.com/Ascend/mind-cluster/releases/download/v26.1.0/Ascend-docker-runtime_26.1.0_linux-<arch>.run"
```

> gitcode 下载会 302 跳转到 CDN，`wget` 默认跟随重定向可正常下载。

### 3.2 GPU 场景（N+X）

```bash
# NVIDIA 驱动（595.91.07，x86_64）
wget "https://us.download.nvidia.cn/tesla/595.91.07/NVIDIA-Linux-x86_64-595.91.07.run"

# Fabric Manager（595.91.07） RPM
wget "https://developer.download.nvidia.cn/compute/cuda/repos/rhel8/x86_64/nvidia-fabricmanager-595.91.07-1.el8.x86_64.rpm"

# Fabric Manager（595.91.07） DEB
wget "https://developer.download.nvidia.cn/compute/cuda/repos/ubuntu2204/x86_64/nvidia-fabricmanager_595.91.07-1ubuntu1_amd64.deb"

# Nvidia Container Toolkit（1.13.5，共 4 个 rpm）
wget "https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/libnvidia-container1-1.13.5-1.x86_64.rpm"
wget "https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/libnvidia-container-tools-1.13.5-1.x86_64.rpm"
wget "https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/nvidia-container-toolkit-1.13.5-1.x86_64.rpm"
wget "https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/nvidia-container-toolkit-base-1.13.5-1.x86_64.rpm"

# Nvidia Container Toolkit（1.13.5，共 4 个 deb，全部必装）
# 官方源（developer.download.nvidia.com 会 301 跳转到 .cn 镜像，wget 默认跟随即可）
# 按依赖顺序：lib1 → tools → base → toolkit
wget "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/libnvidia-container1_1.13.5-1_amd64.deb"
wget "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/libnvidia-container-tools_1.13.5-1_amd64.deb"
wget "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/nvidia-container-toolkit-base_1.13.5-1_amd64.deb"
wget "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/nvidia-container-toolkit_1.13.5-1_amd64.deb"
```


> 也可在 NVIDIA 官网驱动下载页获取：https://www.nvidia.cn/drivers/

### 3.3 Docker + Docker Compose（所有场景通用）

```bash
# Docker 二进制（28.5.2）
wget "https://mirrors.aliyun.com/docker-ce/linux/static/stable/<arch>/docker-28.5.2.tgz"

# Docker Compose（v2.39.3）—— GitHub 下载较慢时可配置代理
wget "https://github.com/docker/compose/releases/download/v2.39.3/docker-compose-linux-<arch>"
```

> GitHub 在部分内网下载极慢且易中断，如遇此情况请使用代理或在外网机器下载后拷入。

---

## 四、安装部署

> 全程以 **root** 用户执行。`<前缀>` 按加速卡系列取：`910b`（A2）、`Atlas-A3-hdk`（A3）、`310p`（300IDUO）。
> `<arch>` 取 `aarch64` 或 `x86_64`。

### 步骤 0. 准备安装包

将本场景所需的全部安装包（驱动 / 固件 / 运行时 / Docker / Compose）下载后**统一放入**服务器同一目录
`/home/install_pkg`，并将 `install_docker.sh` 也放入该目录。

> 按实际场景准备，**一台机器只会是以下一种组合**（架构 × 加速卡类型二选一）：
> - 架构：`aarch64`（A+K）**或** `x86_64`（A+X / N+X）
> - 加速卡：NPU（A+K / A+X）**或** GPU（N+X）
>
> 即目录里只会有一套架构对应的包、只会是 NPU 或 GPU 其中一套驱动，不会同时存在两种。

以 A+K（300IDUO，aarch64）场景为例，`/home/install_pkg` 目录最终内容：

```
/home/install_pkg/
├── install_docker.sh                                   # Docker 一键安装脚本
├── Ascend-hdk-310p-npu-driver_26.1.1_linux-aarch64.run # NPU 驱动（按系列/架构选其一）
├── Ascend-hdk-310p-npu-firmware_9.0.0.9.220.run        # NPU 固件
├── Ascend-docker-runtime_26.1.0_linux-aarch64.run      # Ascend 容器运行时
├── docker-28.5.2.tgz                                   # Docker 二进制
└── docker-compose-linux-aarch64                        # Docker Compose 二进制
```

> GPU（N+X）场景则放 NVIDIA 驱动 / Fabric Manager / Container Toolkit 包 + Docker 两件套，结构同理。
> RPM 系用 4 个 rpm，Ubuntu 用对应的 deb（见 3.2 节下载地址），**按目标系统二选一**。

以 N+X（A100，x86_64，RPM 系）场景为例，`/home/install_pkg` 目录最终内容：

```
/home/install_pkg/
├── docker-28.5.2.tgz
├── docker-compose-linux-x86_64
├── install_docker.sh
├── libnvidia-container1-1.13.5-1.x86_64.rpm
├── libnvidia-container-tools-1.13.5-1.x86_64.rpm
├── nvidia-container-toolkit-1.13.5-1.x86_64.rpm
├── nvidia-container-toolkit-base-1.13.5-1.x86_64.rpm
├── nvidia-fabricmanager-595.91.07-1.el8.x86_64.rpm      # 模组机型才需要
└── NVIDIA-Linux-x86_64-595.91.07.run
```

以 N+X（A100，x86_64，Ubuntu 22.04）场景为例，`/home/install_pkg` 目录最终内容：

```
/home/install_pkg/
├── docker-28.5.2.tgz
├── docker-compose-linux-x86_64
├── install_docker.sh
├── libnvidia-container1_1.13.5-1_amd64.deb
├── libnvidia-container-tools_1.13.5-1_amd64.deb
├── nvidia-container-toolkit_1.13.5-1_amd64.deb
├── nvidia-container-toolkit-base_1.13.5-1_amd64.deb     # 必装（toolkit 的依赖）
├── nvidia-fabricmanager_595.91.07-1ubuntu1_amd64.deb    # 模组机型才需要
└── NVIDIA-Linux-x86_64-595.91.07.run
```

### 步骤 1. 安装基础依赖

**RPM 系（FusionOS / OpenEuler / KyLin，`yum`）：**

```bash
# NPU 场景
yum clean all
yum makecache
# 固定内核版本，避免驱动失效
yum install -y yum-plugin-versionlock
yum versionlock kernel kernel-devel
yum install -y gcc net-tools make kernel-devel-$(uname -r) --disableexcludes=all
useradd HwHiAiUser   # NPU 驱动运行用户（若不存在）

# GPU 场景
yum clean all
yum makecache
# 固定内核版本，避免驱动失效
yum install -y yum-plugin-versionlock
yum versionlock kernel kernel-devel
yum install -y gcc make kernel-devel-$(uname -r) --disableexcludes=all
```

**Ubuntu 22.04（`apt`）：**

```bash
# NPU 场景
apt-get update
# 固定内核版本，避免驱动失效（Ubuntu 无 versionlock，用 apt-mark hold）
apt-mark hold linux-image-$(uname -r) linux-headers-$(uname -r)
apt-get install -y gcc net-tools make linux-headers-$(uname -r)
useradd HwHiAiUser   # NPU 驱动运行用户（若不存在）

# GPU 场景
apt-get update
apt-mark hold linux-image-$(uname -r) linux-headers-$(uname -r)
apt-get install -y gcc make linux-headers-$(uname -r)
```

> **内核头版本必须与当前内核完全一致**，否则驱动编译失败。
> - RPM 系核对：`rpm -q kernel-devel` 应等于 `uname -r`；不一致时
>   `yum install -y "kernel-devel-$(uname -r)" --disableexcludes=all`
> - Ubuntu 核对：`dpkg -l | grep linux-headers-$(uname -r)` 应有输出；缺失时
>   `apt-get install -y "linux-headers-$(uname -r)"`
>
> **建议在安装驱动前关闭 SELinux / AppArmor**：
> - RPM 系（Enforcing 下 NPU/NVIDIA 驱动安装可能失败）：
>   `setenforce 0` 并 `sed -i 's/SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config`
> - Ubuntu 默认不启用 SELinux，一般无需处理；若有 AppArmor 干扰可临时
>   `systemctl stop apparmor && systemctl disable apparmor`

### 步骤 2. 安装 NPU 驱动 + 固件（A+K / A+X 场景）

```bash
cd /home/install_pkg
chmod +x Ascend-hdk-<前缀>-npu-driver_26.1.1_linux-<arch>.run \
         Ascend-hdk-<前缀>-npu-firmware_9.0.0.9.220.run
./Ascend-hdk-<前缀>-npu-driver_26.1.1_linux-<arch>.run --full
./Ascend-hdk-<前缀>-npu-firmware_9.0.0.9.220.run --full
# 安装完成后重启系统
reboot
```

> 重启后从步骤 3 继续，无需重复执行步骤 1/2。

### 步骤 2'. 安装 NVIDIA 驱动 + Fabric Manager（N+X 场景）

**2'.1 安装 NVIDIA 驱动（所有 N+X 机型通用）：**

```bash
cd /home/install_pkg
chmod +x NVIDIA-Linux-x86_64-595.91.07.run

# 安装驱动时，需要 同意使用协议安装
./NVIDIA-Linux-x86_64-595.91.07.run
```

**2'.2 安装 Fabric Manager（按机型二选一）：**

> NVIDIA 加速卡按拓扑分为两类，**是否需要 Fabric Manager 取决于机型**：
>
> | 机型 | 特征 | 是否装 Fabric Manager |
> |------|------|----------------------|
> | **模组机型**（Module，如 H20） | 多卡间通过 NVLink/NVSwitch 互联，需统一管理 fabric 拓扑 | **需要** |
> | **PCIe Switch 机型**（如 L20 / A100 PCIe） | 多卡间通过 PCIe Switch 互联，无 NVLink fabric | **不需要** |
>
> 判断方法：`nvidia-smi topo -m` 输出中若卡间存在 `NV`（NVLink）链路即为模组机型；
> 全为 `SYS`/`PIX`（PCIe）则为 PCIe Switch 机型。装完驱动重启后可查看。

**模组机型（需要 Fabric Manager）：**

RPM 系（FusionOS / OpenEuler / KyLin）：

```bash
rpm -ivh nvidia-fabricmanager-595.91.07-1.el8.x86_64.rpm
systemctl enable nvidia-fabricmanager
systemctl start nvidia-fabricmanager
systemctl status nvidia-fabricmanager    # 应为 active (running)
```

Ubuntu 22.04：

```bash
dpkg -i nvidia-fabricmanager_595.91.07-1ubuntu1_amd64.deb
systemctl enable nvidia-fabricmanager
systemctl start nvidia-fabricmanager
systemctl status nvidia-fabricmanager    # 应为 active (running)
```

> Fabric Manager 版本必须与 NVIDIA 驱动版本完全一致（此处均为 595.91.07），否则服务启动失败。

**PCIe Switch 机型（不需要 Fabric Manager）：**

```bash
# 跳过 Fabric Manager 安装，直接进行后续步骤
```

**2'.3 重启系统：**

```bash
# 驱动（及 Fabric Manager）安装完成后重启系统
reboot
```

### 步骤 3. 安装 Docker + Docker Compose（一键脚本）

使用 `install_docker.sh` 一次性完成 Docker 与 Docker Compose 的离线安装。
脚本自动适配架构、采用隔离 containerd 模式（与 k8s 互不影响）、并在安装结束后永久关闭 SELinux。

**前置**：Docker 两个二进制包（`docker-28.5.2.tgz` 与 `docker-compose-linux-<arch>`）已放入
`/home/install_pkg`（与 `install_docker.sh` 同目录，见步骤 0）。

执行安装：

```bash
cd /home/install_pkg
bash install_docker.sh --pkg-dir /home/install_pkg
# 卸载：           bash install_docker.sh --uninstall
# k8s 环境共享 containerd：bash install_docker.sh --shared-containerd
# 帮助：           bash install_docker.sh -h
```

> 脚本查找包目录的顺序（命中即用）：`--pkg-dir DIR` → 脚本同目录的 `<arch>/` 子目录 → 脚本同目录。
> 本文档统一用 `--pkg-dir /home/install_pkg` 显式指定，最清晰。

脚本行为：解压 Docker 二进制 → 安装到 `/usr/bin`（containerd 运行时装到 `/usr/lib/docker`，
不在 PATH，避免与 k8s 冲突）→ 生成 `docker.service`/`docker-containerd.service`（隔离模式）→
安装 docker-compose → 生成 `daemon.json.example`（可选 `data-root=/data/docker`）→ 启动并验证 →
永久关闭 SELinux。已是运行态的 Docker/Compose 会自动跳过（幂等）。

> 如需把 Docker 数据目录放到大盘（如 `/data/docker`）：
> `cp /etc/docker/daemon.json.example /etc/docker/daemon.json` 后 `systemctl restart docker`。

### 步骤 4. 安装容器运行时

**Ascend Docker Runtime（A+K / A+X 场景）：**

```bash
cd /home/install_pkg
chmod +x Ascend-docker-runtime_26.1.0_linux-<arch>.run
# 需要接受EULA才能安装
./Ascend-docker-runtime_26.1.0_linux-<arch>.run --install
systemctl daemon-reload && systemctl restart docker
```

**NVIDIA Container Toolkit（N+X 场景）：**

RPM 系（FusionOS / OpenEuler / KyLin）：

```bash
cd /home/install_pkg
rpm -ivh libnvidia-container1-1.13.5-1.x86_64.rpm \
        libnvidia-container-tools-1.13.5-1.x86_64.rpm \
        nvidia-container-toolkit-base-1.13.5-1.x86_64.rpm \
        nvidia-container-toolkit-1.13.5-1.x86_64.rpm
nvidia-ctk runtime configure --runtime=docker
systemctl daemon-reload 
systemctl restart docker
```

Ubuntu 22.04（4 个 deb 全部必装）：

> **必须按依赖顺序安装**（`nvidia-container-toolkit` 依赖 `nvidia-container-toolkit-base`，
> 后者又依赖 `libnvidia-container-tools` → `libnvidia-container1`）。缺 `*-base` 或顺序错乱时，
> `nvidia-container-toolkit` 会停在 `iU`（已解包未配置）状态并报 dependency problems。

```bash
cd /home/install_pkg
# 按依赖自底向上安装（也可一次性 dpkg -i 四个包，dpkg 会自动排序）
dpkg -i libnvidia-container1_1.13.5-1_amd64.deb
dpkg -i libnvidia-container-tools_1.13.5-1_amd64.deb
dpkg -i nvidia-container-toolkit-base_1.13.5-1_amd64.deb
dpkg -i nvidia-container-toolkit_1.13.5-1_amd64.deb
# 离线环境下若仍提示依赖缺失，用本地源补齐：
#   apt-get install -f -y      # 需有本地源/缓存
nvidia-ctk runtime configure --runtime=docker
systemctl daemon-reload
systemctl restart docker
```

### 步骤 5. 验证

```bash
npu-smi info          # NPU 场景：查看驱动/固件版本与卡状态
nvidia-smi            # GPU 场景：查看驱动版本与卡状态
docker version        # 确认 Docker 正常
docker-compose version
```

---

## 五、组件版本汇总

| 组件 | 版本 | 备注 |
|------|------|------|
| Ascend NPU 驱动 | Ascend HDK 26.1.1 | A2/A3/300IDUO 各系列按前缀下载 |
| Ascend NPU 固件 | 9.0.0.9.220 | cann 9.0.0 |
| Ascend-docker-runtime | 26.1.0 | 昇腾容器运行时 |
| NVIDIA GPU 驱动 | 595.91.07 | 当前指定版本 |
| NVIDIA Fabric Manager | 595.91.07 | 与驱动版本对齐 |
| Nvidia Container Toolkit | 1.13.5 | nvidia-docker-runtime |
| Docker | 28.5.2 | 二进制 tar 包 |
| Docker Compose | v2.39.3 | 二进制文件 |
| vllm-ascend | v0.21.0rc1 / v0.22.1rc1 / v0.23.0rc1 / v0.26.0rc1 | NPU 推理镜像（310P，aarch64）：`vllm-ascend-v<版本>rc1-310p-aarch64.tgz` |
| vllm (openai) | v0.26.0 / v0.27.1 / v0.28.0 / v0.29.0 | GPU 推理镜像（amd64）：`vllm-openai-v<版本>-amd64.tgz` |

---

## 六、注意事项

- 驱动 / 固件 / Fabric Manager 装完**需重启系统**才生效（步骤 2 / 2' 后会提示，脚本不自动重启）。
- NPU 场景需 `kernel-devel` 与内核匹配；建议装驱动前关闭 SELinux。
- Docker 卸载（`install_docker.sh --uninstall`）会保留 `/etc/docker/` 配置与 `/var/lib/docker/` 数据，如需彻底清除请手动删除。
- （可选）Ascend NPU MCU 升级为非必须步骤，仅在需要刷新 MCU 固件时手动执行，参考华为昇腾官方文档。

## 七、故障排查

- **Docker 启动失败**：`journalctl -u docker -u docker-containerd --no-pager | tail -50`
- **NPU 驱动安装失败**：检查 `kernel-devel` 是否与 `uname -r` 一致、SELinux 是否已关闭、`gcc/make` 是否已装
- **docker-compose 下载中断**：GitHub 在内网可能慢/中断，使用代理或外网下载后拷入
- **驱动装完 `npu-smi`/`nvidia-smi` 无输出**：确认已重启系统生效

---

## 八、FAQ

### Q1. 执行 `yum update` 升级了内核，导致驱动安装失败 / `npu-smi` 异常，如何恢复？

**根因**：`yum update` 会拉取并安装新版内核，同时把 grub 默认启动项指向新内核。但 NPU/NVIDIA 驱动
是针对**当时运行的内核**编译内核模块的——一旦内核版本变化（或 `kernel-devel` 与运行内核不一致），
驱动编译/加载就会失败，表现为驱动安装报错、`npu-smi`/`nvidia-smi` 无输出或报 "version mismatch"。

**排查**：核对三个版本是否一致：

```bash
uname -r                          # 当前运行内核
# RPM 系：
rpm -q kernel-devel               # 已装的 kernel-devel
grubby --default-kernel           # grub 默认启动内核
# Ubuntu：
dpkg -l | grep -E 'linux-(image|headers)-' | awk '{print $2,$3}'   # 已装内核/头文件
grub-editenv list                 # 或 cat /etc/default/grub | grep GRUB_DEFAULT
```

三者应完全一致。若 `kernel-devel` / `linux-headers` 版本 ≠ `uname -r`，即为问题原因。

**恢复默认内核并配套头文件**（以 FusionOS / OpenEuler 为例）：

```bash
# 1) 查看已装内核与默认启动项
rpm -qa | grep -E '^kernel-(rt-)?[0-9]' | sort
grubby --default-kernel

# 2) 将默认启动内核改回原（驱动可用时）的内核
grubby --set-default="/boot/vmlinuz-<原内核版本>"   # 如 5.10.0-278.0.0.181.u183.fos23.aarch64

# 3) 安装与该内核配套的 kernel-devel（精确到 uname -r）
yum install -y "kernel-devel-$(uname -r)" --disableexcludes=all
# 若装成了高版本，用降级方式装回配套版本：
#   yum downgrade -y "kernel-devel-<原内核版本>" --disableexcludes=all

# 4) 重启回到默认内核
reboot

# 5) 重启后再次核对一致，然后重装驱动
uname -r && rpm -q kernel-devel    # 二者应相同
```

**恢复默认内核并配套头文件**（Ubuntu 22.04）：

```bash
# 1) 查看已装内核
dpkg -l | grep -E 'linux-image-[0-9]' | awk '{print $2,$3}'

# 2) 将默认启动内核改回原（驱动可用时）的内核
#    Ubuntu 用 grub-set-default（需 /etc/default/grub 中 GRUB_DEFAULT=saved）
sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' /etc/default/grub
grub-set-default "Ubuntu, with Linux <原内核版本>"   # 或用菜单序号：grub-reboot 1>2
update-grub

# 3) 安装与该内核配套的 linux-headers（精确到 uname -r）
apt-get install -y "linux-headers-$(uname -r)"

# 4) 重启回到默认内核
reboot

# 5) 重启后再次核对一致，然后重装驱动
uname -r && dpkg -l | grep "linux-headers-$(uname -r)"    # 二者应相同
```

**预防（固定内核版本，避免被 `yum update` 带走）**：

NPU/NVIDIA 驱动安装后，若执行 `yum update` / `apt upgrade` 升级内核，驱动会因内核版本变化而失效。
**装驱动前建议固定内核版本**，按操作系统任选：

RPM 系（FusionOS / OpenEuler / KyLin）：

```bash
# 方式 A（推荐）：用 versionlock 插件锁死 kernel / kernel-devel 版本
yum install -y yum-plugin-versionlock
yum versionlock kernel kernel-devel
# 之后 yum update 不会升级内核；解锁：yum versionlock delete kernel kernel-devel

# 方式 B：yum update 时排除内核包（临时，每次都要带）
yum update --exclude=kernel*

# 方式 C：固定 grub 默认启动内核（防止升级后 grub 切到新内核）
grubby --set-default="/boot/vmlinuz-$(uname -r)"
```

Ubuntu 22.04：

```bash
# 方式 A（推荐）：apt-mark hold 锁住当前内核与头文件
apt-mark hold linux-image-$(uname -r) linux-headers-$(uname -r) \
              linux-image-generic linux-headers-generic
# 之后 apt upgrade 不会升级内核；解锁：apt-mark unhold <同上包名>

# 方式 B：apt upgrade 时排除内核包（临时，每次都要带）
apt-mark hold linux-image-generic linux-headers-generic && apt upgrade
# 或单次跳过：apt upgrade -o Dpkg::Options::="--refuse-downgrade" （仅防降级，不防升级，慎用）

# 方式 C：固定 grub 默认启动内核（防止升级后 grub 切到新内核）
sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' /etc/default/grub
grub-set-default "Ubuntu, with Linux $(uname -r)"
update-grub
```

> 装驱动前务必核对头文件版本等于 `uname -r`：
> - RPM 系：`rpm -q kernel-devel` 等于 `uname -r`；不一致时
>   `yum install -y "kernel-devel-$(uname -r)" --disableexcludes=all`
> - Ubuntu：`dpkg -l | grep "linux-headers-$(uname -r)"` 有输出；缺失时
>   `apt-get install -y "linux-headers-$(uname -r)"`
>
> 如确需升级系统内核：先升级 → 重启进入新内核 → 安装配套头文件（`kernel-devel-$(uname -r)` /
> `linux-headers-$(uname -r)`）→ **重新安装驱动**（驱动需针对新内核重新编译内核模块）。
> 建议用 `yum install` / `apt-get install` 精准装包而非 `yum update` / `apt upgrade` 整体升级。

> 注：`install_docker.sh` 安装 Docker 不依赖内核版本，不受此问题影响；仅**驱动 / 固件**对内核版本敏感。
> Ascend NPU 驱动 `.run` 包安装时针对当前内核现场编译内核模块，不支持 DKMS 自动重编，
> 因此**固定内核版本**是避免驱动失效的根本手段。

### Q2. 使用 300I Duo（310P）加速卡时，模型加载 / 推理报 BF16 相关错误怎么办？

**根因**：300I Duo（310P）加速卡**不支持 BF16（bfloat16）数据类型**。若模型权重或配置默认使用
BF16（`torch_dtype` 为 `bfloat16`），在 300I Duo 上会加载失败或推理报错。

**解决**：修改模型权重目录下 `config.json` 中的 `torch_dtype` 字段，将其值改为 `float16`：

```bash
# 进入模型权重目录
cd /path/to/model_weights

# 查看当前 torch_dtype 值
grep '"torch_dtype"' config.json

# 修改为 float16
sed -i 's/"torch_dtype"[[:space:]]*:[[:space:]]*"bfloat16"/"torch_dtype": "float16"/' config.json

# 确认修改结果
grep '"torch_dtype"' config.json
```

> 修改后应输出类似：`"torch_dtype": "float16"`。
>
> 若模型权重本身已按 BF16 存储，仅改 `config.json` 可能不够，需用支持 float16 的权重版本或
> 在加载代码中显式 `torch_dtype=torch.float16` 转换。详见对应模型 / 推理框架的适配说明。
