#!/usr/bin/env bash
# sync-sprites.sh — Download and sync sprite assets for offline use.
#
# Sources:
#   - pokesprite (GitHub)  → items, balls, box sprites, data
#   - Showdown CDN         → animated Pokemon GIFs
#
# Run once to populate, re-run to pull new/updated sprites.
# Usage: ./sync-sprites.sh [target-dir]
set -euo pipefail

DIR="${1:-.local/sprites}"
SHOWDOWN="https://play.pokemonshowdown.com/sprites"
POKESPRITE_ZIP="https://github.com/msikma/pokesprite/archive/refs/heads/master.zip"
JOBS=16

C_RESET="\033[0m"
C_BOLD="\033[1m"
C_DIM="\033[2m"
C_GREEN="\033[32m"
C_CYAN="\033[36m"

info()  { printf "${C_CYAN}▸${C_RESET} %s\n" "$*"; }
done_() { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
dim()   { printf "${C_DIM}  %s${C_RESET}\n" "$*"; }

mkdir -p "$DIR"

# ── pokesprite (items, balls, Pokemon box sprites, data) ─────────────
info "Syncing pokesprite (items, box sprites, data)"
TMPZIP=$(mktemp /tmp/pokesprite-XXXXXX.zip)
TMPDIR=$(mktemp -d /tmp/pokesprite-XXXXXX)
trap 'rm -rf "$TMPZIP" "$TMPDIR"' EXIT

wget -q --show-progress -O "$TMPZIP" "$POKESPRITE_ZIP"
unzip -qo "$TMPZIP" -d "$TMPDIR"

for sub in pokemon-gen8 items data; do
    rsync -a --delete "$TMPDIR/pokesprite-master/$sub/" "$DIR/$sub/"
done
rm -rf "$TMPZIP" "$TMPDIR"
trap - EXIT

ITEM_COUNT=$(find "$DIR/items" -name "*.png" | wc -l)
PKM_COUNT=$(find "$DIR/pokemon-gen8" -name "*.png" | wc -l)
done_ "pokesprite: $PKM_COUNT Pokemon sprites, $ITEM_COUNT item sprites"

# ── Showdown animated sprites ────────────────────────────────────────
sync_showdown_dir() {
    local folder="$1"
    local ext="$2"
    local url="$SHOWDOWN/$folder/"
    local dest="$DIR/$folder"

    info "Syncing Showdown $folder/"
    mkdir -p "$dest"

    local before
    before=$(find "$dest" -maxdepth 1 -name "*.$ext" 2>/dev/null | wc -l)

    local listing
    listing=$(curl -sL "$url" | grep -oP "href=\"\K[^\"]+\\.${ext}" | sort -u)
    local total
    total=$(echo "$listing" | wc -l)

    # Filter to only files we don't have
    local need=()
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        [ -f "$dest/$f" ] || need+=("$f")
    done <<< "$listing"

    local count=${#need[@]}
    dim "$total on server, $before local, $count to download"

    if [ "$count" -eq 0 ]; then
        done_ "$folder: up to date ($total files)"
        return
    fi

    # Download in parallel batches with progress
    local done_n=0
    local pids=()

    for f in "${need[@]}"; do
        wget -q -O "$dest/$f" "$url$f" 2>/dev/null &
        pids+=($!)

        if [ ${#pids[@]} -ge $JOBS ]; then
            # Wait for batch to finish
            for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
            done_n=$((done_n + ${#pids[@]}))
            printf "\r${C_DIM}  %d / %d${C_RESET}  " "$done_n" "$count"
            pids=()
        fi
    done
    # Wait for remaining
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
    done_n=$((done_n + ${#pids[@]}))
    printf "\r"

    local after
    after=$(find "$dest" -maxdepth 1 -name "*.$ext" | wc -l)
    local new=$((after - before))
    done_ "$folder: $after files ($new new)          "
}

sync_showdown_dir "ani"       "gif"
sync_showdown_dir "ani-shiny" "gif"

# ── Summary ──────────────────────────────────────────────────────────
echo ""
printf "${C_BOLD}Sprites synced to ${DIR}${C_RESET}\n"
du -sh "$DIR" | awk '{printf "  Total size: %s\n", $1}'
echo ""
echo "Next: rebuild with  sudo docker compose up -d --build"
