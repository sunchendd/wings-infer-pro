#!/bin/bash
# Usage: bash deploy.sh [meta|memcache <node>|image [nodes] [archives]|p0|p1|d0|d1|proxy|all|stop]
#   image                      distribute ENGINE_IMAGE/CONTROL_IMAGE to all nodes
#                              (pull missing locally, save+gzip, scp + docker load where lacking)
#   image p0,p1 [/a.tar.gz]    restrict to comma-separated nodes; /-prefixed args are comma-separated
#                              saved-image archives loaded directly (docker load is idempotent)
#   IMAGE_ARCHIVE=/path/f.tgz  local export path override for the auto save+gzip branch
#                              (default /tmp/wings-images.tar.gz; move it off tmpfs-backed /tmp)
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE=/tmp/glm53-128k-4node.tgz
SSH=(ssh -o BatchMode=yes)
SCP=(scp -o BatchMode=yes -q)
NODES=(p0 p1 d0 d1)
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
  run_on "$host" docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/$node.env" -p "glm53-128k-4node-$node" "$@"
}
compose_existing() { local node=$1 host; shift; host="$(node_host "$node")"; run_on "$host" docker compose --project-directory "$HERE" --env-file "$HERE/env/common.env" --env-file "$HERE/env/$node.env" -p "glm53-128k-4node-$node" "$@"; }
start_node() { prepare_deploy; compose_node "$1" up -d --force-recreate --wait --wait-timeout 600 control; compose_node "$1" up -d --no-deps --force-recreate engine; }
start_proxy() { prepare_deploy; compose_node p0 up -d --no-deps --force-recreate proxy; }
stop_all() { local failed=0; for node in "${NODES[@]}"; do compose_existing "$node" rm -sf control engine memcache proxy || failed=1; done; compose_existing p0 rm -sf meta || failed=1; return "$failed"; }
# Distribute images to selected nodes (default: all).
#   image [nodes] [archives]
#     nodes    comma-separated node names, e.g. p0 or p0,p1; defaults to all nodes
#     archives comma-separated absolute paths of saved-image archives; when omitted, the images
#              configured in env/common.env are exported locally (missing ones pulled first)
load_images() {
  local packs="" nodes_arg="" arg
  for arg in "$@"; do
    if [[ "$arg" == /* ]]; then packs="$arg"; else nodes_arg="$arg"; fi
  done
  local nodes=() node
  if [[ -n "$nodes_arg" ]]; then
    IFS=',' read -r -a nodes <<< "$nodes_arg"
    for node in "${nodes[@]}"; do
      if [[ " ${NODES[*]} " != *" $node "* ]]; then
        echo "ERROR: unknown node '$node' (valid: ${NODES[*]})" >&2
        exit 1
      fi
    done
  else
    nodes=("${NODES[@]}")
  fi
  # IMAGE_ARCHIVE overrides the local export path: /tmp may be tmpfs-backed, where a
  # tens-of-GB archive exhausts memory instead of disk.
  local archive="${IMAGE_ARCHIVE:-/tmp/wings-images.tar.gz}" host pack remote
  local images=() archives=()
  if [[ -n "$packs" ]]; then
    IFS=',' read -r -a archives <<< "$packs"
    for pack in "${archives[@]}"; do
      if [[ "$pack" != /* || ! -f "$pack" ]]; then
        echo "ERROR: image archive not found (absolute file path required): $pack" >&2
        exit 1
      fi
    done
  else
    images=("$ENGINE_IMAGE" "$CONTROL_IMAGE")
    local image
    for image in "${images[@]}"; do
      if ! docker image inspect "$image" >/dev/null 2>&1; then
        echo "Image not found locally, trying docker pull: $image"
        if ! docker pull "$image"; then
          echo "ERROR: image is neither local nor pullable: $image" >&2
          echo "       pass saved archives instead: bash $0 image p0,p1 /abs/a.tar.gz" >&2
          exit 1
        fi
      fi
    done
    # Conservative free-space gate: docker save reports uncompressed bytes, gzip roughly
    # halves them, so require half the uncompressed size before writing.
    local total_bytes=0 image_size free_kb
    for image in "${images[@]}"; do
      image_size=$(docker image inspect -f '{{.Size}}' "$image")
      total_bytes=$((total_bytes + image_size))
    done
    if ! mkdir -p "$(dirname "$archive")"; then
      echo "ERROR: cannot create IMAGE_ARCHIVE directory: $(dirname "$archive")" >&2
      exit 1
    fi
    free_kb=$(df -Pk "$(dirname "$archive")" | awk 'NR==2{print $4}')
    if (( total_bytes / 2 / 1024 > free_kb )); then
      echo "ERROR: not enough free space for the image archive under $(dirname "$archive")" >&2
      echo "       gzip estimate ~$((total_bytes / 2048 / 1024))GB, free $((free_kb / 1024))MB; set IMAGE_ARCHIVE to a path with room" >&2
      exit 1
    fi
    rm -f "$archive"
    # Guarded so a mid-export failure removes the partial archive instead of leaking via set -e.
    if ! docker save "${images[@]}" | gzip > "$archive"; then
      rm -f "$archive"
      echo "ERROR: image export failed; removed partial archive: $archive" >&2
      exit 1
    fi
    archives=("$archive")
  fi
  for node in "${nodes[@]}"; do
    host="$(node_host "$node")"
    if [[ -z "$packs" ]] && run_on "$host" docker image inspect "${images[@]}" >/dev/null 2>&1; then
      echo "[$node] images already present, skipping"
      continue
    fi
    echo "[$node] loading images on $host"
    for pack in "${archives[@]}"; do
      remote="/tmp/$(basename "$pack")"
      if [[ "$host" == "$local_ip" ]]; then
        docker load -i "$pack"
      else
        "${SCP[@]}" "$pack" root@"$host:$remote"
        run_on "$host" docker load -i "$remote"
        run_on "$host" rm -f "$remote"
      fi
    done
  done
  [[ -z "$packs" ]] && rm -f "$archive"
  echo "Images ready on nodes: ${nodes[*]}"
}
case "${1:-}" in
  p0|p1|d0|d1) start_node "$1" ;;
  proxy) start_proxy ;;
  image) shift; load_images "$@" ;;
  meta) bash "$HERE/memcache-meta.sh" ;;
  memcache)
    [[ -n "${2:-}" ]] || { echo "usage: $0 memcache <p0|p1|d0|d1>"; exit 1; }
    bash "$HERE/memcache-local.sh" "$2"
    ;;
  stop) stop_all ;;
  all)
    bash "$HERE/memcache-meta.sh"
    for node in "${NODES[@]}"; do bash "$HERE/memcache-local.sh" "$node"; done
    for node in p1 p0 d1 d0; do start_node "$node"; done
    start_proxy
    echo "All services started; the proxy waits for backends before serving."
    ;;
  *) echo "usage: $0 [meta|memcache <node>|image [nodes] [archives]|p0|p1|d0|d1|proxy|all|stop]"; exit 1 ;;
esac
