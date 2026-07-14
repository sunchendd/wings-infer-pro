"""Allow running as `python -m wings_ctl`.

启动入口：
1. 首先调用 cli.py:main() 进行配置解析和脚本生成
2. 然后调用 wings_control.py:run() 启动 proxy 服务
"""

import os
import shutil
import sys

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
