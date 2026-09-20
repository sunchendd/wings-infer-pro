#!/bin/bash
# Start MemCache LocalService on one P/D node.
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE=${1:-}
PACKAGE=/tmp/glm53-128k-6node.tgz
case "$NODE" in
  p0|p1|p2|p3|d0|d1) ;;
  *) echo "usage: $0 [p0|p1|p2|p3|d0|d1]"; exit 1 ;;
esac
if [[ ! -f "$HERE/env/$NODE.env" ]]; then echo "Node $NODE is not part of this example" >&2; exit 1; fi
set -a
source "$HERE/env/common.env"
source "$HERE/env/$NODE.env"
set +a
HOST_KEY="NODE_${NODE^^}"
HOST=${!HOST_KEY}
mkdir -p "$HERE/logs" "$HERE/rendered/local-service" "$HERE/rendered/model-client"
sed "s/@META_HOST@/$META_NODE/g" "$HERE/memcache/local-service/mmc-local.conf" > "$HERE/rendered/local-service/mmc-local.conf"
sed "s/@META_HOST@/$META_NODE/g" "$HERE/memcache/model-client/mmc-local.conf" > "$HERE/rendered/model-client/mmc-local.conf"
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ "$HOST" != "$LOCAL_IP" ]]; then
  rm -f "$PACKAGE"; tar czf "$PACKAGE" --exclude=generated --exclude=rendered --exclude=logs -C "$HERE" .
  scp -o BatchMode=yes -q "$PACKAGE" root@"$HOST:$PACKAGE"
  ssh -o BatchMode=yes root@"$HOST" mkdir -p "$HERE"
  ssh -o BatchMode=yes root@"$HOST" tar xzf "$PACKAGE" -C "$HERE"
fi
COMPOSE=(docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/$NODE.env" -p "glm53-128k-6node-$NODE")
if [[ "$HOST" == "$LOCAL_IP" ]]; then "${COMPOSE[@]}" up -d --force-recreate memcache; else ssh -o BatchMode=yes root@"$HOST" "${COMPOSE[@]}" up -d --force-recreate memcache; fi
