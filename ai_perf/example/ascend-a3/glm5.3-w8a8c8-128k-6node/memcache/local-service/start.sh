#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="${WINGS_LOG_DIR:-$(cd -- "$SCRIPT_DIR/../.." && pwd)}"
export MMC_LOCAL_CONFIG_PATH="${MMC_LOCAL_CONFIG_PATH:-$SCRIPT_DIR/mmc-local.conf}"
export MF_GROUP_JOIN_MAX_TIMEOUT=1200
export PYTHONHASHSEED=0

cd "$SCRIPT_DIR"
mkdir -p "$DEPLOY_ROOT/logs"
exec > >(tee -a "$DEPLOY_ROOT/logs/memcache-local-$(hostname).log") 2>&1
exec python3 ./memcache.py
