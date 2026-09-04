# Proxy 服务说明

本文说明 wings-control Proxy 的请求转发流程和维护边界。文中的 client 指调用推理接口的客户端，engine 指当前 Pod 中运行的推理服务。模型配置、启动参数和具体推理由其他模块负责。

## 一次请求如何经过 Proxy

收到请求后，Proxy 先判断是否需要协议转换或 RAG 处理，然后排队并转发给 backend engine。返回给 client 的内容包括 engine 状态码、响应体和 Proxy 生成的观测头。

```text
client 请求
    -> 协议转换或 RAG 处理
    -> 排队准入
    -> 请求 backend engine
    -> 必要时重试
    -> 向 client 返回流式或非流式响应
```

并发槽已满时，请求进入本地队列。队列禁用、队列已满且不允许继续等待，或者等待超时，都会返回 503。

## Proxy 处理什么

| 功能 | 处理方式 |
| --- | --- |
| 普通转发 | 校验请求，补充转发头，再发送到对应的 backend 路径。 |
| 流式响应 | 尽快返回首包，后续数据按字节数、时间间隔或 SSE 分隔符刷新。 |
| 非流式响应 | 小响应一次返回；大响应改为分块回传，避免在内存中完整缓存。 |
| 排队准入 | 全局配额按 worker 拆分。请求先尝试可用 Gate，没有空位时进入 FIFO 队列。 |
| 故障重试 | 连接失败、连接超时和部分网关错误可在响应发出前重试。 |
| 可选功能 | Anthropic 转换和 RAG 加速按开关及请求内容决定是否执行。 |

转发头包括鉴权信息、请求 ID 和链路追踪信息。响应保留 engine 的必要响应头，并补充 Pod 名称、排队状态和重试次数。

## 服务运行时做什么

主 Proxy 启动后会创建 HTTP 客户端和本地排队控制器，同时启动健康监控。Gate 可以在准入后立即释放，也可以一直占用到响应结束。前一种方式控制进入速率，后一种方式限制 engine 的实际并发。

独立健康服务使用同一套状态逻辑探测 backend：

```text
探测 engine TCP 端口
    -> 请求 backend 健康接口
    -> 更新启动和连续失败状态
    -> 对外返回 starting / ready / start_failed / degraded
```

TCP 探测结果只用于诊断。对外健康状态以 backend 健康接口为准。健康服务还读取启动进度和加速状态，并代理白名单内的 engine 监控接口。

## 当前边界和错误

业务接口只接收 JSON。不同 engine 的私有字段由调用方处理，Proxy 不做统一转换。

RAG 加速只处理支持的聊天请求。场景不匹配、检测失败或请求明确关闭 RAG 时，走普通转发。Anthropic 转换由开关控制；关闭后，`/v1/messages` 直接转发给 backend。

队列拒绝和等待超时返回 503。backend 连接重试耗尽后返回 502。流式响应开始发送后，如果连接中断，Proxy 不会重新执行整次请求。

健康检查成功只说明 engine 接口当前可用，不代表性能和稳定性已经通过验收。监控代理只开放只读白名单接口。

`health_service.py` 已经包含监控代理。目录中仍保留可独立运行的 `monitor_proxy.py`，是否启动由外部启动流程决定。

## 观测与分工

Proxy 管理转发、排队、重试和健康状态。engine 负责接口语义和推理执行。启动进度与加速状态文件由启动流程写入，健康服务只负责读取。

响应头包含排队时间、当前并发、重试次数和 Pod 名称。Proxy、health 和 backend 连通性问题记录在 `wings_control.log`；engine 执行异常查看 engine 日志。日志位置和排障顺序见[配置、产物与日志](configuration-artifacts-and-logs.md)和[运行维护手册](../operations/maintenance-handover.md)。

`gateway.py` 维护业务转发，`queueing.py` 处理排队，`health_router.py` 和 `health_service.py` 维护健康与监控接口，`anthropic_converter.py` 负责协议转换。接口路径、状态码、响应头、排队语义、重试范围或健康状态发生变化时，需要同步更新文档和测试。
