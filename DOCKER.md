# Docker Reference

```bash
docker compose up -d             # Start
docker compose down              # Stop
docker compose restart           # Restart
docker compose logs -f           # Follow logs
docker compose ps                # Status

./setup.sh                       # Rebuild (checks for updates)
docker compose up -d --build     # Rebuild with current settings

docker rm -f local-gpss          # Remove container
docker compose down --rmi all    # Stop + remove container and image

docker compose down              # Full reset:
rm -rf .local .env               #   remove config and data
./setup.sh                       #   start fresh
```
