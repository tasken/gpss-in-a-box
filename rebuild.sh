#!/bin/bash
set -e

# rebuild.sh — Rebuild and restart the configured deployment.

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

# Automatically detect if Docker needs sudo.
if docker info > /dev/null 2>&1; then
    DOCKER_CMD="docker"
else
    DOCKER_CMD="sudo docker"
fi

if $DOCKER_CMD container inspect gpss > /dev/null 2>&1; then
    info "Building image [gpss:local] …"
    if ! $DOCKER_CMD build -t gpss:local .; then
        err "Build failed"
        exit 1
    fi

    IMAGE_ID=$($DOCKER_CMD image inspect --format '{{.Id}}' gpss:local)
    CONTAINER_IMAGE_ID=$($DOCKER_CMD container inspect --format '{{.Image}}' gpss)
    if [ "$CONTAINER_IMAGE_ID" != "$IMAGE_ID" ]; then
        err "The Portainer container still uses the previous image."
        err "Redeploy its stack in Portainer to apply gpss:local."
        exit 1
    fi

    info "Restarting Portainer container [gpss] …"
    $DOCKER_CMD restart gpss > /dev/null
else
    info "Building Compose image …"
    if ! $DOCKER_CMD compose build; then
        err "Build failed"
        exit 1
    fi

    info "Starting Compose service [local-gpss] …"
    if ! $DOCKER_CMD compose up -d; then
        err "Failed to start the Compose service."
        exit 1
    fi
fi

echo ""
ok "Rebuild complete. Your development changes are now live."
