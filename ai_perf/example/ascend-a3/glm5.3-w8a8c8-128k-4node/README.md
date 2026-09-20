# GLM-5.3-w8a8c8-128k-4node deployment example

Source: `20260910_128k-dptp.zip`.

- Prefill: one DP2/TP16 Prefill instance (P0/P1).
- Decode: one DP8/TP4 Decode instance (D0/D1).
- Every host uses 16 Ascend NPU devices.
- `This example starts MemCache Meta/Local services before engines.`
- Proxy runs on P0 port `8000`.

## Configure

Update `env/common.env` and every `env/<node>.env`; all `192.0.2.x` addresses are documentation placeholders.
The control image must contain exact variant `GLM-5.3-w8a8c8-128k-4node`.

## Start

```bash
cd ai_perf/example/ascend-a3/glm5.3-w8a8c8-128k-4node
bash deploy.sh all
# After all backends are healthy:
bash deploy.sh proxy
```

After MetaService and every LocalService are running, an individual node's Control/Engine containers may be
started with `bash deploy.sh <node>`, where nodes are: `p0 p1 d0 d1`. This command does not start MemCache.
Stop all services with `bash deploy.sh stop`.

## Expected ranks

- Each Prefill logical instance has ranks `0,1`.
- 128K Decode ranks are `0..7`; 1M Decode ranks are `0..3`.
- In six-node examples P0/P1 and P2/P3 are separate Prefill logical instances; they are not one DP4 instance.
