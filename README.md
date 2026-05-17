# GPSS-in-a-Box

Automated setup for a local [GPSS](https://github.com/FlagBrew/local-gpss) server for [PKSM](https://github.com/FlagBrew/PKSM) on 3DS. Builds the latest [PKHeX](https://github.com/kwsch/PKHeX) legality engine, packages everything in Docker, and gets it running with a single command.

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
```

See [TECHNICAL.md](TECHNICAL.md) for troubleshooting and build details.

## Credits

- [FlagBrew](https://github.com/FlagBrew) - local-gpss server and PKSM
- [kwsch](https://github.com/kwsch/PKHeX) - PKHeX legality engine
- [santacrab2](https://github.com/santacrab2/PKHeX-Plugins) - Auto-Legality Mod
