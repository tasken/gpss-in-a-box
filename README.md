# GPSS-in-a-Box

The official GPSS server shut down in January 2026. This is a local replacement you can run on your own machine to keep using GPSS with [PKSM](https://github.com/FlagBrew/PKSM) on 3DS.

It builds the latest [PKHeX](https://github.com/kwsch/PKHeX) legality engine from source, runs everything in Docker, and includes a web viewer for browsing, searching, and exporting Pokemon. One script to set up, one command to run.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (includes Docker Compose)
- A 3DS with PKSM installed, on the same Wi-Fi network

## Setup

```bash
git clone https://github.com/tasken/gpss-in-a-box.git
cd gpss-in-a-box
./setup.sh
./sync-sprites.sh
```

`setup.sh` asks a few yes/no questions and handles configuring the server. `sync-sprites.sh` downloads Pokemon, item, and ball sprites required by the web viewer.

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
./rebuild.sh               # Rebuild and restart the configured deployment
./sync-sprites.sh          # Download sprites for offline use
```

Open `http://<YOUR_IP>:8082/` in a browser to use the web viewer.

### Legality-only mode

If you only need the PKHeX legality engine as an API (no database, no web UI, no GPSS server):

```bash
LEGALITY_ONLY=1 docker compose up -d
```

Send raw Pokemon bytes to `POST /api/legality` and get back a JSON result. See [API.md](API.md) for details.

## Docs

- [API.md](API.md) - API endpoints and usage examples
- [TECHNICAL.md](TECHNICAL.md) - how the build works, troubleshooting

## License

GPL-3.0 - see [LICENSE](LICENSE).

## Credits

- [FlagBrew](https://github.com/FlagBrew) - [local-gpss](https://github.com/FlagBrew/local-gpss) server and [PKSM](https://github.com/FlagBrew/PKSM)
- [kwsch](https://github.com/kwsch) - [PKHeX](https://github.com/kwsch/PKHeX) legality engine
- [santacrab2](https://github.com/santacrab2) - [PKHeX-Plugins](https://github.com/santacrab2/PKHeX-Plugins) (Auto-Legality Mod)
- [msikma](https://github.com/msikma) - [pokesprite](https://github.com/msikma/pokesprite) (item and ball sprites)
- [Smogon](https://github.com/smogon) - [Pokemon Showdown](https://github.com/smogon/pokemon-showdown-client) (animated sprites, Pokedex data)
