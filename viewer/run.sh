#!/usr/bin/env bash
# Local viewer — port 8082, LAN 0.0.0.0, auto-reload on file changes.
# Override: VIEWER_HOST, VIEWER_PORT, GPSS_DB, GPSS_BACKEND, GPSS_RUNTIME=local|docker
# Disable reload: ./run.sh --no-reload  or  VIEWER_RELOAD=0 ./run.sh
set -euo pipefail
cd "$(dirname "$0")"
reload=(--reload)
if [[ "${VIEWER_RELOAD:-1}" == "0" ]]; then
  reload=(--no-reload)
fi
exec python3 server.py "${reload[@]}" "$@"
