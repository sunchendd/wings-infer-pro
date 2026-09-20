#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="${WINGS_LOG_DIR:-$(cd -- "$SCRIPT_DIR/../.." && pwd)}"
export MMC_META_CONFIG_PATH="${MMC_META_CONFIG_PATH:-$SCRIPT_DIR/mmc-meta.conf}"
export PYTHONHASHSEED=0

mkdir -p "$DEPLOY_ROOT/logs"
exec > >(tee -a "$DEPLOY_ROOT/logs/memcache-meta.log") 2>&1
exec python3 -c 'from memcache_hybrid import MetaService; MetaService.main()'
