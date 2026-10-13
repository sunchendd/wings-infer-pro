"""Allow running as `python -m wings_ctl`.

启动入口：
1. 首先调用 cli.py:main() 进行配置解析和脚本生成
2. 然后调用 wings_control.py:run() 启动 proxy 服务
"""

import os
import shutil
import sys


def _mock_fcntl_on_windows_dry_run() -> None:
    """Windows 上 mock fcntl，使 dry-run 能导入 env_utils。

    fcntl 是 Unix-only 模块，仅 env_utils.get_interface_for_ip 用 fcntl.ioctl
    查询网卡 IP。Windows 上不存在该模块，直接导入会失败，导致整个 wings_ctl
    （含 dry-run）无法启动。这里在导入 cli（进而导入 env_utils → import fcntl）
    之前，向 sys.modules 注入一个 ioctl 恒抛 OSError 的占位模块，使
    get_interface_for_ip 走既有 OSError 分支回退到默认网卡，不改变 Linux 行为。

    仅 Windows + dry-run 生效；正常启动（非 dry-run）不 mock，保持原样。
    """
    if sys.platform != "win32" or "--dry-run" not in sys.argv:
        return
    import types

    _fcntl = types.ModuleType("fcntl")

    def _ioctl(*_args, **_kwargs):
        raise OSError("fcntl.ioctl is not available on this platform")

    _fcntl.ioctl = _ioctl
    sys.modules["fcntl"] = _fcntl


_mock_fcntl_on_windows_dry_run()

from wings_ctl.cli import main

if __name__ == "__main__":
    # 如果是 dry-run 模式，只打印参数不启动服务
    if "--dry-run" in sys.argv:
        sys.exit(main())

    # 正常模式：先调用 cli.main() 生成配置
    main()

    # 自动检测可用的 Python 解释器（优先 python3，回退 python）
    if not os.environ.get("PYTHON_BIN"):
        for candidate in ("python3", "python"):
            if shutil.which(candidate):
                os.environ["PYTHON_BIN"] = candidate
                break

    # 然后启动 proxy 服务
    from wings_ctl.wings_control import run
    sys.exit(run())
