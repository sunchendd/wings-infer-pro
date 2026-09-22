# GLM-5.3-w8a8c8-1m-6node deployment example

Source: `45-46-47-48-glm5.3-0.26.0.rc1-1M` role parameters (2026-09 refresh, aligned with the four-node 1M recipe).

- Prefill: two independent DP2/TP16 Prefill instances (P0/P1 and P2/P3).
- Decode: one DP4/TP8 Decode instance (D0/D1).
- Every host uses 16 Ascend NPU devices.
- `This example starts MemCache Meta/Local services before engines.`
- MemCache spills evicted KV to SSD via UBS IO; edit `ubsio.disk.path` in `memcache/local-service/mmc-local.conf` on each node to that node's dedicated unmounted block devices.
- Proxy runs on P0 port `8000`.

## Configure

Update `env/common.env` and every `env/<node>.env`; all `192.0.2.x` addresses are documentation placeholders.
The control image must contain exact variant `GLM-5.3-w8a8c8-1m-6node`.
License enforcement requires the `-license` suffixed control image and, on every node, exactly one `*.xml` certificate under `/etc/aiperf/license` (certificate/SafeTime mounts, per-node used-card self-check and ESN anti-spoof mounts are built into docker-compose.yaml).

## Start

```bash
cd ai_perf/example/ascend-a3/glm5.3-w8a8c8-1m-6node
# Optional first step: distribute images. Targets default to all nodes; pass a comma-separated
# node list to restrict, and/or saved archives as comma-separated absolute paths:
#   bash deploy.sh image                                        # all nodes, export images from env/common.env
#   bash deploy.sh image p0,p1                                  # only p0 and p1
#   bash deploy.sh image p0,p1 /abs/engine.tar.gz,/abs/control.tar.gz
bash deploy.sh image
bash deploy.sh all
```

`all` starts Meta, every LocalService, every engine node, then the proxy; the proxy itself waits for all backends
to accept connections before serving (`PROXY_BACKEND_TIMEOUT`, default 3600s).

After MetaService and every LocalService are running, an individual node's Control/Engine containers may be
started with `bash deploy.sh <node>`, where nodes are: `p0 p1 p2 p3 d0 d1`. This command does not start MemCache.
Stop all services with `bash deploy.sh stop`.

## Expected ranks

- Each Prefill logical instance has ranks `0,1`.
- 128K Decode ranks are `0..7`; 1M Decode ranks are `0..3`.
- In six-node examples P0/P1 and P2/P3 are separate Prefill logical instances; they are not one DP4 instance.
