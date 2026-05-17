#!/bin/sh

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

# Symlink the built binary so the server finds it at ./bin/GpssConsole
ln -sf /app/bin bin

HOST_IP="${HOST_IP:-}"
if [ -z "$HOST_IP" ] && [ -f host_ip ]; then
    HOST_IP=$(cat host_ip)
fi

PIPE=/tmp/gpss.pipe
rm -f "$PIPE"
mkfifo "$PIPE"

/app/local-gpss > "$PIPE" 2>&1 &
SERVER_PID=$!

cleanup() {
    kill -TERM "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
    rm -f "$PIPE"
    exit 0
}
trap cleanup TERM INT

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
            if [ -n "$HOST_IP" ]; then
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
rm -f "$PIPE"
exit "$EXIT_CODE"
