#!/bin/bash
#
# install_docker.sh — Docker + Docker Compose 离线一键安装/卸载脚本（自包含）
#
# 目标：全新未安装机器，配合 README.md 手动安装驱动/固件/运行时后，本脚本完成
#       Docker + Docker Compose 的安装，即可完成整个环境部署。
#
# 特性：
#   - 纯离线：从本地目录读取二进制包，不联网
#   - 自包含：不依赖 common.sh / versions.conf，可独立拷贝运行
#   - 自动适配 x86_64 / aarch64
#   - 隔离模式（默认）：Docker 启动自己的 containerd 守护进程，与 k8s 完全隔离
#     可选 --shared-containerd 共享 k8s 的 containerd
#   - 幂等：检测到 Docker 已在运行则跳过安装
#   - 支持 --uninstall 卸载
#
# 包查找路径（依次查找，命中即用）：
#   1. --pkg-dir DIR 指定目录
#   2. <install>/packages/<arch>/docker/   （仓库约定，首选）
#   3. <script-dir>/<arch>/                （兼容离线脚本目录约定）
#   4. <script-dir>/                       （脚本同目录）
#
# 目录结构示例（只需准备当前架构对应的包）：
#   ai_perf/install/
#   ├── script/install_docker.sh
#   └── packages/<arch>/docker/
#       ├── docker-28.5.2.tgz
#       └── docker-compose-linux-<arch>
#
# 用法:
#   安装: bash install_docker.sh
#   指定包目录: bash install_docker.sh --pkg-dir /path/to/packages/aarch64/docker
#   卸载: bash install_docker.sh --uninstall
#

set -euo pipefail

# ==================== 配置 ====================
DOCKER_VERSION="28.5.2"
COMPOSE_VERSION="v2.39.3"
INSTALL_DIR="/usr/bin"
SERVICE_DIR="/etc/systemd/system"
DATA_ROOT="/data/docker"
DOCKER_LIB_DIR="/usr/lib/docker"
DOCKER_CTRD_SOCK="/var/run/docker/containerd/containerd.sock"
COMPOSE_BIN_PATH="/usr/local/bin/docker-compose"
# ==================== 配置结束 ====================

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ==================== 参数解析 ====================
SHARED_CONTAINERD=false
PKG_DIR=""
UNINSTALL=false

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Docker + Docker Compose 离线安装/卸载脚本 (无需网络)"
    echo ""
    echo "Options:"
    echo "  --uninstall          卸载 Docker 与 Docker Compose (保留配置和数据)"
    echo "  --pkg-dir DIR        指定 Docker 二进制包所在目录"
    echo "                       默认依次查找:"
    echo "                         <install>/packages/<arch>/docker/"
    echo "                         <script-dir>/<arch>/"
    echo "                         <script-dir>/"
    echo "  --shared-containerd  Docker 共享已有的 containerd (k8s 环境)"
    echo "  -h, --help           显示帮助"
    echo ""
    echo "目录结构 (只需准备当前架构对应的包):"
    echo "  <pkg-dir>/"
    echo "  ├── docker-${DOCKER_VERSION}.tgz"
    echo "  └── docker-compose-linux-<arch>"
    echo ""
    echo "Docker 二进制包下载地址 (离线前自行下载):"
    echo "  x86_64:  https://mirrors.aliyun.com/docker-ce/linux/static/stable/x86_64/docker-${DOCKER_VERSION}.tgz"
    echo "  aarch64: https://mirrors.aliyun.com/docker-ce/linux/static/stable/aarch64/docker-${DOCKER_VERSION}.tgz"
    echo "Docker Compose 下载地址:"
    echo "  x86_64:  https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64"
    echo "  aarch64: https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-aarch64"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --uninstall) UNINSTALL=true; shift ;;
        --pkg-dir) PKG_DIR="$2"; shift 2 ;;
        --shared-containerd) SHARED_CONTAINERD=true; shift ;;
        -h|--help)   usage ;;
        *)           error "未知参数: $1 (见 --help)" ;;
    esac
done

# ==================== root 权限检查 ====================
if [ "$(id -u)" -ne 0 ]; then
    error "请使用 root 用户运行此脚本"
fi

# ==================== 卸载 ====================
if [ "$UNINSTALL" = true ]; then
    info "===== 卸载 Docker / Docker Compose ====="

    # 停止 Docker 服务
    if systemctl is-active --quiet docker 2>/dev/null; then
        info "停止 Docker 服务..."
        systemctl stop docker || true
    fi

    # 停止 Docker 的 containerd 服务
    if systemctl is-active --quiet docker-containerd 2>/dev/null; then
        info "停止 docker-containerd 服务..."
        systemctl stop docker-containerd || true
    fi

    # 禁用并删除 service 文件
    for svc in docker docker-containerd; do
        if [ -f "${SERVICE_DIR}/${svc}.service" ]; then
            info "删除 ${svc}.service..."
            systemctl disable "$svc" 2>/dev/null || true
            rm -f "${SERVICE_DIR}/${svc}.service"
        fi
    done
    systemctl daemon-reload

    # 删除 Docker 专属二进制
    for bin in docker dockerd docker-init docker-proxy; do
        if [ -x "${INSTALL_DIR}/${bin}" ]; then
            rm -f "${INSTALL_DIR}/${bin}"
            info "  删除: ${INSTALL_DIR}/${bin}"
        fi
    done

    # 删除 Docker 的 containerd 运行时
    if [ -d "${DOCKER_LIB_DIR}" ]; then
        for bin in containerd containerd-shim-runc-v2 runc; do
            if [ -x "${DOCKER_LIB_DIR}/${bin}" ]; then
                rm -f "${DOCKER_LIB_DIR}/${bin}"
                info "  删除: ${DOCKER_LIB_DIR}/${bin}"
            fi
        done
        rmdir "${DOCKER_LIB_DIR}" 2>/dev/null || true
    fi

    # 删除 docker-compose
    for f in "${COMPOSE_BIN_PATH}" /usr/bin/docker-compose; do
        if [ -L "$f" ] || [ -x "$f" ]; then
            rm -f "$f"
            info "  删除: $f"
        fi
    done

    # 删除 Docker 专用的 containerd 配置
    rm -rf /etc/docker/containerd

    # 验证 k8s containerd 未受影响
    if systemctl is-active --quiet containerd 2>/dev/null; then
        info "k8s containerd 服务正常运行 (未受影响)"
    else
        warn "containerd 服务未运行，请检查 k8s!"
    fi

    info "Docker / Docker Compose 卸载完成!"
    warn "以下内容已保留 (如需删除请手动操作):"
    warn "  配置: /etc/docker/"
    warn "  数据: /var/lib/docker/ 或 ${DATA_ROOT}"
    exit 0
fi

# ==================== 安装流程 ====================

# 脚本目录与 install 根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ==================== 1. 架构检测 ====================
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  DOCKER_ARCH="x86_64" ;;
    aarch64) DOCKER_ARCH="aarch64" ;;
    *)       error "不支持的架构: $ARCH" ;;
esac
info "检测到架构: ${ARCH}"

# ==================== 2. 幂等检测 ====================
if command -v docker &>/dev/null && docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
    DOCKER_VER="$(docker version --format '{{.Server.Version}}' 2>/dev/null)"
    info "检测到 Docker 已在运行 (v${DOCKER_VER})，跳过安装。"
    if [ -x "${COMPOSE_BIN_PATH}" ]; then
        info "检测到 docker-compose 已存在，跳过。"
    else
        warn "docker-compose 未安装，将继续安装 compose。"
        SKIP_DOCKER=1
    fi
    # 若 docker 与 compose 都已就绪，则直接退出
    if [ -x "${COMPOSE_BIN_PATH}" ]; then
        info "Docker 与 Docker Compose 均已就绪，无需操作。"
        exit 0
    fi
else
    SKIP_DOCKER=0
fi

# ==================== 3. 确定包目录 ====================
# 候选目录（依次查找，命中即用）
CANDIDATE_DIRS=()
if [ -n "$PKG_DIR" ]; then
    CANDIDATE_DIRS+=("$PKG_DIR")
fi
CANDIDATE_DIRS+=("${INSTALL_ROOT}/packages/${DOCKER_ARCH}/docker")
CANDIDATE_DIRS+=("${SCRIPT_DIR}/${DOCKER_ARCH}")
CANDIDATE_DIRS+=("${SCRIPT_DIR}")

PKG_FOUND_DIR=""
for d in "${CANDIDATE_DIRS[@]}"; do
    if [ -d "$d" ]; then
        if [ -f "${d}/docker-${DOCKER_VERSION}.tgz" ] || [ -f "${d}/docker-compose-linux-${DOCKER_ARCH}" ]; then
            PKG_FOUND_DIR="$d"
            break
        fi
    fi
done

if [ -z "$PKG_FOUND_DIR" ]; then
    error "未找到 Docker 安装包目录。请将 docker-${DOCKER_VERSION}.tgz 与 docker-compose-linux-${DOCKER_ARCH} 放入以下任一目录后重试:
  <install>/packages/${DOCKER_ARCH}/docker/
  <script-dir>/${DOCKER_ARCH}/
  <script-dir>/
或使用 --pkg-dir DIR 指定。"
fi
info "包目录: ${PKG_FOUND_DIR}"

# ==================== 4. 离线文件检查 ====================
DOCKER_TGZ=""
COMPOSE_BIN=""

for p in \
    "${PKG_FOUND_DIR}/docker-${DOCKER_VERSION}.tgz"; do
    if [ -f "$p" ]; then
        DOCKER_TGZ="$p"
        break
    fi
done

for p in \
    "${PKG_FOUND_DIR}/docker-compose-linux-${DOCKER_ARCH}"; do
    if [ -f "$p" ]; then
        COMPOSE_BIN="$p"
        break
    fi
done

info "检查离线安装包..."
if [ "$SKIP_DOCKER" != 1 ] && [ -z "$DOCKER_TGZ" ]; then
    error "Docker 二进制包不存在: docker-${DOCKER_VERSION}.tgz (在 ${PKG_FOUND_DIR}/)"
fi
[ -n "$DOCKER_TGZ" ] && info "  Docker: ${DOCKER_TGZ} ($(du -sh "$DOCKER_TGZ" | awk '{print $1}'))"

if [ -z "$COMPOSE_BIN" ]; then
    warn "docker-compose 二进制不存在 (docker-compose-linux-${DOCKER_ARCH})，将跳过 compose 安装"
else
    info "  Compose: ${COMPOSE_BIN} ($(du -sh "$COMPOSE_BIN" | awk '{print $1}'))"
fi

# ==================== 5. 环境检测（k8s / containerd） ====================
if [ "$SKIP_DOCKER" != 1 ]; then
    info "检测环境中..."

    HAS_K8S=false
    HAS_CONTAINERD=false
    CONTAINERD_SOCKET=""
    K8S_CTRD_PATH=""

    if command -v kubelet &>/dev/null || [ -d /etc/kubernetes ]; then
        HAS_K8S=true
        info "检测到 Kubernetes 环境"
    fi

    if command -v containerd &>/dev/null; then
        HAS_CONTAINERD=true
        PATH_CTRD_PATH=$(command -v containerd)
        PATH_CTRD_VERSION=$(containerd --version 2>/dev/null | awk '{print $3}' | sed 's/^v//' || echo "unknown")
        info "检测到 containerd (PATH): ${PATH_CTRD_PATH} v${PATH_CTRD_VERSION}"
    fi

    if systemctl is-active --quiet containerd 2>/dev/null; then
        K8S_CTRD_PATH=$(systemctl cat containerd 2>/dev/null | grep '^ExecStart=' | head -1 | sed 's/ExecStart=//' | awk '{print $1}' || true)
        if [ -n "$K8S_CTRD_PATH" ]; then
            info "k8s containerd 服务二进制: ${K8S_CTRD_PATH}"
        fi
        info "containerd 服务正在运行"
    fi

    for sock in /run/containerd/containerd.sock /var/run/containerd/containerd.sock; do
        if [ -S "$sock" ]; then
            CONTAINERD_SOCKET="$sock"
            info "检测到 containerd socket: $sock"
            break
        fi
    done
fi

# ==================== 6. 解压安装 Docker 二进制 ====================
#
# Docker 专属 (docker/dockerd/docker-init/docker-proxy) → /usr/bin/
# Docker 的 containerd 运行时 (containerd/runc/shim)   → /usr/lib/docker/
#
# /usr/lib/docker/ 不在系统 PATH 中，k8s 不可能误用，彻底避免冲突。
# docker-containerd.service 和 docker.service 通过 Environment=PATH
# 将 /usr/lib/docker/ 加入进程 PATH，使 dockerd 及其子进程能找到。

if [ "$SKIP_DOCKER" = 1 ]; then
    info "Docker 已在运行，跳过二进制安装。"
else
    TMP_DIR=$(mktemp -d /tmp/docker_install.XXXXXX)
    cleanup() { rm -rf "$TMP_DIR"; }
    trap cleanup EXIT

    info "解压 Docker 二进制包..."
    tar -xzf "$DOCKER_TGZ" -C "$TMP_DIR"

    info "安装二进制文件..."
    for bin in docker dockerd docker-init docker-proxy; do
        if [ -f "${TMP_DIR}/docker/${bin}" ]; then
            install -m 755 "${TMP_DIR}/docker/${bin}" "${INSTALL_DIR}/${bin}"
            info "  安装: ${bin} → ${INSTALL_DIR}/${bin}"
        fi
    done

    mkdir -p "${DOCKER_LIB_DIR}"
    for bin in containerd containerd-shim-runc-v2 runc; do
        if [ -f "${TMP_DIR}/docker/${bin}" ]; then
            install -m 755 "${TMP_DIR}/docker/${bin}" "${DOCKER_LIB_DIR}/${bin}"
            VER=$("${DOCKER_LIB_DIR}/${bin}" --version 2>/dev/null | awk '{print $3}' | sed 's/^v//' || echo "unknown")
            info "  安装: ${bin} → ${DOCKER_LIB_DIR}/${bin} (v${VER})"
        fi
    done
fi

# ==================== 7. 安装 docker-compose ====================
if [ -n "$COMPOSE_BIN" ] && [ ! -x "${COMPOSE_BIN_PATH}" ]; then
    info "安装 docker-compose..."
    install -m 755 "$COMPOSE_BIN" "${COMPOSE_BIN_PATH}"
    ln -sf "${COMPOSE_BIN_PATH}" /usr/bin/docker-compose
    COMPOSE_VER=$("${COMPOSE_BIN_PATH}" version --short 2>/dev/null || echo "unknown")
    info "  安装: docker-compose → ${COMPOSE_BIN_PATH} (v${COMPOSE_VER})"
elif [ -x "${COMPOSE_BIN_PATH}" ]; then
    info "docker-compose 已存在，跳过。"
fi

# 若 Docker 此前已在运行，则无需重配服务，直接退出
if [ "$SKIP_DOCKER" = 1 ]; then
    echo ""
    echo "========================================"
    docker -v
    [ -x "${COMPOSE_BIN_PATH}" ] && "${COMPOSE_BIN_PATH}" version
    echo "========================================"
    info "完成。"
    exit 0
fi

# ==================== 8. 共存模式配置 ====================
#
# 【隔离模式】(默认):
#   Docker 的 containerd 运行时位于 /usr/lib/docker/ (不在系统 PATH 中)
#   1. 生成 Docker 专用的 containerd 配置 (/etc/docker/containerd/config.toml)
#      使用 v2 格式 (containerd v1.7.x 兼容)，避免读取 k8s 的 v3 格式配置
#   2. 创建 docker-containerd.service 启动 Docker 自己的 containerd 守护进程
#      使用独立 socket (/var/run/docker/containerd/containerd.sock)
#      使用独立数据目录 (/var/lib/docker/containerd)
#   3. docker.service 依赖 docker-containerd.service
#      dockerd 通过 --containerd 连接 Docker 自己的 containerd
#
# 【共享模式】(--shared-containerd):
#   dockerd 直接连接 k8s 的 containerd socket

info "配置共存模式..."

if [ "$SHARED_CONTAINERD" = true ]; then
    # 共享模式: dockerd 连接 k8s 的 containerd
    if [ -z "$CONTAINERD_SOCKET" ]; then
        error "共享模式需要 containerd socket，但未检测到"
    fi
    DOCKERD_EXEC="ExecStart=${INSTALL_DIR}/dockerd --containerd ${CONTAINERD_SOCKET}"
    DOCKERD_PATH=""
    DOCKER_CTRD_SERVICE=false
    info "共享模式: Docker 将连接 ${CONTAINERD_SOCKET}"
else
    # 隔离模式: Docker 启动自己的 containerd 守护进程

    # 8a. 生成 Docker 专用的 containerd 配置
    mkdir -p /etc/docker/containerd
    cat > /etc/docker/containerd/config.toml <<EOF
version = 2
root = "/var/lib/docker/containerd"
state = "/var/run/docker/containerd"

[grpc]
  address = "${DOCKER_CTRD_SOCK}"

[plugins."io.containerd.grpc.v1.cri"]
  disable_cri = true
EOF
    info "  已生成: /etc/docker/containerd/config.toml"

    # 8b. 生成 docker-containerd.service
    cat > "${SERVICE_DIR}/docker-containerd.service" <<EOF
[Unit]
Description=Docker containerd (isolated from k8s)
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=${DOCKER_LIB_DIR}/containerd --config /etc/docker/containerd/config.toml
ExecReload=/bin/kill -s HUP \$MAINPID
Environment=PATH=${DOCKER_LIB_DIR}:/usr/bin:/usr/local/bin:/usr/sbin:/usr/local/sbin
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
TasksMax=infinity
Delegate=yes
KillMode=process
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    chmod 644 "${SERVICE_DIR}/docker-containerd.service"
    info "  已生成: docker-containerd.service"

    # 8c. docker.service 依赖 docker-containerd
    DOCKERD_EXEC="ExecStart=${INSTALL_DIR}/dockerd --containerd ${DOCKER_CTRD_SOCK}"
    DOCKERD_PATH="Environment=PATH=${DOCKER_LIB_DIR}:/usr/bin:/usr/local/bin:/usr/sbin:/usr/local/sbin"
    DOCKER_CTRD_SERVICE=true

    info "隔离模式:"
    info "  Docker containerd: ${DOCKER_LIB_DIR}/containerd → ${DOCKER_CTRD_SOCK}"
    info "  k8s   containerd:  ${K8S_CTRD_PATH:-/usr/local/bin/containerd} → ${CONTAINERD_SOCKET:-/run/containerd/containerd.sock}"
fi

# ==================== 9. docker.service ====================
info "生成 docker.service..."

if [ -f "${SERVICE_DIR}/docker.service" ]; then
    rm -f "${SERVICE_DIR}/docker.service"
fi

if [ "$DOCKER_CTRD_SERVICE" = true ]; then
    CTRD_AFTER="After=network-online.target firewalld.service docker-containerd.service"
    CTRD_REQUIRES="Requires=docker-containerd.service"
else
    CTRD_AFTER="After=network-online.target firewalld.service containerd.service"
    CTRD_REQUIRES=""
fi

cat > "${SERVICE_DIR}/docker.service" <<EOF
[Unit]
Description=Docker Application Container Engine
Documentation=https://docs.docker.com
${CTRD_AFTER}
${CTRD_REQUIRES}
Wants=network-online.target

[Service]
Type=notify
${DOCKERD_EXEC}
${DOCKERD_PATH}
ExecReload=/bin/kill -s HUP \$MAINPID
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
TimeoutStartSec=0
Delegate=yes
KillMode=process
Restart=on-failure
StartLimitBurst=3
StartLimitInterval=60s

[Install]
WantedBy=multi-user.target
EOF
chmod 644 "${SERVICE_DIR}/docker.service"
info "  已生成: docker.service"

# ==================== 10. daemon.json ====================
info "检查存储空间..."

VAR_LIB_AVAIL_GB=$(df /var/lib/ --output=avail -BG 2>/dev/null | tail -1 | tr -d ' G' || echo "0")
if [ "$VAR_LIB_AVAIL_GB" -lt 200 ] 2>/dev/null; then
    warn "/var/lib/ 可用空间仅 ${VAR_LIB_AVAIL_GB}G (建议 >= 200G)"
    warn "建议将 Docker 数据目录设置到更大存储路径 (如 ${DATA_ROOT})"
fi

mkdir -p /etc/docker
if [ -f /etc/docker/daemon.json ]; then
    warn "/etc/docker/daemon.json 已存在，跳过"
else
    cat > /etc/docker/daemon.json.example <<EOF
{
    "data-root": "${DATA_ROOT}"
}
EOF
    info "  已生成: /etc/docker/daemon.json.example"
    info "  请修改后: cp /etc/docker/daemon.json.example /etc/docker/daemon.json"
fi

# ==================== 11. 启动 ====================
info "启动 Docker..."

systemctl daemon-reload

if [ "$DOCKER_CTRD_SERVICE" = true ]; then
    systemctl enable docker-containerd
    if ! systemctl start docker-containerd; then
        error "docker-containerd 启动失败，请检查: journalctl -u docker-containerd"
    fi
    info "docker-containerd 启动成功"
fi

systemctl enable docker
if systemctl start docker; then
    info "Docker 启动成功!"
else
    error "Docker 启动失败，请检查: journalctl -u docker"
fi

# ==================== 12. 验证 ====================
echo ""
echo "========================================"
docker -v
if [ -x "${COMPOSE_BIN_PATH}" ]; then
    "${COMPOSE_BIN_PATH}" version
fi
echo ""

if [ "${HAS_K8S:-false}" = true ] || [ "${HAS_CONTAINERD:-false}" = true ]; then
    echo "=== k8s 安全验证 ==="

    if systemctl is-active --quiet containerd 2>/dev/null; then
        info "k8s containerd 服务正常运行 (未受影响)"
    else
        warn "containerd 服务未运行，请检查 k8s!"
    fi

    if [ -n "${K8S_CTRD_PATH:-}" ] && [ -x "$K8S_CTRD_PATH" ]; then
        AFTER_VER=$("$K8S_CTRD_PATH" --version 2>/dev/null | awk '{print $3}' | sed 's/^v//' || echo "unknown")
        info "k8s containerd 二进制: ${K8S_CTRD_PATH} v${AFTER_VER} (未被修改)"
    fi

    if [ "$SHARED_CONTAINERD" = false ]; then
        echo ""
        echo "=== containerd 进程 ==="
        ps -eo pid,args | grep '[/]containerd ' | grep -v shim

        echo ""
        DOCKER_CTRD_VER=$(docker info 2>/dev/null | grep "containerd version" | awk '{print $3}')
        if [ -n "$DOCKER_CTRD_VER" ]; then
            info "Docker containerd version: ${DOCKER_CTRD_VER}"
        else
            warn "无法获取 Docker containerd 版本"
        fi

        if [ -S "${DOCKER_CTRD_SOCK}" ] && [ -S "${CONTAINERD_SOCKET:-/run/containerd/containerd.sock}" ]; then
            info "隔离验证通过: Docker 和 k8s 使用不同的 containerd socket"
        fi
    fi
    echo ""
fi

if [ ! -f /etc/docker/daemon.json ]; then
    warn "请配置 daemon.json 后重启 Docker:"
    warn "  cp /etc/docker/daemon.json.example /etc/docker/daemon.json"
    warn "  systemctl daemon-reload"
    warn "  systemctl restart docker"
    echo ""
fi

# ==================== 13. 关闭 SELinux ====================
# FusionOS 23.3.10 上 SELINUX=enforcing 会导致问题
info "永久关闭 SELinux"
if [ -f /etc/selinux/config ]; then
    sed -i 's/SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config
    setenforce 0 2>/dev/null || true
    info "  已修改 /etc/selinux/config (SELINUX=disabled)"
else
    warn "未找到 /etc/selinux/config，跳过"
fi

info "安装完成!"
