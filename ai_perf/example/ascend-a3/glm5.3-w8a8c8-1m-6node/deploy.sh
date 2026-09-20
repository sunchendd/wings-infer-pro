#!/bin/bash
# Usage: bash deploy.sh [p0|p1|p2|p3|d0|d1|proxy|all|stop]
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE=/tmp/glm53-1m-6node.tgz
SSH=(ssh -o BatchMode=yes)
SCP=(scp -o BatchMode=yes -q)
NODES=(p0 p1 p2 p3 d0 d1)
set -a
source "$HERE/env/common.env"
set +a
local_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
run_on() { local host=$1; shift; if [[ "$host" == "$local_ip" ]]; then "$@"; else "${SSH[@]}" root@"$host" "$@"; fi; }
node_host() { local key="NODE_${1^^}"; printf '%s' "${!key}"; }
prepare_deploy() { rm -f "$PACKAGE"; tar czf "$PACKAGE" --exclude=generated --exclude=rendered --exclude=logs -C "$HERE" .; }
compose_node() {
  local node=$1 host; shift; host="$(node_host "$node")"
  if [[ "$host" != "$local_ip" ]]; then "${SCP[@]}" "$PACKAGE" root@"$host:$PACKAGE"; run_on "$host" mkdir -p "$HERE"; run_on "$host" tar xzf "$PACKAGE" -C "$HERE"; fi
  run_on "$host" docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/$node.env" -p "glm53-1m-6node-$node" "$@"
}
compose_existing() { local node=$1 host; shift; host="$(node_host "$node")"; run_on "$host" docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/$node.env" -p "glm53-1m-6node-$node" "$@"; }
start_node() { prepare_deploy; compose_node "$1" up -d --force-recreate --wait --wait-timeout 600 control; compose_node "$1" up -d --no-deps --force-recreate engine; }
start_proxy() { prepare_deploy; compose_node p0 up -d --no-deps --force-recreate proxy; }
stop_all() { local failed=0; for node in "${NODES[@]}"; do compose_existing "$node" rm -sf control engine memcache proxy || failed=1; done; compose_existing p0 rm -sf meta || failed=1; return "$failed"; }
case "${1:-}" in
  p0|p1|p2|p3|d0|d1) start_node "$1" ;;
  proxy) start_proxy ;;
  stop) stop_all ;;
  all)
    bash "$HERE/memcache-meta.sh"
    for node in "${NODES[@]}"; do bash "$HERE/memcache-local.sh" "$node"; done
    for node in p1 p3 p0 p2 d1 d0; do start_node "$node"; done
    echo "Engine containers started. Start proxy after all backends are ready: bash $0 proxy"
    ;;
  *) echo "usage: $0 [p0|p1|p2|p3|d0|d1|proxy|all|stop]"; exit 1 ;;
esac
