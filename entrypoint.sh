#!/bin/sh

LEGALITY_ONLY="${LEGALITY_ONLY:-0}"
PUBLIC_PORT=8082

if [ "$LEGALITY_ONLY" = "1" ]; then
    export GPSS_CONSOLE="/app/bin/GpssConsole"
    export VIEWER_HOST="0.0.0.0"
    export VIEWER_PORT="$PUBLIC_PORT"
    echo "=== GPSS-in-a-Box (legality only) ==="
    exec python3 /app/viewer/server.py --legality-only
fi

mkdir -p /app/host/.local
cd /app/host/.local || exit 1

if [ ! -f config.json ]; then
    echo ""
    echo "Server is not configured yet."
    echo "Run ./setup.sh to set up the server."
    echo ""
    trap 'exit 0' TERM INT
    sleep infinity &
    wait
    exit 0
fi

# The Go server expects ./bin/GpssConsole relative to its working dir (.local/).
# This symlink lands in the host-mounted folder — cleaned up on exit.
ln -sf /app/bin bin

# Serve sprites from host-mounted .local/sprites/ instead of baking into image.
ln -sfn /app/host/.local/sprites /app/sprites

HOST_IP="${HOST_IP:-}"
if [ -z "$HOST_IP" ] && [ -f host_ip ]; then
    HOST_IP=$(cat host_ip)
fi

VIEWER_ENABLED="${VIEWER_ENABLED:-1}"
GPSS_INTERNAL_PORT="${GPSS_INTERNAL_PORT:-8083}"
CONFIG_BACKUP=""
VIEWER_PID=""

if [ "$VIEWER_ENABLED" = "1" ]; then
    CONFIG_BACKUP="/tmp/gpss-config-user.json"
    cp config.json "$CONFIG_BACKUP"
    python3 /app/viewer/patch_gpss_port.py \
        "$CONFIG_BACKUP" config.json "$GPSS_INTERNAL_PORT" "127.0.0.1"
fi

PIPE=/tmp/gpss.pipe
rm -f "$PIPE"
mkfifo "$PIPE"

/app/local-gpss > "$PIPE" 2>&1 &
SERVER_PID=$!

restore_config() {
    if [ -n "$CONFIG_BACKUP" ] && [ -f "$CONFIG_BACKUP" ]; then
        # Restore only the http section (port/addr) from the backup,
        # preserving any flags the Go server changed at runtime.
        python3 -c "
import json
with open('$CONFIG_BACKUP') as f: backup = json.load(f)
with open('config.json') as f: current = json.load(f)
current['http'] = backup['http']
with open('config.json', 'w') as f: json.dump(current, f, indent=2); f.write('\n')
" 2>/dev/null || cp "$CONFIG_BACKUP" config.json
    fi
}

stop_services() {
    kill -TERM "$VIEWER_PID" 2>/dev/null
    kill -TERM "$SERVER_PID" 2>/dev/null
    wait "$VIEWER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
}

cleanup() {
    stop_services
    restore_config
    rm -f "$PIPE" bin
    exit 0
}
trap cleanup TERM INT

if [ "$VIEWER_ENABLED" = "1" ]; then
    export GPSS_DB="/app/host/.local/local-gpss.db"
    export GPSS_INDEX="/app/host/.local/viewer-index.db"
    export GPSS_BACKEND="http://127.0.0.1:${GPSS_INTERNAL_PORT}"
    export GPSS_CONSOLE="/app/bin/GpssConsole"
    export GPSS_RUNTIME=docker
    export VIEWER_HOST="0.0.0.0"
    export VIEWER_PORT="$PUBLIC_PORT"
    python3 /app/viewer/server.py \
        --db "$GPSS_DB" \
        --gpss-backend "$GPSS_BACKEND" \
        &
    VIEWER_PID=$!
    echo "Viewer: starting (pid $VIEWER_PID)"
fi

while IFS= read -r line; do
    case "$line" in
        "Checked: "*)
            rest="${line#Checked: }"
            current="${rest%%/*}"
            after="${rest#*/}"
            total="${after%%,*}"

            if [ $((current % 100)) -ne 0 ] && [ "$current" != "$total" ]; then
                continue
            fi

            NOW=$(date +%s)
            if [ -z "$CHECK_START" ]; then
                CHECK_START=$NOW
                CHECK_START_COUNT=$current
                echo "$line"
                continue
            fi

            ELAPSED=$((NOW - CHECK_START))
            DONE=$((current - CHECK_START_COUNT))
            if [ "$DONE" -gt 0 ] && [ "$ELAPSED" -gt 0 ]; then
                LEFT=$(( (total - current) * ELAPSED / DONE ))
                MINS=$((LEFT / 60))
                SECS=$((LEFT % 60))
                PCT=$((current * 100 / total))
                printf "%s - %d%% - ETA: %dm %02ds\n" "$line" "$PCT" "$MINS" "$SECS"
            else
                echo "$line"
            fi
            ;;
        "Created: "*)
            rest="${line#Created: }"
            current="${rest%%/*}"
            total="${rest#*/}"

            if [ $((current % 100)) -ne 0 ] && [ "$current" != "$total" ]; then
                continue
            fi
            echo "$line"
            ;;
        *"Starting HTTP server on "*)
            if [ "$VIEWER_ENABLED" = "1" ]; then
                # Check viewer is still alive
                if kill -0 "$VIEWER_PID" 2>/dev/null; then
                    VIEWER_STATUS="running"
                else
                    VIEWER_STATUS="failed (check /tmp/viewer.log)"
                fi
                echo ""
                echo "=== GPSS-in-a-Box ==="
                echo "  GPSS server:  running (Go)"
                echo "  Viewer:       ${VIEWER_STATUS} (Python)"
                echo ""
                if [ -n "$HOST_IP" ]; then
                    echo "  Browse:    http://${HOST_IP}:${PUBLIC_PORT}/"
                    echo "  PKSM API:  http://${HOST_IP}:${PUBLIC_PORT}/api/v2/gpss/"
                else
                    echo "  Browse:    http://<your-lan-ip>:${PUBLIC_PORT}/"
                    echo "  PKSM API:  http://<your-lan-ip>:${PUBLIC_PORT}/api/v2/gpss/"
                fi
                echo ""
            elif [ -n "$HOST_IP" ]; then
                echo "$line" | sed "s/0\.0\.0\.0/$HOST_IP/"
            else
                echo "$line"
            fi
            ;;
        *)
            echo "$line"
            ;;
    esac
done < "$PIPE"

wait "$SERVER_PID"
EXIT_CODE=$?
stop_services
restore_config
rm -f "$PIPE"
exit "$EXIT_CODE"
