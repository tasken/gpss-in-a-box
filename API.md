# API

Base URL: `http://<your-ip>:8082`

## Modes

**Full** (default): everything - GPSS server, web viewer, database, all endpoints below.

**Legality-only**: just `POST /api/legality` and `GET /api/status`. No database, no UI.

```bash
LEGALITY_ONLY=1 docker compose up -d
```

---

## POST /api/legality

Check raw Pokemon bytes against PKHeX. Works in both modes.

| Header | Required | Description |
|--------|----------|-------------|
| `X-Generation` | Yes | `1`-`9`, `BDSP`, or `PLA` |

Body: raw `.pkm` bytes (max 1 MB).

```bash
curl -X POST http://192.168.1.3:8082/api/legality \
  -H "X-Generation: 9" \
  --data-binary @my_pokemon.pkm
```

```json
{"legal": true, "report": []}
```

```json
{"legal": false, "report": ["Invalid: Move 1 PP is above the amount allowed (99)."]}
```

---

## GET /api/pokemon

Search the database. Full mode only.

| Param | Description |
|-------|-------------|
| `q` | Name, nickname, OT, code, or ID |
| `gen` | `1`-`9`, `3.1` (Colosseum), `3.2` (XD) |
| `legal` | `1` or `0` |
| `shiny` | `1` or `0` |
| `species` | Species ID |
| `sort` | `recent`, `dl`, `level`, `az`, `id` |
| `page` | Page number |
| `limit` | Results per page (max `100`) |

## GET /api/pokemon/{id}

Full detail for one Pokemon (stats, moves, types, Showdown paste, sprites).

## GET /api/pokemon/{id}/legality

Live PKHeX legality check on a Pokemon in the database. Returns `legal`, `report`, and whether the check was live or from the DB cache.

## GET /api/pokemon/{id}/download

Download raw `.pkm` file.

## GET /api/stats

Total count, legal count, per-generation breakdown, service status.

## GET /api/status

Engine version, database size, service health.

## GET /api/updates

Checks GitHub for newer PKHeX versions.

## /api/v2/*

Proxied to the Go GPSS server. This is what PKSM talks to.
