#!/bin/bash
# Start MemCache MetaService on P0.
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE=/tmp/glm53-1m-4node.tgz
set -a
source "$HERE/env/common.env"
source "$HERE/env/p0.env"
set +a
mkdir -p "$HERE/logs" "$HERE/rendered/meta"
sed "s/@META_HOST@/$META_NODE/g" "$HERE/memcache/meta/mmc-meta.conf" > "$HERE/rendered/meta/mmc-meta.conf"
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ "$NODE_P0" != "$LOCAL_IP" ]]; then
  rm -f "$PACKAGE"; tar czf "$PACKAGE" --exclude=generated --exclude=rendered --exclude=logs -C "$HERE" .
  scp -o BatchMode=yes -q "$PACKAGE" root@"$NODE_P0:$PACKAGE"
  ssh -o BatchMode=yes root@"$NODE_P0" mkdir -p "$HERE"
  ssh -o BatchMode=yes root@"$NODE_P0" tar xzf "$PACKAGE" -C "$HERE"
fi
COMPOSE=(docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/p0.env" -p glm53-1m-4node-p0)
if [[ "$NODE_P0" == "$LOCAL_IP" ]]; then "${COMPOSE[@]}" up -d --force-recreate meta; else ssh -o BatchMode=yes root@"$NODE_P0" "${COMPOSE[@]}" up -d --force-recreate meta; fi
