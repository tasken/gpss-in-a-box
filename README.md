# GPSS-in-a-Box

Local replacement for the official GPSS server (shut down January 2026). Serves [PKSM](https://github.com/FlagBrew/PKSM) on 3DS and includes a web viewer for browsing, searching, and exporting Pokémon from the database. Builds the latest [PKHeX](https://github.com/kwsch/PKHeX) legality engine from source, packages everything in Docker, and gets it running with a single command.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (includes Docker Compose)
- A 3DS with PKSM installed, on the same Wi-Fi network

## Setup

```bash
git clone https://github.com/tasken/gpss-in-a-box.git
cd gpss-in-a-box
./setup.sh
```

The script asks a few yes/no questions and handles everything else.

## Connect your 3DS

After setup, the script shows your server address. In PKSM:

1. Open the GPSS screen
2. Set the server URL to `http://<YOUR_IP>:8082/`
3. Make sure to include the `/` at the end

## Usage

```bash
docker compose up -d       # Start
docker compose down        # Stop
docker compose logs -f     # Logs
./setup.sh                 # Update or reconfigure
./rebuild.sh               # Stop, remove image, rebuild
./sync-sprites.sh          # Download sprites for offline use
```

The web viewer is available at `http://<YOUR_IP>:8082/` in any browser.

### Legality-only mode

Run just the PKHeX legality engine as an API, without the database or web UI:

```bash
LEGALITY_ONLY=1 docker compose up -d
```

See [API.md](API.md) for endpoint documentation and [TECHNICAL.md](TECHNICAL.md) for troubleshooting and build details.

## License

GPL-3.0 — see [LICENSE](LICENSE).

## Credits

- [FlagBrew](https://github.com/FlagBrew) - local-gpss server and PKSM
- [kwsch](https://github.com/kwsch/PKHeX) - PKHeX legality engine
- [santacrab2](https://github.com/santacrab2/PKHeX-Plugins) - Auto-Legality Mod
