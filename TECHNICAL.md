# Technical Details

## Why this exists

The official [local-gpss v2.0.1](https://github.com/FlagBrew/local-gpss) ships with a PKHeX legality engine from December 2025. As new games come out, that engine falls behind and starts marking valid Pokemon as illegal (or vice versa).

This project rebuilds the legality engine from source against the latest [PKHeX](https://github.com/kwsch/PKHeX) and [PKHeX-Plugins](https://github.com/santacrab2/PKHeX-Plugins) so legality checks stay current.

## How setup works

`setup.sh` checks if `.local/config.json` exists.

**First run**: asks about the legality engine (build latest vs bundled), the community Pokemon backup (~91k Pokemon), whether to re-check legality, and whether to start after building. Generates `.env` and config, builds the Docker image.

**Returning runs**: checks GitHub for engine updates and offers to rebuild if there's a newer version.

## How the build works

The Dockerfile has two targets:

**`not-configured`**: tiny Alpine placeholder that tells you to run `setup.sh`. This is what runs before first setup.

**`runtime`**: the real image, three stages:

1. **.NET** - builds GpssConsole from PKHeX source (or downloads the bundled binary). Two `sed` patches fix breaking API changes in newer PKHeX versions.
2. **Go** - builds the local-gpss API server. One patch fixes log flushing in Docker.
3. **Alpine** - combines both binaries with Python for the viewer.

Sprites are not in the image. They're served from `.local/sprites/` via volume mount, symlinked at startup.

## Runtime

The entrypoint starts the Go server and the Python viewer behind a single port (8082). If `LEGALITY_ONLY=1` is set, it skips the Go server and database entirely and runs just the legality API.

The Go server's output goes through a filter that throttles progress lines and adds ETA for legality re-checks.

## Project structure

```
gpss-in-a-box/
├── Dockerfile           # Multi-stage build
├── docker-compose.yml   # Service config, reads .env
├── setup.sh             # Setup wizard
├── rebuild.sh           # Rebuild and restart the configured deployment
├── sync-sprites.sh      # Download sprites for offline use
├── entrypoint.sh        # Container startup
├── LICENSE              # GPL-3.0
├── README.md
├── API.md               # API reference
├── TECHNICAL.md         # This file
├── viewer/
│   ├── server.py        # Server bootstrap, auto-reload
│   ├── routes.py        # HTTP handlers
│   ├── run.sh           # Local dev launcher
│   ├── pkm/             # Per-generation binary parsers
│   ├── dex.py           # Showdown data + lookup tables
│   ├── index.py         # Search index
│   ├── pokepaste.py     # Showdown set export
│   ├── legality.py      # PKHeX legality checking
│   ├── revalidate.py    # Batch legality re-check
│   ├── patch_gpss_port.py
│   └── static/          # Frontend (HTML/CSS/JS)
├── .env                 # Build args (gitignored)
└── .local/              # Runtime data (gitignored)
    ├── config.json
    ├── pkhex_version
    ├── host_ip
    ├── sprites/         # Downloaded sprites
    ├── local-gpss.db    # Active database
    └── gpss.db          # Backup database
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 3DS shows an error | Check the server is running and the IP is correct |
| Error after entering URL | Add `/` at the end |
| Connection refused | Open port 8082 in your firewall (see below) |
| No Pokemon showing up | Backup is still importing. Check `docker compose logs -f` |
| Sprites / images missing (404 in logs) | Run `./sync-sprites.sh` to download sprite assets |
| Pokemon marked as illegal incorrectly | Run `./setup.sh` to update the legality engine |
| 3DS freezes | Update PKSM from [latest release](https://github.com/FlagBrew/PKSM/releases) |

### Firewall

```bash
# Allow
sudo ufw allow from 192.168.1.0/24 to any port 8082 proto tcp

# Remove later
sudo ufw delete allow from 192.168.1.0/24 to any port 8082 proto tcp
```

### Starting over

```bash
# Keep database, rebuild everything else
./setup.sh clean
./setup.sh

# Full reset including database
./setup.sh clean --all
./setup.sh
```
