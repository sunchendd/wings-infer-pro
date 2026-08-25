# wings_monitor — 可观测工具组件

基于 **Prometheus + Grafana** 的推理服务监控方案,用于采集、存储并可视化 vLLM 引擎的吞吐量、时延、资源利用率等运行时指标,对服务运行状态进行实时观测。

## 方案介绍

- **Prometheus**:定期抓取 vLLM 暴露的 Metrics 指标，并按照 `scrape_interval` 配置完成采集与时序存储；通过 `relabel_configs` 对指标标签进行映射和重写。
- **Grafana**:基于 Prometheus 数据源构建 vLLM 监控看板（`vllm-dashboard.json`），以多维可视化方式实时呈现服务吞吐量、时延及资源利用率等关键指标。

## 目录结构

```
wings_monitor/
├── README.md                 # 本文档
└── example/                  # 部署示例文件
    ├── docker-compose.yaml   # Prometheus + Grafana 容器编排
    ├── prometheus.yml        # Prometheus 抓取配置
    └── vllm-dashboard.json   # Grafana vLLM 监控看板
```

## 部署步骤

### 1. 准备配置文件

将 `example/` 下的配置放到宿主机固定目录(以下以 `/home/prometheus` 为例):

```bash
mkdir -p /home/prometheus
cp example/prometheus.yml /home/prometheus/prometheus.yml
```

### 2. 修改 Prometheus 抓取目标

编辑 `/home/prometheus/prometheus.yml` ，在 vllm Job 中配置需要监控的 vLLM 实例地址。Prometheus 会按照配置的 scrape_interval 周期性访问目标实例的 /metrics 端点，并采集监控指标。

```yaml
- job_name: 'vllm'
  static_configs:
    - targets: ['<vllm-host>:18000']     # vLLM metrics 默认端口 18000
      labels:
        node: <node-name>
        role: inference
        service: vllm
        cluster: <cluster-name>
```
参数说明：
- targets：Prometheus 抓取目标列表，格式为 `<IP 或域名>:<metrics-port>`。每个目标对应一个 vLLM 实例的 metrics 服务地址。
- node：节点名称或主机标识，用于区分不同推理节点。该值会作为 Prometheus 的 `instance` 标签，并在看板「节点」下拉框中展示。
- role：节点角色标识。对于 vLLM 推理服务，通常配置为 inference。当前作为通用业务标识，看板暂未按此过滤。
- service：服务名称标识，建议统一配置为 vllm，用于区分不同业务组件。当前作为通用业务标识，看板暂未按此过滤。
- cluster：集群名称，用于标识节点所属集群。注意：当前看板查询中写死 `cluster="ai-cluster-1"`，新增集群时需同步新增看板并修改过滤条件。

### 3. 启动 Prometheus + Grafana

`example/docker-compose.yaml` 已预配置 Prometheus 和 Grafana 服务，并将宿主机的 `/home/prometheus/prometheus.yml` 挂载到 Prometheus 容器中。完成配置后，可通过以下命令启动监控组件：

```bash
cd example
docker compose up -d
```
启动成功后，可通过以下地址访问服务：

- **Prometheus**：`http://<host-IP>:9090`
  - 用于查看监控目标状态、抓取结果及指标采集情况。

- **Grafana**：`http://<host-IP>:3000`
  - 用于查看监控数据的可视化面板和预置的 vLLM 监控看板。
  - 默认用户名：`admin`
  - 默认密码：`admin`
  - 首次登录后会提示修改初始密码。

> Grafana 数据目录通过命名卷 `grafana-data` 持久化存储，容器重启后不会丢失看板、数据源及用户配置。

## 使用方法

### 1. 添加 Prometheus 数据源

1. 登录 Grafana,进入 **Connections → Data sources → Add data source**。
2. 选择 **Prometheus**,URL 填 `http://<prometheus-host>:9090`。
3. 点击 **Save & Test**,确认连通。

### 2. 导入 vLLM 看板

1. **Dashboards → New → Import**,上传 `example/vllm-dashboard.json`。
2. 看板依赖 `DS_PROMETHEUS` 数据源,导入时选择上一步新建的 Prometheus。
3. 顶部 `Model`(对应 `$model_name`)与 `节点`(对应 `$node`)下拉框用于筛选模型与节点,默认展示所有。

### 3. 查看监控

1. 进入 **Dashboards** 页面。
2. 打开导入的 **vLLM Dashboard**。
3. 通过顶部的 `Model` 和 `节点` 筛选器查看指定模型或节点的监控数据。`节点` 筛选器支持多选及「All」(匹配全部节点),可用于对比多台机器或汇总整个集群。

> 若看板无数据，请检查 Prometheus 是否已成功抓取 vLLM 的 `/metrics` 指标，并确认对应 Target 状态为 **UP**。

## 注意事项

- **端口配置**：确保 `9090`（Prometheus）和 `3000`（Grafana）端口未被占用；如有冲突，可修改 `docker-compose.yaml` 中的端口映射。
- **网络连通性**：Prometheus 需能够访问 vLLM 的 `/metrics` 端点；跨主机部署时请确认网络策略、防火墙及安全组配置正确。
- **安全配置**：生产环境建议修改 Grafana 默认密码，并通过 HTTPS 和统一认证机制保护访问入口。