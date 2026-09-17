# License SDK 资产地图

AIPerf License 的代码、文档、依赖分布在本仓库多个位置,由构建边界和
仓库规范决定(见下表)。本文件是唯一导航入口:找任何 license 资产从这里查。

| 资产 | 位置 | 说明 |
| --- | --- | --- |
| 门禁实现(唯一真实现) | `wings_control/src/wings_ctl/license.py` | 证书唯一性、checker 调用、配额、错误码、结构化日志;仅 License 镜像携带(普通镜像构建期 `rm` 删除) |
| 门禁协议/工厂(常驻) | `wings_control/src/wings_ctl/license_gate.py` | `LicenseGate` Protocol + `NullLicenseGate` + fail-closed 工厂 + `validate_device_count_early`(CLI 前移的 2016 强校验入口);两种镜像都必须存在,故独立于 `license.py` |
| 构建声明 | `wings_control/src/wings_ctl/build_info.py` | `LICENSE_ENABLED` 常量;构建期由 Dockerfile 按模式改写,源码树恒为 `False` |
| C 侧 SDK(本目录) | `wings_control/license_sdk/` | checker.c、build.sh、encrypt_key.py、产品 Key;AdaptiveLM/libboundscheck 构建期从内部制品仓库下载,不入 git |
| 镜像构建 | `build/wings-control/Dockerfile.license` | 分层构建:FROM 普通镜像叠加 checker/license 模块,产出 `-license` tag |
| 镜像构建脚本 | `build/wings-control/build_wings_control.sh` | `LICENSE_ENABLED=true` 时先出普通 tag 再叠加 license 层 |
| 宿主机工具 | `ai_perf/license/` | `aiperf.py` 总入口(license show 等)+ `aiperf.json` 配置;随示例包统一分发(License 挂载已内置 example compose) |
| 设计文档 | `wings_control/docs/features/aiperf-license-design.md` | 流程/校验规则/错误码/威胁模型(docs/ 为唯一权威文档体系) |
| 单元测试 | `wings_control/tests/unit/test_license_gate.py` `test_license_quota.py` | 工厂/协议与配额编排(tests/ 为唯一测试体系) |
| CLI 参数 | `wings_control/src/wings_ctl/cli.py` 的 `--license-file` | CLI 表面归 CLI 管;请求字段 `PipelineRequest.license_file` 定义于 core/models.py |

## 为什么不物理合并成一个目录

- Python 模块必须在 `src/wings_ctl/` 包内(wheel 打包与 import 路径约束);
  `license_gate.py` 不能并进 `license.py`(普通镜像删除后者,前者必须常驻)。
- 文档必须在 `docs/`(仓库唯一权威文档体系);测试必须在 `tests/`(仓库测试规范)。
- C SDK 与 Python 代码生命周期不同(构建期 vs 运行期),独立目录即其聚合。
