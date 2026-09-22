#!/bin/bash
# 独立启动指定 P/D 节点上的 MemCache LocalService。
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE=${1:-}
PACKAGE=/tmp/ascend-a3-glm53-dptp-128k.tgz

case "$NODE" in
  p0|p1|d0|d1) ;;
  *) echo "usage: $0 [p0|p1|d0|d1]"; exit 1 ;;
esac

set -a
source "$HERE/env/common.env"
source "$HERE/env/$NODE.env"
set +a

HOST_KEY="NODE_${NODE^^}"
HOST=${!HOST_KEY}
mkdir -p "$HERE/logs" "$HERE/rendered/local-service" "$HERE/rendered/model-client"
# Only the meta address is rendered; per-node UBS IO disk settings stay in the conf file.
sed "s/@META_HOST@/$META_NODE/g" "$HERE/memcache/local-service/mmc-local.conf" > "$HERE/rendered/local-service/mmc-local.conf"
sed "s/@META_HOST@/$META_NODE/g" "$HERE/memcache/model-client/mmc-local.conf" > "$HERE/rendered/model-client/mmc-local.conf"

LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
# Refuse missing or mounted devices: UBS IO owns the raw disk and destroys existing data on it.
disk_path="$(sed -n 's/^ubsio.disk.path *= *//p' "$HERE/rendered/local-service/mmc-local.conf" | head -n1)"
[[ -n "$disk_path" ]] || { echo "ubsio.disk.path is missing in memcache/local-service/mmc-local.conf" >&2; exit 1; }
for disk in ${disk_path//:/ }; do
  [[ "$disk" == /dev/* ]] || { echo "Invalid ubsio.disk.path entry: $disk" >&2; exit 1; }
  if [[ "$HOST" == "$LOCAL_IP" ]]; then
    [[ -b "$disk" ]] || { echo "UBS IO block device not found: $disk" >&2; exit 1; }
    if lsblk -nrpo MOUNTPOINTS "$disk" | grep -q '[^[:space:]]'; then
      echo "Refusing to use mounted UBS IO device: $disk" >&2; exit 1
    fi
  else
    ssh -o BatchMode=yes root@"$HOST" "test -b $disk" || { echo "UBS IO block device not found on $HOST: $disk" >&2; exit 1; }
    if ssh -o BatchMode=yes root@"$HOST" "lsblk -nrpo MOUNTPOINTS $disk" | grep -q '[^[:space:]]'; then
      echo "Refusing to use mounted UBS IO device on $HOST: $disk" >&2; exit 1
    fi
  fi
done
if [[ "$HOST" != "$LOCAL_IP" ]]; then
  rm -f "$PACKAGE"
  tar czf "$PACKAGE" --exclude=generated --exclude=rendered --exclude=logs -C "$HERE" .
  scp -o BatchMode=yes -q "$PACKAGE" root@"$HOST:$PACKAGE"
  ssh -o BatchMode=yes root@"$HOST" mkdir -p "$HERE"
  ssh -o BatchMode=yes root@"$HOST" tar xzf "$PACKAGE" -C "$HERE"
fi

COMPOSE=(docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/$NODE.env" -p "glm53-128k-4node-$NODE")
if [[ "$HOST" == "$LOCAL_IP" ]]; then
  "${COMPOSE[@]}" up -d --force-recreate memcache
else
  ssh -o BatchMode=yes root@"$HOST" "${COMPOSE[@]}" up -d --force-recreate memcache
fi
