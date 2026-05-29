#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# ./setup.sh              Interactive setup / update wizard
# ./setup.sh clean        Remove cache and Docker image (keeps database)
# ./setup.sh clean --all  Remove everything including the database
# ---------------------------------------------------------------------------

# Colors (skip if not a terminal)
if [ -t 1 ]; then
    C_RESET='\033[0m'
    C_BOLD='\033[1m'
    C_DIM='\033[2m'
    C_CYAN='\033[1;36m'
    C_GREEN='\033[0;32m'
    C_RED='\033[0;31m'
    C_YELLOW='\033[0;33m'
else
    C_RESET='' C_BOLD='' C_DIM='' C_CYAN='' C_GREEN='' C_RED='' C_YELLOW=''
fi

info()  { printf "${C_CYAN}%s${C_RESET}\n" "$*"; }
ok()    { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
err()   { printf "${C_RED}✗ %s${C_RESET}\n" "$*" >&2; }
warn()  { printf "${C_YELLOW}! %s${C_RESET}\n" "$*"; }
header(){ printf "\n${C_BOLD}${C_CYAN}=== %s ===${C_RESET}\n\n" "$*"; }

spinner() {
    local pid=$1 msg=$2
    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0 start=$(date +%s)
    while kill -0 "$pid" 2>/dev/null; do
        local elapsed=$(( $(date +%s) - start ))
        printf "\r  ${C_DIM}${frames:i%10:1}${C_RESET} %s (%ds)" "$msg" "$elapsed"
        sleep 0.1
        i=$((i + 1))
    done
    printf "\r\033[K"
    wait "$pid"
    return $?
}

# --- Clean command ---
if [ "${1:-}" = "clean" ]; then
    header "Clean"

    # Docker needs sudo?
    if docker info > /dev/null 2>&1; then
        COMPOSE="docker compose"
        DOCKER="docker"
    else
        COMPOSE="sudo docker compose"
        DOCKER="sudo docker"
    fi

    # Always: stop container, remove image, remove cache
    $COMPOSE down 2>/dev/null && ok "Stopped container" || true
    $COMPOSE down --rmi all 2>/dev/null && ok "Removed Docker image" || true

    if [ -d .local/cache ]; then
        rm -rf .local/cache
        ok "Removed Showdown cache"
    fi

    if [ -f .local/viewer-index.db ]; then
        rm -f .local/viewer-index.db
        ok "Removed search index"
    fi

    # --all: also remove database and config
    if [ "${2:-}" = "--all" ]; then
        echo ""
        warn "This will delete your Pokemon database and all configuration."
        printf "Are you sure? [y/N]: "
        read -r confirm
        case "$confirm" in
            [yY]*)
                rm -rf .local .env
                ok "Removed database, config, and .env"
                ;;
            *)
                echo "  Database kept."
                ;;
        esac
    else
        echo ""
        info "Database and config are untouched."
        echo "  To also remove the database: ./setup.sh clean --all"
    fi

    echo ""
    exit 0
fi

# --- Prerequisites ---
missing=""
for cmd in docker curl; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        missing="$missing $cmd"
    fi
done
if [ -n "$missing" ]; then
    echo ""
    err "Looks like some required tools are missing:$missing"
    echo ""
    for cmd in $missing; do
        case "$cmd" in
            docker)
                printf "  Install Docker: ${C_CYAN}https://docs.docker.com/get-docker/${C_RESET}\n"
                ;;
            curl)
                printf "  Install curl: ${C_CYAN}sudo apt install curl${C_RESET}\n"
                ;;
        esac
    done
    echo ""
    echo "Please install them and run this script again."
    exit 1
fi

if ! docker compose version > /dev/null 2>&1; then
    echo ""
    err "Docker Compose v2 is required but not installed."
    echo ""
    printf "  Install it here: ${C_CYAN}https://docs.docker.com/compose/install/${C_RESET}\n"
    exit 1
fi

# Use sudo for docker if the current user can't access it directly
if docker info > /dev/null 2>&1; then
    COMPOSE="docker compose"
    DOCKER="docker"
else
    warn "Docker requires elevated permissions, using sudo."
    echo ""
    COMPOSE="sudo docker compose"
    DOCKER="sudo docker"
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')

# Fix ownership of .local/ files (Docker creates them as root)
if [ -d .local ] && [ "$(find .local -not -user "$(id -u)" -print -quit 2>/dev/null)" ]; then
    sudo chown -R "$(id -u):$(id -g)" .local
fi

# --- Check existing setup ---
if [ -f .local/config.json ]; then
    # ===========================================
    #  Already set up - check for updates
    # ===========================================
    header "GPSS-in-a-Box"

    RUNNING=false
    if $DOCKER ps --filter name=local-gpss --format '{{.Names}}' 2>/dev/null | grep -q local-gpss; then
        RUNNING=true
    fi

    IMAGE_EXISTS=false
    IMAGE_NAME=$($COMPOSE images -q 2>/dev/null)
    if [ -n "$IMAGE_NAME" ]; then
        IMAGE_EXISTS=true
    fi

    CURRENT_VERSION=""
    if [ -f .local/pkhex_version ]; then
        CURRENT_VERSION=$(cat .local/pkhex_version)
    fi

    LATEST_TAG=$(curl -sL https://api.github.com/repos/santacrab2/PKHeX-Plugins/releases/latest | grep '"tag_name"' | head -1 | cut -d'"' -f4)

    NEED_BUILD=false
    UPDATE_LEGALITY=false
    PKHEX_TAG="${CURRENT_VERSION}"
    RECHECK=false

    # Image missing - need to rebuild with whatever was last used
    if [ "$IMAGE_EXISTS" = "false" ]; then
        warn "Docker image not found. Needs to be rebuilt."
        echo ""
        NEED_BUILD=true
        if [ -n "$CURRENT_VERSION" ] && [ "$CURRENT_VERSION" != "bundled" ]; then
            UPDATE_LEGALITY=true
        fi
    fi

    # Check for engine updates
    if [ -z "$CURRENT_VERSION" ] || [ "$CURRENT_VERSION" = "bundled" ]; then
        if [ -n "$LATEST_TAG" ]; then
            info "You're using the bundled legality engine (Dec 2025)."
            info "Latest version available: $LATEST_TAG"
            echo ""
            printf "Build the latest engine? [Y/n]: "
            read -r choice
            case "$choice" in
                [nN]*)
                    echo "  Keeping bundled engine"
                    ;;
                *)
                    NEED_BUILD=true
                    UPDATE_LEGALITY=true
                    PKHEX_TAG="$LATEST_TAG"
                    echo "  Will build latest engine"
                    ;;
            esac
        else
            info "Legality engine: bundled (Dec 2025)"
            warn "Could not check for updates"
        fi
    elif [ -n "$LATEST_TAG" ] && [ "$LATEST_TAG" != "$CURRENT_VERSION" ]; then
        info "Legality engine update available: $CURRENT_VERSION → $LATEST_TAG"
        echo ""
        printf "Update? [Y/n]: "
        read -r choice
        case "$choice" in
            [nN]*)
                echo "  Keeping current version"
                ;;
            *)
                NEED_BUILD=true
                UPDATE_LEGALITY=true
                PKHEX_TAG="$LATEST_TAG"
                echo "  Will update engine"
                ;;
        esac
    else
        ok "Legality engine is up to date ($CURRENT_VERSION)."
    fi

    # Re-check if updating engine and database exists
    if [ "$UPDATE_LEGALITY" = "true" ] && [ -f .local/local-gpss.db ]; then
        echo ""
        echo "Re-check all Pokemon with the new engine?"
        echo "This runs in the background after the server starts."
        echo ""
        printf "Re-check? [Y/n]: "
        read -r recheck_choice
        case "$recheck_choice" in
            [nN]*)
                echo "  Skipping re-check"
                ;;
            *)
                RECHECK=true
                echo "  Will re-check after start"
                ;;
        esac
    fi

    # Check for empty database — offer to download community backup
    DOWNLOAD_DB=false
    if [ -f .local/local-gpss.db ]; then
        DB_SIZE=$(stat -c%s .local/local-gpss.db 2>/dev/null || stat -f%z .local/local-gpss.db 2>/dev/null || echo 0)
        if [ "$DB_SIZE" -lt 100000 ]; then
            echo ""
            warn "Database is nearly empty ($(( DB_SIZE / 1024 ))KB)."
            echo "The community Pokemon backup (~91k Pokemon) can be downloaded"
            echo "to give you a full library to browse."
            echo ""
            printf "Download Pokemon backup? [Y/n]: "
            read -r dl_choice
            case "$dl_choice" in
                [nN]*)
                    echo "  Skipping download"
                    ;;
                *)
                    DOWNLOAD_DB=true
                    echo "  Will download Pokemon backup"
                    ;;
            esac
        fi
    else
        echo ""
        echo "No database found. The community Pokemon backup (~91k Pokemon)"
        echo "can be downloaded so your server has Pokemon ready to browse."
        echo ""
        printf "Download Pokemon backup? [Y/n]: "
        read -r dl_choice
        case "$dl_choice" in
            [nN]*)
                echo "  Skipping download"
                ;;
            *)
                DOWNLOAD_DB=true
                echo "  Will download Pokemon backup"
                ;;
        esac
    fi

    # Update config
    cat > .local/config.json << EOF
{
  "fancy_screen": false,
  "database": {
    "db_type": "sqlite",
    "connection_string": "file:local-gpss.db?cache=shared&_pragma=foreign_keys(1)"
  },
  "http": {
    "port": 8082,
    "listening_addr": "0.0.0.0"
  },
  "misc": {
    "recheck_legality": $RECHECK,
    "migrate_original_db": $DOWNLOAD_DB,
    "download_original_db": $DOWNLOAD_DB
  }
}
EOF

    # Build if needed
    if [ "$NEED_BUILD" = "true" ]; then
        if [ "$RUNNING" = "true" ]; then
            $COMPOSE down 2>/dev/null || true
            RUNNING=false
        fi

        cat > .env << EOF
BUILD_TARGET=runtime
UPDATE_LEGALITY=$UPDATE_LEGALITY
PKHEX_TAG=${PKHEX_TAG:-unused}
EOF

        echo ""
        $COMPOSE build > /tmp/gpss-build.log 2>&1 &
        BUILD_PID=$!
        if spinner $BUILD_PID "Building Docker image"; then
            ok "Build complete"
        else
            err "Build failed. Last 20 lines:"
            tail -20 /tmp/gpss-build.log
            echo ""
            if grep -q "Could not resolve host" /tmp/gpss-build.log 2>/dev/null; then
                warn "Could not reach GitHub. Check your internet connection."
            elif grep -q "no space left" /tmp/gpss-build.log 2>/dev/null; then
                warn "Disk full — check available space: df -h"
            fi
            exit 1
        fi

        if [ "$UPDATE_LEGALITY" = "true" ]; then
            echo "$PKHEX_TAG" > .local/pkhex_version
        else
            echo "bundled" > .local/pkhex_version
        fi
    fi

    # Start / restart / already running
    if [ "$NEED_BUILD" = "true" ]; then
        echo ""
        info "Starting server..."
        $COMPOSE up -d
        if [ "$RECHECK" = "true" ]; then
            echo ""
            info "The Pokemon re-check is running in the background."
            echo "You can use the server right away. To see progress:"
            echo ""
            echo "  $COMPOSE logs -f"
        fi
    elif [ "$RUNNING" = "true" ]; then
        echo ""
        ok "Server is already running."
    else
        echo ""
        printf "Start the server? [Y/n]: "
        read -r start_choice
        case "$start_choice" in
            [nN]*)
                echo ""
                echo "Run '$COMPOSE up -d' when ready."
                ;;
            *)
                echo ""
                $COMPOSE up -d
                ;;
        esac
    fi

    if [ -n "$IP" ]; then
        echo "$IP" > .local/host_ip
        echo ""
        header "All done!"
        echo ""
        printf "  ${C_BOLD}Server URL:${C_RESET}\n"
        printf "\n"
        printf "  ┌─────────────────────────────────┐\n"
        SUMMARY_URL="http://${IP}:8082/"
        printf "  │                                 │\n"
        printf "  │   ${C_BOLD}%s${C_RESET}" "$SUMMARY_URL"
        SUMMARY_PAD=$((31 - ${#SUMMARY_URL}))
        printf "%*s│\n" "$SUMMARY_PAD" ""
        printf "  │                                 │\n"
        printf "  └─────────────────────────────────┘\n"
        echo ""
        printf "  ${C_BOLD}In PKSM:${C_RESET}\n"
        printf "    Set server URL to: ${C_CYAN}http://${IP}:8082/${C_RESET}\n"
        printf "    ${C_DIM}(include the / at the end)${C_RESET}\n"
        echo ""
        printf "  ${C_BOLD}Quick reference:${C_RESET}\n"
        printf "    ${C_DIM}start${C_RESET}   $COMPOSE up -d\n"
        printf "    ${C_DIM}stop${C_RESET}    $COMPOSE down\n"
        printf "    ${C_DIM}logs${C_RESET}    $COMPOSE logs -f\n"
        printf "    ${C_DIM}update${C_RESET}  ./setup.sh\n"
        echo ""
    fi
    echo ""

else
    # ===========================================
    #  First time setup
    # ===========================================
    header "GPSS-in-a-Box Setup"
    echo "This sets up a local GPSS server for PKSM on your 3DS."
    echo "The official server shut down in January 2026. This"
    echo "runs a replacement on your own machine."
    echo ""

    # --- Legality engine ---
    echo "--- Legality Engine ---"
    echo ""
    echo "The legality engine checks if Pokemon are valid and powers"
    echo "the auto-legalization feature in PKSM. You can build the"
    echo "latest version from source, or use the one bundled with"
    echo "the original release (from December 2025)."
    echo ""
    echo "  Yes = Build latest (recommended, adds ~30s to build)"
    echo "  No  = Use bundled version from Dec 2025"
    echo ""
    printf "Build latest legality engine? [Y/n]: "
    read -r legality_choice

    case "$legality_choice" in
        [nN]*)
            UPDATE_LEGALITY=false
            echo "  Using bundled engine (Dec 2025)"
            ;;
        *)
            UPDATE_LEGALITY=true
            PKHEX_TAG=$(curl -sL https://api.github.com/repos/santacrab2/PKHeX-Plugins/releases/latest | grep '"tag_name"' | head -1 | cut -d'"' -f4)
            if [ -z "$PKHEX_TAG" ]; then
                warn "Could not fetch latest version. Using bundled engine instead"
                UPDATE_LEGALITY=false
            else
                ok "Will build latest engine (version $PKHEX_TAG)"
            fi
            ;;
    esac

    # --- Backup database ---
    if [ -f .local/local-gpss.db ]; then
        DOWNLOAD_DB=false
        echo ""
        ok "Existing Pokemon database found. Will use it."
    else
        echo ""
        echo "--- Pokemon Database ---"
        echo ""
        echo "Before the official server shut down, the community had"
        echo "uploaded about 91,000 Pokemon. You can download this"
        echo "backup so your server has Pokemon ready to browse and"
        echo "download right away."
        echo ""
        echo "  Yes = Download the backup (recommended)"
        echo "  No  = Start with an empty server"
        echo ""
        printf "Download Pokemon backup? [Y/n]: "
        read -r db_choice

        case "$db_choice" in
            [nN]*)
                DOWNLOAD_DB=false
                echo "  Starting with empty database"
                ;;
            *)
                DOWNLOAD_DB=true
                echo "  Will download Pokemon backup"
                ;;
        esac
    fi

    # --- Re-check legality ---
    RECHECK=false
    HAS_DB=false
    if [ "$DOWNLOAD_DB" = "true" ] || [ -f .local/local-gpss.db ]; then
        HAS_DB=true
    fi
    if [ "$UPDATE_LEGALITY" = "true" ] && [ "$HAS_DB" = "true" ]; then
        echo ""
        echo "--- Re-check Pokemon ---"
        echo ""
        echo "The backup Pokemon were checked with an older engine."
        echo "You can re-check them with the new one to make sure"
        echo "their legal/illegal status is accurate. This happens"
        echo "in the background after the server starts. You can"
        echo "use the server normally while it works."
        echo ""
        echo "  Yes = Re-check all Pokemon (recommended)"
        echo "  No  = Keep original data (faster first start)"
        echo ""
        printf "Re-check Pokemon? [Y/n]: "
        read -r recheck_choice

        case "$recheck_choice" in
            [nN]*)
                RECHECK=false
                echo "  Keeping original data"
                ;;
            *)
                RECHECK=true
                echo "  Will re-check after first start"
                ;;
        esac
    fi

    # --- Start server ---
    echo ""
    printf "Start the server after building? [Y/n]: "
    read -r start_choice

    case "$start_choice" in
        [nN]*)
            START=false
            echo "  Will build only"
            ;;
        *)
            START=true
            echo "  Will start after build"
            ;;
    esac

    # --- Summary ---
    echo ""
    header "Ready to build"
    echo "  Legality engine:  $([ "$UPDATE_LEGALITY" = "true" ] && echo "Latest (v$PKHEX_TAG)" || echo "Bundled (Dec 2025)")"
    if [ -f .local/local-gpss.db ]; then
        echo "  Pokemon database: Existing"
    elif [ "$DOWNLOAD_DB" = "true" ]; then
        echo "  Pokemon backup:   Download"
    else
        echo "  Pokemon backup:   No (empty server)"
    fi
    if [ "$UPDATE_LEGALITY" = "true" ] && [ "$HAS_DB" = "true" ]; then
        echo "  Re-check Pokemon: $([ "$RECHECK" = "true" ] && echo "Yes (runs in background)" || echo "No")"
    fi
    echo "  Start after build: $([ "$START" = "true" ] && echo "Yes" || echo "No")"
    echo ""
    printf "Look good? [Y/n]: "
    read -r confirm

    case "$confirm" in
        [nN]*)
            echo "Setup cancelled."
            exit 0
            ;;
    esac

    # --- Stop existing container if running ---
    $COMPOSE down 2>/dev/null || true

    # --- Generate config ---
    mkdir -p .local

    cat > .local/config.json << EOF
{
  "fancy_screen": false,
  "database": {
    "db_type": "sqlite",
    "connection_string": "file:local-gpss.db?cache=shared&_pragma=foreign_keys(1)"
  },
  "http": {
    "port": 8082,
    "listening_addr": "0.0.0.0"
  },
  "misc": {
    "recheck_legality": $RECHECK,
    "migrate_original_db": $DOWNLOAD_DB,
    "download_original_db": $DOWNLOAD_DB
  }
}
EOF

    if [ "$UPDATE_LEGALITY" = "true" ]; then
        echo "$PKHEX_TAG" > .local/pkhex_version
    else
        echo "bundled" > .local/pkhex_version
    fi

    if [ -n "$IP" ]; then
        echo "$IP" > .local/host_ip
    fi

    # Save build args so 'docker compose up --build' uses the right ones
    cat > .env << EOF
BUILD_TARGET=runtime
UPDATE_LEGALITY=$UPDATE_LEGALITY
PKHEX_TAG=${PKHEX_TAG:-unused}
EOF

    # --- Build ---
    echo ""
    $COMPOSE build > /tmp/gpss-build.log 2>&1 &
    BUILD_PID=$!
    if spinner $BUILD_PID "Building Docker image (this takes about a minute the first time)"; then
        ok "Build complete"
    else
        err "Build failed. Last 20 lines:"
        tail -20 /tmp/gpss-build.log
        echo ""
        if grep -q "Could not resolve host" /tmp/gpss-build.log 2>/dev/null; then
            warn "Could not reach GitHub. Check your internet connection."
        elif grep -q "no space left" /tmp/gpss-build.log 2>/dev/null; then
            warn "Disk full — check available space: df -h"
        fi
        exit 1
    fi

    # --- Start ---
    if [ "$START" = "true" ]; then
        echo ""
        info "Starting server..."
        $COMPOSE up -d
        if [ "$RECHECK" = "true" ]; then
            echo ""
            info "The Pokemon re-check is running in the background."
            echo "You can use the server right away. To see progress:"
            echo ""
            echo "  $COMPOSE logs -f"
        elif [ "$DOWNLOAD_DB" = "true" ]; then
            echo ""
            info "The Pokemon backup is importing in the background."
            echo "To see progress:"
            echo ""
            echo "  $COMPOSE logs -f"
        fi
    else
        echo ""
        header "Build complete!"
        echo "When you're ready to start the server, run:"
        echo ""
        echo "  $COMPOSE up -d"
    fi

    if [ -n "$IP" ]; then
        echo ""
        header "All done!"
        echo ""
        printf "  ${C_BOLD}Server URL:${C_RESET}\n"
        printf "\n"
        printf "  ┌─────────────────────────────────┐\n"
        SUMMARY_URL="http://${IP}:8082/"
        printf "  │                                 │\n"
        printf "  │   ${C_BOLD}%s${C_RESET}" "$SUMMARY_URL"
        SUMMARY_PAD=$((31 - ${#SUMMARY_URL}))
        printf "%*s│\n" "$SUMMARY_PAD" ""
        printf "  │                                 │\n"
        printf "  └─────────────────────────────────┘\n"
        echo ""
        printf "  ${C_BOLD}In PKSM:${C_RESET}\n"
        printf "    Set server URL to: ${C_CYAN}http://${IP}:8082/${C_RESET}\n"
        printf "    ${C_DIM}(include the / at the end)${C_RESET}\n"
        echo ""
        printf "  ${C_BOLD}Quick reference:${C_RESET}\n"
        printf "    ${C_DIM}start${C_RESET}   $COMPOSE up -d\n"
        printf "    ${C_DIM}stop${C_RESET}    $COMPOSE down\n"
        printf "    ${C_DIM}logs${C_RESET}    $COMPOSE logs -f\n"
        printf "    ${C_DIM}update${C_RESET}  ./setup.sh\n"
        echo ""
    fi
    echo ""
fi
