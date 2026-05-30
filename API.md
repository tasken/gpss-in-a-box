# API Reference

Base URL: `http://<your-ip>:8082`

## Legality check

Check a raw PKM file against PKHeX without storing it in the database.

```
POST /api/legality
```

**Headers:**

| Header | Required | Description |
|--------|----------|-------------|
| `X-Generation` | Yes | Game generation (`1`-`9`, `BDSP`, `PLA`) |
| `Content-Type` | No | `application/octet-stream` |

**Body:** Raw `.pkm` binary data (max 1 MB).

**Response:**

```json
{
  "legal": true,
  "report": []
}
```

```json
{
  "legal": false,
  "report": [
    "Invalid: Move 1 PP is above the amount allowed (99).",
    "Invalid: Unable to match encounter."
  ]
}
```

**Example:**

```bash
curl -X POST http://192.168.1.3:8082/api/legality \
  -H "X-Generation: 9" \
  --data-binary @my_pokemon.pkm
```

## Search

```
GET /api/pokemon?q=&gen=&legal=&shiny=&sort=&page=&limit=
```

| Param | Description |
|-------|-------------|
| `q` | Search by name, nickname, OT, code, or ID |
| `gen` | Filter by generation (`1`-`9`, `3.1` for Colosseum, `3.2` for XD) |
| `legal` | `1` for legal, `0` for illegal |
| `shiny` | `1` for shiny, `0` for regular |
| `species` | Filter by species ID |
| `sort` | `recent` (default), `dl`, `level`, `az`, `id` |
| `page` | Page number (default `1`) |
| `limit` | Results per page (default `40`, max `100`) |

**Response:**

```json
{
  "total": 91372,
  "page": 1,
  "pages": 3808,
  "pokemon": [{ ... }, { ... }]
}
```

## Pokemon detail

```
GET /api/pokemon/{id}
```

Returns full detail for a single Pokemon including stats, moves, types, Showdown paste, and sprite URLs.

## Legality check (by ID)

```
GET /api/pokemon/{id}/legality
```

Runs a live PKHeX legality check on a Pokemon already in the database.

**Response:**

```json
{
  "legal": true,
  "legal_db": true,
  "live": true,
  "report": [],
  "generation_checked": "9"
}
```

## Download

```
GET /api/pokemon/{id}/download
```

Download the raw `.pkm` binary file.

## Stats

```
GET /api/stats
```

Database summary: total count, legal count, per-generation breakdown, service status.

## Server status

```
GET /api/status
```

Engine version, database size, service health (GPSS, legality, sprites).

## Update check

```
GET /api/updates
```

Check if a newer PKHeX engine version is available on GitHub.

## GPSS proxy

```
* /api/v2/*
```

All requests under `/api/v2/` are proxied to the Go GPSS server. This is what PKSM on the 3DS talks to.
