#!/bin/sh
set -e

# --- Prerequisites ---
missing=""
for cmd in docker curl; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        missing="$missing $cmd"
    fi
done
if [ -n "$missing" ]; then
    echo ""
    echo "Looks like some required tools are missing:$missing"
    echo ""
    echo "Please install them and run this script again."
    exit 1
fi

if ! docker compose version > /dev/null 2>&1; then
    echo ""
    echo "Docker Compose v2 is required but not installed."
    echo ""
    echo "Install it here: https://docs.docker.com/compose/install/"
    exit 1
fi

# Use sudo for docker if the current user can't access it directly
if docker info > /dev/null 2>&1; then
    COMPOSE="docker compose"
    DOCKER="docker"
else
    echo "Docker requires elevated permissions, using sudo."
    echo ""
    COMPOSE="sudo docker compose"
    DOCKER="sudo docker"
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')

# --- Check existing setup ---
if [ -f .local/config.json ]; then
    # ===========================================
    #  Already set up - check for updates
    # ===========================================
    echo ""
    echo "=== GPSS-in-a-Box ==="
    echo ""

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
        echo "Docker image not found. Needs to be rebuilt."
        echo ""
        NEED_BUILD=true
        if [ -n "$CURRENT_VERSION" ] && [ "$CURRENT_VERSION" != "bundled" ]; then
            UPDATE_LEGALITY=true
        fi
    fi

    # Check for engine updates
    if [ -z "$CURRENT_VERSION" ] || [ "$CURRENT_VERSION" = "bundled" ]; then
        if [ -n "$LATEST_TAG" ]; then
            echo "You're using the bundled legality engine (Dec 2025)."
            echo "Latest version available: $LATEST_TAG"
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
            echo "Legality engine: bundled (Dec 2025)"
            echo "(Could not check for updates)"
        fi
    elif [ -n "$LATEST_TAG" ] && [ "$LATEST_TAG" != "$CURRENT_VERSION" ]; then
        echo "Legality engine update available: $CURRENT_VERSION → $LATEST_TAG"
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
        echo "Legality engine is up to date ($CURRENT_VERSION)."
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
    "migrate_original_db": false,
    "download_original_db": false
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
        echo "Building..."
        echo ""
        if ! $COMPOSE build; then
            echo ""
            echo "Something went wrong during the build."
            echo "Try running the script again."
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
        echo "Starting server..."
        $COMPOSE up -d
        if [ "$RECHECK" = "true" ]; then
            echo ""
            echo "The Pokemon re-check is running in the background."
            echo "You can use the server right away. To see progress:"
            echo ""
            echo "  $COMPOSE logs -f"
        fi
    elif [ "$RUNNING" = "true" ]; then
        echo ""
        echo "Server is already running."
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
        echo "Server: http://${IP}:8082/"
    fi
    echo ""

else
    # ===========================================
    #  First time setup
    # ===========================================
    echo ""
    echo "=== GPSS-in-a-Box Setup ==="
    echo ""
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
                echo "  Could not fetch latest version. Using bundled engine instead"
                UPDATE_LEGALITY=false
            else
                echo "  Will build latest engine (version $PKHEX_TAG)"
            fi
            ;;
    esac

    # --- Backup database ---
    if [ -f .local/local-gpss.db ]; then
        DOWNLOAD_DB=false
        echo ""
        echo "Existing Pokemon database found. Will use it."
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
    echo "=== Ready to build ==="
    echo ""
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
    echo "Building... (this takes about a minute the first time)"
    echo ""
    if ! $COMPOSE build; then
        echo ""
        echo "Something went wrong during the build."
        echo "Try running the script again. If it keeps failing,"
        echo "check your internet connection and Docker installation."
        exit 1
    fi

    # --- Start ---
    if [ "$START" = "true" ]; then
        echo ""
        echo "Starting server..."
        $COMPOSE up -d
        echo ""
        echo "=== All done! ==="
        echo ""
        echo "Your server is running on port 8082."
        if [ "$RECHECK" = "true" ]; then
            echo ""
            echo "The Pokemon re-check is running in the background."
            echo "You can use the server right away. To see progress:"
            echo ""
            echo "  $COMPOSE logs -f"
        elif [ "$DOWNLOAD_DB" = "true" ]; then
            echo ""
            echo "The Pokemon backup is importing in the background."
            echo "To see progress:"
            echo ""
            echo "  $COMPOSE logs -f"
        fi
    else
        echo ""
        echo "=== Build complete! ==="
        echo ""
        echo "When you're ready to start the server, run:"
        echo ""
        echo "  $COMPOSE up -d"
    fi

    if [ -n "$IP" ]; then
        echo ""
        echo "=== Connect your 3DS ==="
        echo ""
        echo "In PKSM, set the server URL to:"
        echo ""
        echo "  http://${IP}:8082/"
        echo ""
        echo "Make sure to include the / at the end."
    fi
    echo ""
    echo "=== Quick reference ==="
    echo ""
    echo "  $COMPOSE up -d      Start the server"
    echo "  $COMPOSE down       Stop the server"
    echo "  $COMPOSE logs -f    View logs"
    echo ""
fi
