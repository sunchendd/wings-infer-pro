# DeepSeek-V4-Pro-w4a8-1m-4node deployment example

DeepSeek-V4-Pro-w4a8 1M-context PD disaggregation on Ascend A3: P0/P1 prefill + D0/D1 decode
(DP2/TP16 per role), Mooncake KV transfer, proxy on P0 port `8000`.

## Usage

Edit `env/common.env` (image, model path) and `env/<node>.env` (node IPs), then:

```bash
bash deploy.sh image   # distribute images to all nodes
bash deploy.sh all     # start every engine node, then the proxy
```

Restart a single node: `bash deploy.sh <p0|p1|d0|d1>`; stop all: `bash deploy.sh stop`.
