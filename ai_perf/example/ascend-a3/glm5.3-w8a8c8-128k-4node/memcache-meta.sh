#!/bin/bash
# 独立启动 P0 节点上的 MemCache MetaService。
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE=/tmp/ascend-a3-glm53-dptp-128k.tgz

set -a
source "$HERE/env/common.env"
source "$HERE/env/p0.env"
set +a

mkdir -p "$HERE/logs" "$HERE/rendered/meta"
sed "s/@META_HOST@/$META_NODE/g" "$HERE/memcache/meta/mmc-meta.conf" > "$HERE/rendered/meta/mmc-meta.conf"

LOCAL_IP=""
for _addr in $(hostname -I 2>/dev/null); do
  for _name in "${!NODE_@}"; do
    [ "${!_name}" = "$_addr" ] && { LOCAL_IP="$_addr"; break 2; }
  done
done
[ -n "$LOCAL_IP" ] || echo "NOTICE: this host matches none of the configured NODE_* addresses ($(hostname -I 2>/dev/null)); nodes will be reached over SSH." >&2
if [[ "$NODE_P0" != "$LOCAL_IP" ]]; then
  rm -f "$PACKAGE"
  # Same as memcache-local.sh: rendered/ must ship or the remote node never gets its conf.
  tar czf "$PACKAGE" --exclude=generated --exclude=logs -C "$HERE" .
  scp -o BatchMode=yes -q "$PACKAGE" root@"$NODE_P0:$PACKAGE"
  ssh -o BatchMode=yes root@"$NODE_P0" mkdir -p "$HERE"
  ssh -o BatchMode=yes root@"$NODE_P0" tar xzf "$PACKAGE" -C "$HERE"
fi

COMPOSE=(docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/p0.env" -p glm53-128k-4node-p0)
if [[ "$NODE_P0" == "$LOCAL_IP" ]]; then
  "${COMPOSE[@]}" up -d --force-recreate meta
else
  ssh -o BatchMode=yes root@"$NODE_P0" "${COMPOSE[@]}" up -d --force-recreate meta
fi
