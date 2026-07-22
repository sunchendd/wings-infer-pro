# =============================================================================
# Wings-Control 统一控制容器 Dockerfile
# 支持引擎: vllm, vllm_ascend, sglang, mindie
# 支持模式: 单机 / 分布式
# 构建命令:
#   docker build -t wings-control:latest wings-control/
#
# 构建产物:
#   - /opt/wings-control/*: Sidecar 后端 Python 代码（config/core/engines/proxy/utils 等）
#   - /opt/wings-control/wings_start.sh: 兼容 wings 接口的启动脚本
#   - /shared-volume: 启动脚本写入目录
# 端口:
#   - 17000: 引擎推理端口
#   - 18000: Proxy 代理
#   - 19000: Health 健康检查
# 启动方式:
#   - CMD 默认使用 wings_start.sh，与 wings 原始容器完全兼容
#   - 也可通过覆盖 CMD 直接运行 python -m wings_control
# =============================================================================
ARG BASE_IMG
FROM ${BASE_IMG}

WORKDIR /opt/wings-control
RUN mkdir /workspace

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV DEBIAN_FRONTEND=noninteractive

# 更换 pip 源
RUN pip config set global.index-url "https://artifactrepo.wux-g.tools.xfusion.com/artifactory/pypi-public/simple" && \
    pip config set global.trusted-host "artifactrepo.wux-g.tools.xfusion.com"

# 更换debian的apt源
RUN echo "Types: deb" > /etc/apt/sources.list.d/debian.sources && \
    echo "URIs: https://mirrors.xfusion.com/debian" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Suites: trixie trixie-updates" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Components: main" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg" >> /etc/apt/sources.list.d/debian.sources 

RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    pciutils \
    procps \
    && rm -rf /var/lib/apt/lists/*

# install wings-control requirements
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 拷贝主要的代码目录
COPY ./wings_control/src  /opt/wings-control/src
COPY ./wings_control/config /opt/wings-control/config
COPY ./wings_control/docs/features /opt/wings-control/docs/features
COPY ./wings_control/pyproject.toml /opt/wings-control/pyproject.toml
COPY ./wings_control/wings_start.sh /opt/wings-control/wings_start.sh
RUN chmod +x /opt/wings-control/wings_start.sh

RUN mkdir -p /shared-volume /var/log/wings

RUN ln -s /opt/wings-control /opt/wings_control

ENV PYTHONPATH="/opt"
ENV APP_WORKDIR="/opt/wings-control"

# 默认启动: bash /opt/wings-control/wings_start.sh（与 wings 原始容器兼容）
# 调试覆盖: docker run wings-control:xxx bash             → 进入 shell
# 直接运行: docker run wings-control:xxx python3 wings_control.py --engine vllm
CMD ["bash", "/opt/wings-control/wings_start.sh"]

# 构建参数
ARG WINGS_VERSION
ARG WINGS_CONTROL_BUILD_DATE

ENV WINGS_VERSION=${WINGS_VERSION} \
    WINGS_CONTROL_BUILD_DATE=${WINGS_CONTROL_BUILD_DATE}

# wings代码加密
COPY ./compile_wings.sh /opt/
RUN bash /opt/compile_wings.sh && \
    rm -rf /opt/compile_wings.sh

# 设置标签
LABEL description="Wings Control Service" \
      version="${WINGS_VERSION}" \
      WINGS_CONTROL_BUILD_DATE=$WINGS_CONTROL_BUILD_DATE

