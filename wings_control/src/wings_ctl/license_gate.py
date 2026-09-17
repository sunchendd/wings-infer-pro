"""License 门禁统一入口 — 所有镜像常驻的协议与工厂。

非 License 镜像构建期会物理删除 ``wings_ctl.license``,因此协议、空实现
和工厂必须放在本常驻模块;pipeline 只经由 ``get_license_gate()`` 取实现,
对 License 零分支感知。真实现 ``LicensePublisher`` 在 ``wings_ctl.license``
(仅 License 镜像存在),License 构建缺模块时 fail-closed。
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Optional, Protocol, Tuple, runtime_checkable

from wings_ctl.build_info import LICENSE_ENABLED
from wings_ctl.core.models import PipelineRequest, ResolvedConfig


@runtime_checkable
class LicenseGate(Protocol):
    """启动产物发布前的 License 门禁契约。

    enforce 在 resolve 之后、产物落盘之前执行;不通过必须抛错终止启动。
    validate_device_count 是 device_count 的前置强校验(CLI 在参数解析后、
    任何依赖 device_count 的校验之前调用),缺失/非正整数直接拒绝。
    invalidate/artifact_dir/lock/publish 负责旧产物清理与发布时序。
    """

    def enforce(self, request: PipelineRequest, resolved: ResolvedConfig) -> None:
        """校验失败必须抛错;方法体仅在 Protocol 定义中为空。"""

    def validate_device_count(self, device_count: object) -> None:
        """device_count 缺失或非正整数时抛错终止;方法体仅在 Protocol 定义中为空。"""

    def invalidate(self, output_dir: Path) -> None:
        """删除 output_dir 下残留的旧启动脚本。"""

    def artifact_dir(self, output_dir: Path) -> Tuple[Path, Optional[int]]:
        """返回 (产物目录, 代际);无代际概念的实现返回 (output_dir, None)。"""

    def lock(self, output_dir: Path):
        """返回产物发布全程持有的锁上下文;无锁需求返回直通 contextmanager。"""

    def publish(self, output_dir: Path, generation: Optional[int], artifact_dir: Path) -> Path:
        """把 artifact_dir 发布为最终交付目录并返回其路径。"""


class NullLicenseGate:
    """非 License 构建的空实现(Null Object):全部方法直通,零副作用。"""

    @staticmethod
    def enforce(request: PipelineRequest, resolved: ResolvedConfig) -> None:
        return None

    @staticmethod
    def validate_device_count(device_count: object) -> None:
        # 普通构建维持现状:device_count 可选(None=不触发 DP 协调),
        # 强校验是 License 特性引入的不兼容变化,不施加给存量调用方。
        return None

    @staticmethod
    def invalidate(output_dir: Path) -> None:
        return None

    @staticmethod
    def artifact_dir(output_dir: Path) -> Tuple[Path, None]:
        return output_dir, None

    @staticmethod
    def lock(output_dir: Path):
        return nullcontext()

    @staticmethod
    def publish(output_dir: Path, generation: None, artifact_dir: Path) -> Path:
        return artifact_dir


def get_license_gate() -> LicenseGate:
    """按构建声明选择门禁实现;License 构建缺 license 模块时 fail-closed。"""
    if not LICENSE_ENABLED:
        return NullLicenseGate()
    try:
        from wings_ctl.license import LicensePublisher
    except ModuleNotFoundError as exc:
        raise ValueError("License-enabled image is missing the License gate") from exc
    return LicensePublisher()


def validate_device_count_early(device_count: object) -> None:
    """CLI 前移的 device_count 强校验(仅 License 构建生效)。

    在参数解析之后、任何依赖 device_count 的校验(尤其 TP-shrink 前置闸)
    之前调用:缺失/非正整数时输出 ``code=2016 status=device_count_unknown``
    结构化日志并抛错终止,消除 device_count=None 落入 TP-shrink 逻辑后
    误导性的 hardware_family 报错。普通构建(Null 门禁)直通,维持现状。
    """
    get_license_gate().validate_device_count(device_count)
