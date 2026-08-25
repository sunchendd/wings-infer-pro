#!/bin/bash

# Wings 镜像构建主脚本
# 依次调用 wings-accel 和 wings-infer 的构建脚本完成整个镜像的构建流程

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


function print_banner() {
    log_info ""
    log_info "=========================================="
    log_info "  Wings 镜像构建主脚本"
    log_info "  版本: ${WINGS_VERSION}"
    log_info "  架构: ${ARCH}"
    log_info "=========================================="
    log_info ""
}


function check_docker() {
    log_info "检查 Docker 环境..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    log_info "Docker 环境检查通过"
}


function build_wings_accel() {
    log_info "=========================================="
    log_info "开始构建 wings-accel 镜像..."
    log_info "=========================================="

    local accel_script="${WORK_DIR}/wings-accel/build_wings_accel.sh"

    if [ ! -f "$accel_script" ]; then
        log_error "wings-accel 构建脚本不存在: $accel_script"
        exit 1
    fi

    # 赋予执行权限
    chmod +x "$accel_script"

    # 执行构建脚本
    if bash "$accel_script"; then
        log_info "wings-accel 镜像构建成功"
    else
        log_error "wings-accel 镜像构建失败"
        exit 1
    fi
}


function build_wings_control() {
    log_info "=========================================="
    log_info "开始构建 wings-control 镜像..."
    log_info "=========================================="

    local control_script="${WORK_DIR}/wings-control/build_wings_control.sh"

    if [ ! -f "$control_script" ]; then
        log_error "wings-control 构建脚本不存在: $control_script"
        exit 1
    fi

    # 赋予执行权限
    chmod +x "$control_script"

    # 执行构建脚本
    if bash "$control_script"; then
        log_info "wings-control 镜像构建成功"
    else
        log_error "wings-control 镜像构建失败"
        exit 1
    fi
}


function print_summary() {
    log_info "=========================================="
    log_info "镜像构建完成！"
    log_info "=========================================="
    log_info "构建的镜像列表:"

    ls -al "${WORK_DIR}/output"

    log_info "=========================================="
}


function package_ai_perf() {
    log_info "打包 ai_perf 目录为 AIPerf_SDK_example.zip ..."

    local ai_perf_dir="${WORK_DIR}/../ai_perf"
    local zip_name="AIPerf_SDK_example.zip"

    if [ ! -d "$ai_perf_dir" ]; then
        log_error "ai_perf 目录不存在: $ai_perf_dir"
        exit 1
    fi

    if [ -f "${WORK_DIR}/output/${zip_name}" ]; then
        rm -f "${WORK_DIR}/output/${zip_name}"
    fi

    cd "${WORK_DIR}/.." || exit 1
    if zip -r "build/output/${zip_name}" "ai_perf"; then
        log_info "create ${zip_name} success"
    else
        log_error "打包 ${zip_name} 失败"
        exit 1
    fi
}


function compose_zip() {
    log_info "compose wings-control image and wings-accel image"

    cd "${WORK_DIR}/output" || log_error "${WORK_DIR}/output 不存在"

    # 如果启用了 --ai_perf，则将 AIPerf_SDK_example.zip 一并打入输出件
    local extra_files=()
    if [ "$AI_PERF" = "1" ]; then
        extra_files+=("AIPerf_SDK_example.zip")
    fi

    if [ -f "Wings_control_${WINGS_VERSION}_x86_64.tar" ]; then
        zip "Wings_infer_${WINGS_VERSION}_x86_64.zip" \
            "Wings_accel_${WINGS_VERSION}_x86_64.tar" \
            "Wings_control_${WINGS_VERSION}_x86_64.tar" \
            "${extra_files[@]}"

        log_info "create Wings_infer_${WINGS_VERSION}_x86_64.zip success"

    elif [ -f "Wings_control_${WINGS_VERSION}_aarch64.tar" ];then
        zip "Wings_infer_${WINGS_VERSION}_aarch64.zip" \
            "Wings_accel_${WINGS_VERSION}_aarch64.tar" \
            "Wings_control_${WINGS_VERSION}_aarch64.tar" \
            "${extra_files[@]}"

        log_info "create Wings_infer_${WINGS_VERSION}_aarch64.zip success"
    else
        log_error "构建有问题，wings-control镜像未构建"
    fi

    # 输出件生成后，清理打入其中的 extra_files 临时文件
    for f in "${extra_files[@]}"; do
        if [ -f "$f" ]; then
            rm -f "$f"
            log_info "cleanup extra file: $f"
        fi
    done
}


function main() {
    # 检查 Docker 环境
    check_docker

    log_info "create tar file"

    # 解析参数：--ai_perf 可选参数（默认关闭），其余位置参数中第一个作为版本号
    AI_PERF=0
    WINGS_VERSION="26.0.0"
    if [ "$#" -gt 0 ]; then
        for arg in "$@"; do
            if [ "$arg" = "--ai_perf" ]; then
                AI_PERF=1
            elif [ "$WINGS_VERSION" = "26.0.0" ]; then
                # 由CI构建控制最终的出包版本（取第一个非 --ai_perf 参数）
                WINGS_VERSION=$arg
            fi
        done
    fi
    export WINGS_VERSION=$WINGS_VERSION
    echo "[Wings][INFO] version: $WINGS_VERSION"
    echo "[Wings][INFO] ai_perf: $AI_PERF"

    print_banner
    build_wings_accel
    build_wings_control

    # 如果启用了 --ai_perf，则先打包 AIPerf_SDK_example.zip 以便并入最终输出件
    if [ "$AI_PERF" = "1" ]; then
        package_ai_perf
    fi

    compose_zip
    print_summary

}


main "$@"