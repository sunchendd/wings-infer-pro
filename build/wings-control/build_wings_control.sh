#!/bin/bash

# 设置工作目录
SCRIPT_PATH=$(readlink -f "$0")
WORK_DIR=$(dirname "$SCRIPT_PATH")

# 获取系统架构信息
ARCH=$(uname -m)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取当前时间戳
function get_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

function log_info() {
    echo -e "${GREEN}[$(get_timestamp)][Wings][INFO]${NC} $1"
}

function log_warn() {
    echo -e "${YELLOW}[$(get_timestamp)][Wings][WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[$(get_timestamp)][Wings][ERROR]${NC} $1"
}

# wings-control镜像
WINGS_VERSION="${WINGS_VERSION:-26.0.0}"
LICENSE_ENABLED="${LICENSE_ENABLED:-false}"
case "$LICENSE_ENABLED" in
    true|false) ;;
    *) log_error "LICENSE_ENABLED must be 'true' or 'false', got: ${LICENSE_ENABLED}"; exit 2 ;;
esac
REPO="fusionregistry:5000"
# License 构建用独立 tag 后缀,与非 License 版物理隔离:客户 compose 即使
# 拉错/替换镜像,tag 也对不上,不会被无 License 镜像静默顶替。
if [ "$LICENSE_ENABLED" = "true" ]; then
    WINGS_CONTROL_TAG="${REPO}/wings-control:${WINGS_VERSION}-license"
else
    WINGS_CONTROL_TAG="${REPO}/wings-control:${WINGS_VERSION}"
fi

# 根据不同的架构选择基础镜像文件
case $ARCH in
    x86_64|amd64)
        log_info "检测到x86架构"
        # 基础镜像
        BASE_IMG="docker.artifactrepo.wux-g.tools.xfusion.com/docker_universal2/linux/amd64/python:3.10.19-slim"
        # 最终输出文件
        WINGS_CONTROL_FILE="Wings_control_${WINGS_VERSION}_x86_64.tar"
        ;;
    arm|aarch64)
        log_info "检测到ARM架构"
        # 基础镜像
        BASE_IMG="docker.artifactrepo.wux-g.tools.xfusion.com/docker_universal2/linux/arm64/python:3.10.19-slim"
        # 最终输出文件
        WINGS_CONTROL_FILE="Wings_control_${WINGS_VERSION}_aarch64.tar"
        ;;
    *)
        log_error "不支持的架构: ${ARCH}"
        exit 1
        ;;
esac

# 分层构建中间 tag:License 层 FROM 普通镜像叠加,普通 Dockerfile 保持零
# License 逻辑;两份 Dockerfile 的公共内容不重复维护。
WINGS_CONTROL_BASE_TAG="${REPO}/wings-control:${WINGS_VERSION}-base"


function build_wings_control_image(){
    log_info "开始构建Wings Control 镜像，当前CPU架构： ${ARCH}"

    # 导入基础镜像
    log_info "拉取基础镜像: ${BASE_IMG}"
    docker pull ${BASE_IMG} || { log_error "拉取基础镜像失败: ${BASE_IMG}"; exit 1; }

    # 阶段1:普通镜像(单一事实源)。License 构建也以它为底,层缓存下增量很小。
    log_info "构建基础镜像: ${WINGS_CONTROL_BASE_TAG}"
    docker build --build-arg BASE_IMG="${BASE_IMG}" \
                 --build-arg WINGS_VERSION="${WINGS_VERSION}" \
                 --build-arg WINGS_CONTROL_BUILD_DATE=$(date +%Y%m%d_%H%M%S) \
                 -f Dockerfile \
                 -t "${WINGS_CONTROL_BASE_TAG}" . || { log_error "基础镜像构建失败"; exit 1; }

    local dockerfile="Dockerfile"
    local final_tag="${WINGS_CONTROL_BASE_TAG}"
    if [ "$LICENSE_ENABLED" = "true" ]; then
        # 阶段2:License 叠加层(FROM 普通镜像,只含 checker/门禁模块差异)。
        dockerfile="Dockerfile.license"
        final_tag="${WINGS_CONTROL_TAG}"
        log_info "构建License叠加镜像: ${final_tag}"
        docker build --build-arg BASE_IMG="${WINGS_CONTROL_BASE_TAG}" \
                     --build-arg WINGS_VERSION="${WINGS_VERSION}" \
                     --build-arg WINGS_CONTROL_BUILD_DATE=$(date +%Y%m%d_%H%M%S) \
                     -f "$dockerfile" \
                     -t "${final_tag}" . || { log_error "License镜像构建失败"; exit 1; }
    else
        # 普通构建:阶段1的上下文已由 prepare_build_context 清理过 License
        # 资产,基础 tag 直接作为最终交付 tag。
        docker tag "${WINGS_CONTROL_BASE_TAG}" "${WINGS_CONTROL_TAG}" || { log_error "镜像tag失败"; exit 1; }
        docker rmi "${WINGS_CONTROL_BASE_TAG}" >/dev/null 2>&1 || true
    fi

    # 打包镜像
    log_info "打包镜像到: ../output/${WINGS_CONTROL_FILE}"
    docker save "${WINGS_CONTROL_TAG}" -o "${WINGS_CONTROL_FILE}" || { log_error "镜像打包失败"; exit 1; }
    mv "${WINGS_CONTROL_FILE}" ../output/
    log_info "${ARCH}镜像构建完成: ${WINGS_CONTROL_FILE}"
}


function prepare_build_context(){
    # 准备文件：加密脚本、wings-control代码
    # 先清掉上次构建的暂存副本:cp -r 对已存在目录会嵌套复制,且会残留上一次
    # 构建(如非 License 构建删掉的 license_sdk)造成陈旧上下文。
    cp ../compile_wings.sh .
    rm -rf wings_control
    cp -r ../../wings_control .

    # 普通构建的 License 防线在构建上下文完成(普通 Dockerfile 保持零 License
    # 逻辑):删除门禁实现与 License 文档,并固化 build_info 为关闭声明。
    # license_gate.py(Null 直通)与测试不在此列——pipeline 对它的依赖在普通
    # 构建同样需要,关闭场景零影响。
    if [ "$LICENSE_ENABLED" != "true" ]; then
        rm -rf wings_control/license_sdk
        rm -f wings_control/src/wings_ctl/license.py
        rm -f wings_control/docs/features/aiperf-license-design.md
        printf '%s\n\n%s\n' '"""Generated immutable build declarations."""' 'LICENSE_ENABLED = False' \
            > wings_control/src/wings_ctl/build_info.py
    fi
}


function main(){
    cd "$WORK_DIR" && ls -al

    log_info "=========================================="
    log_info "Wings-Control 镜像构建脚本"
    log_info "版本: ${WINGS_VERSION}"
    log_info "架构: ${ARCH}"
    log_info "=========================================="

    prepare_build_context
    build_wings_control_image

    log_info "=========================================="
    log_info "Wings-Control 镜像构建完成"
    log_info "=========================================="
}


main