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
mkdir -p "$HERE/logs" "$HERE/rendered/local-service/$NODE" "$HERE/rendered/model-client"
# Nodes with different UBS IO disks or memory tiers ship a per-node override
# mmc-local.conf.<node>; nodes with identical hardware share the plain mmc-local.conf.
# Only the meta address is rendered; per-node UBS IO disk settings stay in the conf file.
LOCAL_SRC="$HERE/memcache/local-service/mmc-local.conf.$NODE"
[ -f "$LOCAL_SRC" ] || LOCAL_SRC="$HERE/memcache/local-service/mmc-local.conf"
sed "s/@META_HOST@/$META_NODE/g" "$LOCAL_SRC" > "$HERE/rendered/local-service/$NODE/mmc-local.conf"
sed "s/@META_HOST@/$META_NODE/g" "$HERE/memcache/model-client/mmc-local.conf" > "$HERE/rendered/model-client/mmc-local.conf"
LOCAL_IP=""
for _addr in $(hostname -I 2>/dev/null); do
  for _name in "${!NODE_@}"; do
    [ "${!_name}" = "$_addr" ] && { LOCAL_IP="$_addr"; break 2; }
  done
done
[ -n "$LOCAL_IP" ] || echo "NOTICE: this host matches none of the configured NODE_* addresses ($(hostname -I 2>/dev/null)); nodes will be reached over SSH." >&2
# Refuse missing or mounted devices: UBS IO owns the raw disk and destroys existing data on it.
disk_path="$(sed -n 's/^ubsio.disk.path *= *//p' "$HERE/rendered/local-service/$NODE/mmc-local.conf" | head -n1)"
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
  # rendered/ must ship with the package: the remote memcache and the engine model-client
  # read $HERE/rendered/... at startup and nothing regenerates them on the remote node.
  rm -f "$PACKAGE"; tar czf "$PACKAGE" --exclude=generated --exclude=logs -C "$HERE" .
  scp -o BatchMode=yes -q "$PACKAGE" root@"$HOST:$PACKAGE"
  ssh -o BatchMode=yes root@"$HOST" mkdir -p "$HERE"
  ssh -o BatchMode=yes root@"$HOST" tar xzf "$PACKAGE" -C "$HERE"
fi
COMPOSE=(docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/$NODE.env" -p "glm53-128k-6node-$NODE")
if [[ "$HOST" == "$LOCAL_IP" ]]; then "${COMPOSE[@]}" up -d --force-recreate memcache; else ssh -o BatchMode=yes root@"$HOST" "${COMPOSE[@]}" up -d --force-recreate memcache; fi
