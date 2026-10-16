# GLM-5.3-w8a8c8-128k-6node 部署示例

来源：`41-42-43-44-45-46-glm5.3-w8a8c8-mtp-128k.zip`。

- Prefill：两个独立的 DP2/TP16 Prefill 实例（P0/P1 与 P2/P3）。
- Decode：一个 DP8/TP4 Decode 实例（D0/D1）。
- 每台主机使用 16 张昇腾 NPU。
- P/D 传输使用 Mooncake，KV 卸载使用 MemCache 支撑的 AscendStore。
- MetaService 运行在 P0；每个 P/D 主机各运行一个 LocalService。
- MemCache 将被驱逐的 KV 经 UBS IO 落到 SSD。每个节点读取自己的
  `memcache/local-service/mmc-local.conf.<节点名>`（`p0`/`p1`/`p2`/`p3`/`d0`/`d1`，随包附带、内容为共用版
  `mmc-local.conf` 的拷贝）：在其中填写该节点专用的未挂载 `ubsio.disk.path` 裸盘，各台内存不一致时
  再调整 DRAM/L2.5 分层大小。删掉某节点的文件即回退共用版 `mmc-local.conf`。
- Proxy 运行在 P0 的 `8000` 端口。

## 前置条件（每台主机）

- Docker 26+ 且 Compose v2 插件不低于 v2.20（`--wait-timeout` 依赖此版本）；离线安装见 `ai_perf/install/`。
- P0 到其余各节点 root 免密 SSH（部署脚本全程使用 `ssh -o BatchMode=yes`）。
- 每台主机的 `MODEL_PATH` 路径下已放好模型权重，`env/common.env` 指定的两个镜像可加载。
- 之前强杀过引擎的主机必须处于干净状态（或重启过）——见"运维注意事项"。
- 若 `/tmp` 是 tmpfs，执行 `deploy.sh image` 前把 `IMAGE_ARCHIVE` 指到磁盘路径；镜像导出有几十 GB。

## 第 1 步 — 放置 License 证书（每台主机）

证书按主机 ESN（= `/sys/class/dmi/id/board_serial`）签发：每台放**自己的**那份 `*.xml`，
`/etc/aiperf/license/` 下有且只有一份。不要把一台的证书拷给另一台。

```bash
mkdir -p /etc/aiperf/license && rm -f /etc/aiperf/license/*.xml
cp /path/to/<本机证书>.xml /etc/aiperf/license/
```

## 第 2 步 — 导入镜像并配置

**每台主机**导入镜像，并把 control 镜像 tag 对齐 `env/common.env`：

```bash
docker load -i AIPerf_control_26.0.1.tar
docker load -i wings-vllm-ascend-glm53-a3-20260913015609.tar
docker tag aiperf-control:26.0.1 fusionregistry:5000/wings-control:26.0.2-license
```

（`AIPerf_accel_26.0.1.tar` 本示例不引用，可不导入。若你的 `CONTROL_IMAGE` 不同，`docker tag`
的目标名随之调整。）

然后**只在 P0 上**配置部署树（树只需要放 P0，`deploy.sh` 会自动推送到其余节点）：

- `env/common.env` 和每个 `env/<node>.env`：把 `192.0.2.x` 文档占位地址换成真实 IP，设置
  `MODEL_PATH`、引擎与 control 镜像。control 镜像必须包含精确的 `glm5.3-w8a8c8-128k-6node`
  variant；License 门禁要求 `-license` 后缀的 control 镜像（证书/SafeTime 挂载、每节点已用卡数
  自查与 ESN 防伪挂载已内置于 docker-compose.yaml）。
- 每节点的 `memcache/local-service/mmc-local.conf.<node>`：填写该节点专用的未挂载 UBS IO 裸盘
  与内存分层大小（无节点文件的节点回退共用版 `mmc-local.conf`）。

## 第 3 步 — 拉起

在 P0 的示例目录执行：

```bash
bash deploy.sh all
```

`all` 依次启动 Meta、每个节点的 LocalService、每个节点的引擎，最后启动 proxy；proxy 会等所有
backend 可连接后才开始服务（`PROXY_BACKEND_TIMEOUT`，默认 3600s）。首次拉起每台要加载约 711GB
权重，预计 15-30 分钟。

可选：向缺少镜像的节点分发镜像（默认目标为全部节点；可用逗号分隔的节点列表限定范围，
`/` 开头的逗号分隔参数直接加载离线镜像包）：

```bash
bash deploy.sh image                                        # 全部节点，按 env/common.env 导出镜像
bash deploy.sh image p0,p1                                  # 仅 p0 和 p1
bash deploy.sh image p0,p1 /abs/engine.tar.gz,/abs/control.tar.gz
```

Meta 和所有 LocalService 运行之后，单个节点的 Control/Engine 容器可用 `bash deploy.sh <node>`
启动，节点为 `p0 p1 p2 p3 d0 d1`；该命令不会启动 MemCache。全部停止用 `bash deploy.sh stop`。

## 第 4 步 — 验证

```bash
curl -s http://<NODE_P0>:8000/v1/models
# 预期返回：GLM-5.3-w8a8c8

curl -s http://<NODE_P0>:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"GLM-5.3-w8a8c8","messages":[{"role":"user","content":"你好，请做个自我介绍"}],"max_tokens":64}'
# 预期返回：正常补全
```

## 运维注意事项

- `all` 有意在引擎之前启动 MemCache：DRAM 分层必须抢先拿到主机内存，
  因此不要打断正在初始化的 LocalService。
- 引擎要成对重启（P0 配 P1、P2 配 P3，D0 配 D1）：两侧在启动时互为集合点，只重启一侧会导致另一侧的等待中断退出。
- proxy 等待 backend 超时（`PROXY_BACKEND_TIMEOUT`，默认 3600s）后，
  再执行一次 `bash deploy.sh proxy` 即可。
- 被 SIGKILL 的引擎会泄漏 CANN devmm 钉死页。若某节点 MemCache 随后 DRAM 分配失败
  （dmesg 出现 `alloc_contig_range: PFNs busy`），重新部署前先重启该节点。

## 预期 rank 布局

- 每个 Prefill 逻辑实例的 rank 为 `0,1`。
- 128K Decode 的 rank 为 `0..7`；1M Decode 的 rank 为 `0..3`。
- 六节点示例中 P0/P1 与 P2/P3 是两个独立的 Prefill 逻辑实例，不是同一个 DP4 实例。
