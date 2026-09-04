# wings-control 文档

本目录提供开发、MaaS 对接和运维中需要长期遵循的规则。代码层面的细节以源码、测试和实际生成文件为准。

## 按任务阅读

| 任务 | 文档 |
| --- | --- |
| MaaS 参数、PD 字段、placement 和端口 | [MaaS 接口参数契约](guideline/Maas侧与wins-control侧交互接口参数锲约说明.md) |
| 已支持能力、限制和验证边界 | [支持边界](capabilities/support-boundaries.md) |
| 启动脚本、审计、日志和共享卷文件 | [配置、产物与日志](contracts/configuration-artifacts-and-logs.md) |
| Proxy 请求转发、排队、健康和监控 | [Proxy 服务](contracts/proxy-service.md) |
| Wings Accel 输入、返回内容、安装和启动前命令 | [Wings Accel 接口](contracts/wings-accel-interface.md) |
| 配置匹配、来源追踪、并行度和回退规则 | [TP/DP 并行策略](policies/parallelism-and-resolution.md) |
| 部署检查、排障、验收和回退 | [运行维护手册](operations/maintenance-handover.md) |
| 开发、测试和提交要求 | [开发与提交要求](development/development-and-contribution.md) |

## 维护规则

- 修改外部字段、输出文件、错误行为或兼容语义时，同时更新对应文档和测试。
- 新增、拆分、替代或废弃正式文档时，必须同步更新本页的阅读入口。优先更新已有权威文档；只有现有文档无法清楚说明一项独立、稳定的规则时，才新增文档。
- 同一事实只在一篇文档中维护；其他文档只说明入口或链接，不重复规则。
- 文档与代码冲突时，先核对测试和实际产物，再修正文档或代码；不要静默改变对外承诺。
