# GLM-5.3-w8a8c8-128k-6node deployment example

Source: `41-42-43-44-45-46-glm5.3-w8a8c8-mtp-128k.zip`.

- Prefill: two independent DP2/TP16 Prefill instances (P0/P1 and P2/P3).
- Decode: one DP8/TP4 Decode instance (D0/D1).
- Every host uses 16 Ascend NPU devices.
- The recipe uses Mooncake for P/D transfer and AscendStore backed by MemCache.
- MemCache spills evicted KV to SSD via UBS IO. Each node reads its own
  `memcache/local-service/mmc-local.conf.<node>` (`p0`/`p1`/`d0`/`d1`, shipped as copies of the shared
  `mmc-local.conf`): set that node's dedicated unmounted `ubsio.disk.path` devices there and, when hosts
  differ in RAM, the DRAM/L2.5 tier sizes. Delete a node's file to fall back to the shared `mmc-local.conf`.
- P0 runs MetaService; every P/D host runs one LocalService.
- Proxy runs on P0 port `8000`.

## Prerequisites (every host)

- Docker 26+ with the Compose v2 plugin at v2.20 or newer (`--wait-timeout` requires it). Offline install: `ai_perf/install/`.
- Passwordless root SSH from P0 to every other node; the deploy scripts use `ssh -o BatchMode=yes`.
- Model weights present on every node at `MODEL_PATH`, and both images named in `env/common.env` loadable.
- Hosts must be clean (or rebooted) if engines were force-killed before — see Operational notes.
- If `/tmp` is tmpfs-backed, point `IMAGE_ARCHIVE` at a disk-backed path before `deploy.sh image`; the export is tens of GB.

## Configure

Update `env/common.env` and every `env/<node>.env`; all `192.0.2.x` addresses are documentation placeholders.
The control image must contain exact variant `GLM-5.3-w8a8c8-128k-6node`.
License enforcement requires the `-license` suffixed control image and, on every node, exactly one `*.xml` certificate under `/etc/aiperf/license` (certificate/SafeTime mounts, per-node used-card self-check and ESN anti-spoof mounts are built into docker-compose.yaml).

## Start

```bash
cd ai_perf/example/ascend-a3/glm5.3-w8a8c8-128k-6node
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


## Operational notes

- `all` starts MemCache before the engines on purpose: the DRAM tier must win the host
  memory race, so never interrupt a LocalService mid-initialization.
- Restart engines pairwise: the two sides of each Prefill (or Decode) group rendezvous at
  startup, and restarting one side makes the other side's wait abort.
- If the proxy gives up waiting for backends (`PROXY_BACKEND_TIMEOUT`, default 3600s),
  just run `bash deploy.sh proxy` again.
- SIGKILLed engines can leak CANN devmm pinned pages. If a node's MemCache then fails its
  DRAM allocation (dmesg `alloc_contig_range: PFNs busy`), reboot that node before redeploying.

## Expected ranks

- Each Prefill logical instance has ranks `0,1`.
- 128K Decode ranks are `0..7`; 1M Decode ranks are `0..3`.
- In six-node examples P0/P1 and P2/P3 are separate Prefill logical instances; they are not one DP4 instance.
