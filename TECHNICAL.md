# Technical Details

## Why this exists

The official [local-gpss v2.0.1](https://github.com/FlagBrew/local-gpss) ships with a PKHeX legality engine from December 2025. As new games and updates come out, that engine falls behind and starts marking valid Pokemon as illegal (or vice versa).

This project rebuilds the legality engine ([GpssConsole](https://github.com/FlagBrew/local-gpss)) from source against the latest [PKHeX](https://github.com/kwsch/PKHeX) and [PKHeX-Plugins](https://github.com/santacrab2/PKHeX-Plugins), so legality checks stay current. It also patches the Go server's progress output to flush properly in Docker.

## Setup

`setup.sh` has two modes, determined by whether `.local/config.json` exists:

**First run** asks about the legality engine (build latest or use bundled), the community Pokemon backup (~91k Pokemon), whether to re-check legality on those Pokemon, and whether to start the server after building. It then generates config, builds the Docker image, and optionally starts.

**Returning runs** check for engine updates via the GitHub API. If a newer version is available, it offers to rebuild. It only touches the Docker image when something actually changed.

Both flows store their choices in `.env` (read by Docker Compose) and `.local/pkhex_version` (for version tracking across runs).

## Build

The Dockerfile has two build targets:

**`not-configured`** is a tiny Alpine image (~5MB) with just the entrypoint script. This is what `docker compose up` builds when no `.env` exists yet (i.e. before `setup.sh` has run). It shows a message telling the user to run setup and waits.

**`runtime`** is the full image, built in three stages:

1. **.NET stage** builds GpssConsole from the latest PKHeX source (or downloads the bundled v2.0.1 binary if the user chose that). Two `sed` patches fix breaking API changes in newer PKHeX:
   - `pokemon.Context.Generation()` → `.Generation` (method became a property)
   - `DecryptedPartyData` / `DecryptedBoxData` → `WriteDecryptedDataParty()` / `WriteDecryptedDataStored()` (direct byte access replaced with write methods)

2. **Go stage** builds the local-gpss API server. One `sed` patch adds `\n` to `fmt.Printf` progress lines so they flush instead of getting stuck in Go's internal buffer.

3. **Alpine stage** combines both binaries into a minimal runtime image with the required shared libraries. Sprites are **not** baked into the image — they're served from the host via volume mount (`.local/sprites/`, symlinked at container startup by `entrypoint.sh`).

Docker Compose reads `BUILD_TARGET`, `UPDATE_LEGALITY`, and `PKHEX_TAG` from `.env`, so `docker compose up --build` always uses the right settings without needing `setup.sh` again.

## Runtime

The container entrypoint (`entrypoint.sh`) does a few things before and around the server process:

If `config.json` is missing, it prints a setup message and sleeps forever (clean `docker stop`, no restart loop). Otherwise, it starts the Go server with its output piped through a filter that:

- Reduces progress lines (Checked/Created) to every 100th, with percentage and ETA on re-check lines
- Replaces `0.0.0.0` in the startup message with the machine's LAN IP (read from `.local/host_ip`)
- Passes everything else through unchanged

A named pipe keeps the server PID known so TERM/INT signals forward cleanly for graceful Docker shutdown.

## Project structure

```
gpss-in-a-box/
├── Dockerfile           # Multi-stage build (not-configured + runtime targets)
├── docker-compose.yml   # Service config, reads build args from .env
├── setup.sh             # Interactive setup wizard
├── rebuild.sh           # Stop, remove image, rebuild
├── sync-sprites.sh      # Download sprites for offline use
├── entrypoint.sh        # Container startup, progress filter, signal handling
├── LICENSE              # GPL-3.0
├── README.md            # User guide
├── API.md               # API endpoint reference
├── TECHNICAL.md         # This file
├── viewer/              # Web UI (Python + vanilla JS/CSS)
│   ├── server.py        # Bootstrap, auto-reload dev mode
│   ├── routes.py        # HTTP handlers
│   ├── run.sh           # Local dev launcher (auto-reload)
│   ├── pkm/             # Per-generation binary parsers
│   ├── dex.py           # Showdown Pokédex data + lookup tables
│   ├── index.py         # Search index builder/manager
│   ├── pokepaste.py     # Showdown set export
│   ├── legality.py      # PKHeX legality checking
│   ├── revalidate.py    # Batch legality re-check CLI
│   ├── patch_gpss_port.py # Redirect Go server to internal port
│   └── static/          # Frontend (HTML/CSS/JS)
├── .env                 # Build args (gitignored, created by setup.sh)
└── .local/              # Runtime data (gitignored, created by setup.sh)
    ├── config.json      # Server configuration
    ├── pkhex_version    # Installed engine version ("bundled" or tag)
    ├── host_ip          # Machine LAN IP for log display
    ├── sprites/         # Downloaded sprites (via sync-sprites.sh)
    ├── local-gpss.db    # Active database
    └── gpss.db          # Backup database (downloaded from original GPSS)
```

## Troubleshooting

| Problem | What to do |
|---------|------------|
| 3DS shows an error | Make sure the server is running and check the IP address |
| Error right after entering the URL | Add `/` at the end of the URL |
| Connection refused | Open the firewall port (see below) |
| No Pokemon showing up | The backup is still importing. Run `docker compose logs -f` to check |
| Pokemon incorrectly marked as illegal | Run `./setup.sh` again to get the latest legality engine |
| 3DS freezes | Try updating PKSM from the [latest release](https://github.com/FlagBrew/PKSM/releases) |

### Firewall

If your 3DS can't connect, your firewall might be blocking port 8082:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 8082 proto tcp
```

Remove the rule later with:

```bash
sudo ufw delete allow from 192.168.1.0/24 to any port 8082 proto tcp
```

### Starting over

Clean cache and rebuild artifacts (keeps your database):

```bash
./setup.sh clean
./setup.sh
```

Full reset (deletes everything including your database):

```bash
./setup.sh clean --all
./setup.sh
```
