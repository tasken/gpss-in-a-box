#!/bin/bash
set -e

# rebuild.sh — Stop, remove image, rebuild, and restart the container.

if [ -t 1 ]; then
    C_RESET='\033[0m'
    C_BOLD='\033[1m'
    C_DIM='\033[2m'
    C_CYAN='\033[1;36m'
    C_GREEN='\033[0;32m'
    C_RED='\033[0;31m'
else
    C_RESET='' C_BOLD='' C_DIM='' C_CYAN='' C_GREEN='' C_RED=''
fi

info()  { printf "${C_CYAN}%s${C_RESET}\n" "$*"; }
ok()    { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
err()   { printf "${C_RED}✗ %s${C_RESET}\n" "$*" >&2; }

if docker info > /dev/null 2>&1; then
    COMPOSE="docker compose"
else
    COMPOSE="sudo docker compose"
fi

info "Stopping container …"
$COMPOSE down 2>/dev/null && ok "Stopped" || ok "Not running"

info "Removing image …"
$COMPOSE down --rmi local 2>/dev/null && ok "Image removed" || ok "No image to remove"

info "Building …"
if $COMPOSE build; then
    ok "Build complete"
else
    err "Build failed"
    exit 1
fi

echo ""
ok "Rebuild complete. Run '$COMPOSE up -d' to start."
