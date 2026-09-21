#!/bin/bash
set -e

mkdir -p /var/log/wings

echo "[engine] waiting for /wings-generated/start_command.sh ..."
timeout=600
elapsed=0
while [ ! -f /wings-generated/start_command.sh ]; do
  sleep 2
  elapsed=$((elapsed+2))
  if [ "$elapsed" -ge "$timeout" ]; then
    echo "[engine] ERROR: timeout waiting for start_command.sh"
    exit 1
  fi
done

echo "[engine] launching wings start_command.sh"
exec bash /wings-generated/start_command.sh
