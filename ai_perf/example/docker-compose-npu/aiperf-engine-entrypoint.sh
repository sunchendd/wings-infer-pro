#!/bin/bash
set -e

echo "[engine] Waiting for start_command.sh..."

timeout=3600
elapsed=0

while [ ! -f /shared-volume/start_command.sh ]; do
  sleep 2
  elapsed=$((elapsed+2))
  if [ "$elapsed" -ge "$timeout" ]; then
    echo "[engine] ERROR: timeout waiting for start_command.sh"
    exit 1
  fi
done

echo "[engine] Found start_command.sh"

echo "[engine] Original host binding:"
grep -- '--host' /shared-volume/start_command.sh || true

echo "[engine] Patching host to 0.0.0.0 ..."
sed -i 's/--host [^ ]*/--host 0.0.0.0/g' /shared-volume/start_command.sh

echo "[engine] Patched host binding:"
grep -- '--host' /shared-volume/start_command.sh || true

echo "[engine] Launching engine..."
exec bash /shared-volume/start_command.sh
