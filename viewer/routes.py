"""HTTP request handler with all route handlers."""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dex import DexData, SPRITES_DIR
from pokepaste import export_showdown_set
from legality import (
    gpss_console_bin,
    legality_check_pkm,
    legality_generation,
    legalize_pkm,
)
from pkm import (
    effective_nickname,
    parse_pokemon,
    sanitize_pkm_string,
    sprite_url_for,
    sprite_url_static,
)

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

_SPRITE_CONTENT_TYPES = {
    ".png": "image/png",
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
}

_update_cache: dict = {"checked_at": 0, "result": None}


def _engine_version() -> str:
    db_file = Path(os.environ.get("GPSS_DB", ""))
    if not str(db_file):
        return "unknown"
    version_file = db_file.parent / "pkhex_version"
    if version_file.is_file():
        return version_file.read_text().strip()
    return "unknown"


def _runtime_mode() -> str:
    """``local`` (CLI / run.sh) or ``docker`` (container entrypoint)."""
    explicit = os.environ.get("GPSS_RUNTIME", "").strip().lower()
    if explicit in ("docker", "container"):
        return "docker"
    if explicit in ("local", "dev", "cli"):
        return "local"
    if Path("/.dockerenv").is_file():
        return "docker"
    if str(ROOT).startswith("/app/"):
        return "docker"
    return "local"


def _probe_http(url: str, timeout: float = 2.0) -> bool:
    """True if host responds (any HTTP status below 500)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as err:
        return err.code < 500
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _service_status(gpss_backend: str) -> dict:
    """Live status for status bar (GPSS HTTP vs viewer-only)."""
    console = gpss_console_bin()
    gpss: dict = {"configured": bool(gpss_backend), "online": False}
    if gpss_backend:
        base = gpss_backend.rstrip("/")
        gpss["online"] = _probe_http(f"{base}/api/v2/pksm/legality") or _probe_http(
            base
        )
        gpss["detail"] = "connected" if gpss["online"] else "unreachable"
    else:
        gpss["detail"] = "not configured"

    if gpss["online"]:
        legality_mode = "gpss"
    elif console is not None:
        legality_mode = "console"
    else:
        legality_mode = "none"

    has_ani = (SPRITES_DIR / "ani").is_dir()
    has_box = (SPRITES_DIR / "pokemon-gen8" / "regular").is_dir()
    sprites_ok = has_ani or has_box
    return {
        "runtime": _runtime_mode(),
        "gpss": gpss,
        "legality": {
            "available": gpss["online"] or console is not None,
            "mode": legality_mode,
        },
        "sprites": {
            "source": "pokesprite",
            "online": sprites_ok,
        },
    }


def row_to_entry(row: sqlite3.Row, dex: DexData, include_b64: bool = False) -> dict:
    """Convert a database row to an API response entry."""
    parsed = parse_pokemon(row["base_64"], row["generation"])
    sid = parsed["species_id"]
    gen = row["generation"]
    slug = dex.num_to_slug.get(sid, "missingno")
    sprite_sl = dex.sprite_slug(sid)
    shiny = parsed["shiny"]
    species_name = dex.species_name(sid)
    nickname = effective_nickname(parsed["nickname"], species_name)
    original_trainer = sanitize_pkm_string(parsed["original_trainer"])

    entry = {
        "id": row["id"],
        "upload_datetime": row["upload_datetime"],
        "download_code": row["download_code"],
        "download_count": row["download_count"],
        "generation": gen,
        "legal": bool(row["legal"]),
        "species_id": sid,
        "species_name": species_name,
        "species_slug": slug,
        "sprite_url": sprite_url_for(sid, slug, gen, shiny, sprite_slug=sprite_sl),
        "sprite_url_static": sprite_url_static(sid, sprite_sl, gen, shiny),
        "form": parsed["form"],
        "gender": parsed["gender"],
        "level": parsed["level"],
        "nickname": nickname,
        "original_trainer": original_trainer,
        "tid": parsed["tid"],
        "sid": parsed["sid"],
        "pid": parsed["pid"],
        "shiny": shiny,
        "held_item": dex.item_name(parsed["held_item_id"]),
        "held_item_id": parsed["held_item_id"],
        "held_item_slug": dex.item_slug(parsed["held_item_id"]),
        "held_item_sprite": dex.item_sprite(parsed["held_item_id"]),
        "ability": dex.ability_name(parsed["ability_id"]),
        "nature": dex.nature_name(parsed["nature_id"]),
        "moves": [dex.move_name(m) for m in parsed["moves"] if m],
        "move_ids": parsed["moves"],
        "move_pp": parsed["move_pp"],
        "is_egg": parsed["is_egg"],
        "ball_id": parsed["ball_id"],
        "met_level": parsed["met_level"],
        "ivs": parsed["ivs"],
        "evs": parsed.get("evs", {}),
        "language": parsed["language"],
        "parse_layout": parsed["parse_layout"],
        "types": dex.species_types(sid),
        "base_stats": dex.species_base_stats(sid),
        "ball_name": dex.ball_name(parsed["ball_id"]),
        "ball_slug": dex.ball_slug(parsed["ball_id"]),
        "ball_sprite": dex.ball_sprite(parsed["ball_id"]),
        "language_name": dex.language_name(parsed["language"]),
        "nature_plus": dex.nature_stats(parsed["nature_id"])[0],
        "nature_minus": dex.nature_stats(parsed["nature_id"])[1],
        "form_name": dex.form_name(sid, parsed["form"]),
    }
    if include_b64:
        entry["base_64"] = row["base_64"]
    return entry


class Handler(BaseHTTPRequestHandler):
    """HTTP handler for the viewer API and static files."""

    dex: DexData
    index: sqlite3.Connection
    source: sqlite3.Connection
    gpss_backend: str = ""
    _source_path: Path | None = None
    _last_index_check: float = 0
    _index_lock = threading.Lock()

    def _maybe_refresh_index(self) -> None:
        now = time.time()
        if now - Handler._last_index_check < 5:
            return
        with Handler._index_lock:
            if now - Handler._last_index_check < 5:
                return
            Handler._last_index_check = now
            src = Handler._source_path
            if src is None or not src.exists():
                return
            cur_mtime = src.stat().st_mtime
            stored = Handler.index.execute(
                "SELECT value FROM meta WHERE key='source_mtime'"
            ).fetchone()
            if stored and float(stored["value"]) == cur_mtime:
                return
            from index import ensure_index
            old = Handler.index
            Handler.index = ensure_index(src, Handler.dex)
            try:
                old.close()
            except Exception:
                pass

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str, cache: str = "") -> None:
        resolved = path.resolve()
        if not str(resolved).startswith(str(STATIC.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not resolved.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def _sprite(self, rel: str) -> None:
        fp = (SPRITES_DIR / rel).resolve()
        if not str(fp).startswith(str(SPRITES_DIR.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not fp.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        ct = _SPRITE_CONTENT_TYPES.get(fp.suffix.lower(), "application/octet-stream")
        data = fp.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=604800, immutable")
        self.end_headers()
        self.wfile.write(data)

    def _should_proxy_gpss(self) -> bool:
        return bool(self.gpss_backend) and self.path.startswith("/api/v2")

    def _proxy_gpss(self) -> None:
        parsed = urlparse(self.path)
        url = self.gpss_backend.rstrip("/") + parsed.path
        if parsed.query:
            url += "?" + parsed.query

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None

        req = urllib.request.Request(url, data=body, method=self.command)
        skip = {"host", "connection", "transfer-encoding", "content-length"}
        for key, val in self.headers.items():
            if key.lower() not in skip:
                req.add_header(key, val)

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as err:
            data = err.read()
            self.send_response(err.code)
            for key, val in err.headers.items():
                if key.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(key, val)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except OSError as err:
            self._json(502, {"error": f"GPSS backend unreachable: {err}"})

    def do_GET(self) -> None:
        if self._should_proxy_gpss():
            return self._proxy_gpss()

        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            return self._file(STATIC / "index.html", "text/html; charset=utf-8")
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            fp = STATIC / rel
            ct = "text/css" if rel.endswith(".css") else "application/javascript"
            return self._file(fp, f"{ct}; charset=utf-8", cache="public, max-age=3600")
        if path.startswith("/sprites/"):
            return self._sprite(path[len("/sprites/"):])

        if path == "/api/stats":
            total = self.index.execute(
                "SELECT COUNT(*) c FROM pokemon_index"
            ).fetchone()["c"]
            legal_count = self.index.execute(
                "SELECT COUNT(*) c FROM pokemon_index WHERE legal = 1"
            ).fetchone()["c"]
            gens = [
                dict(r)
                for r in self.index.execute(
                    "SELECT generation g, COUNT(*) n FROM pokemon_index "
                    "GROUP BY generation ORDER BY n DESC"
                )
            ]
            return self._json(
                200,
                {
                    "total": total,
                    "legal_count": legal_count,
                    "generations": gens,
                    "services": _service_status(self.gpss_backend),
                },
            )

        if path == "/api/status":
            return self._status()

        if path == "/api/updates":
            return self._updates()

        if path == "/api/pokemon":
            return self._search(parsed.query)

        if path.startswith("/api/pokemon/"):
            parts = [p for p in path.split("/") if p]
            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "pokemon"
                and parts[3] == "download"
                and parts[2].isdigit()
            ):
                return self._download(int(parts[2]))
            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "pokemon"
                and parts[3] == "legality"
                and parts[2].isdigit()
            ):
                return self._legality(int(parts[2]))
            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "pokemon"
                and parts[3] == "legalize"
                and parts[2].isdigit()
            ):
                return self._legalize_id(int(parts[2]))
            pid = parts[-1] if parts else ""
            if pid.isdigit():
                return self._detail(int(pid))
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self._should_proxy_gpss():
            return self._proxy_gpss()

        parsed = urlparse(self.path)
        if parsed.path == "/api/legality":
            return self._legality_check()
        if parsed.path == "/api/legalize":
            return self._legalize()

        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def _legality_check(self) -> None:
        """Standalone legality check: POST raw PKM bytes + generation header."""
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return self._json(400, {"error": "empty body"})
        if length > 1_000_000:
            return self._json(413, {"error": "payload too large"})

        generation = self.headers.get("X-Generation", "").strip()
        if not generation:
            return self._json(400, {"error": "missing X-Generation header"})

        pkm_bytes = self.rfile.read(length)

        if not self.gpss_backend and gpss_console_bin() is None:
            return self._json(503, {"error": "legality engine not available"})

        try:
            result = legality_check_pkm(
                generation, pkm_bytes, self.gpss_backend or None
            )
            if "error" in result:
                return self._json(200, {
                    "legal": False,
                    "report": [str(result["error"])],
                    "error": str(result["error"]),
                })
            report = [
                line.strip()
                for line in result.get("report", [])
                if line and line.strip() and line.strip() != "Legal!"
            ]
            return self._json(200, {
                "legal": bool(result.get("legal", False)),
                "report": report,
            })
        except Exception as err:
            return self._json(500, {"error": f"legality check failed: {err}"})

    def _legalize(self) -> None:
        """Auto-legalize a Pokemon: POST raw PKM bytes + generation + version."""
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return self._json(400, {"error": "empty body"})
        if length > 1_000_000:
            return self._json(413, {"error": "payload too large"})

        generation = self.headers.get("X-Generation", "").strip()
        if not generation:
            return self._json(400, {"error": "missing X-Generation header"})

        version = self.headers.get("X-Version", "Any").strip()

        pkm_bytes = self.rfile.read(length)

        if gpss_console_bin() is None:
            return self._json(503, {"error": "legality engine not available"})

        try:
            check = legality_check_pkm(generation, pkm_bytes, None)
            report_before = [
                line.strip()
                for line in check.get("report", [])
                if line and line.strip() and line.strip() != "Legal!"
            ] if "error" not in check else []

            result = legalize_pkm(generation, pkm_bytes, version)
            if "error" in result:
                return self._json(200, {"error": str(result["error"])})
            report_after = [
                line.strip()
                for line in result.get("report", [])
                if line and line.strip() and line.strip() != "Legal!"
            ]
            return self._json(200, {
                "legal": bool(result.get("legal", False)),
                "modified": bool(result.get("ran", False)),
                "pokemon": result.get("pokemon"),
                "report_before": report_before,
                "report_after": report_after,
            })
        except Exception as err:
            return self._json(500, {"error": f"legalization failed: {err}"})

    _SORT_ORDERS = {
        "recent": "upload_datetime DESC, id DESC",
        "dl": "download_count DESC, id DESC",
        "level": "level DESC, id DESC",
        "az": "species_name ASC, id ASC",
        "id": "id DESC",
    }

    def _search(self, query: str) -> None:
        self._maybe_refresh_index()
        qs = parse_qs(query)
        q = (qs.get("q", [""])[0] or "").strip().lower()
        species_id = qs.get("species", [""])[0]
        gen = qs.get("gen", [""])[0]
        legal = qs.get("legal", [""])[0]
        shiny = qs.get("shiny", [""])[0]
        sort = qs.get("sort", ["recent"])[0] or "recent"
        try:
            page = max(1, int(qs.get("page", ["1"])[0] or 1))
            limit = min(100, max(1, int(qs.get("limit", ["40"])[0] or 40)))
        except (ValueError, TypeError):
            return self._json(400, {"error": "invalid page or limit"})

        offset = (page - 1) * limit

        clauses = ["1=1"]
        params: list = []
        if q:
            clauses.append(
                "(LOWER(species_name) LIKE ? OR LOWER(nickname) LIKE ? "
                "OR LOWER(original_trainer) LIKE ? OR download_code LIKE ? "
                "OR CAST(id AS TEXT) = ?)"
            )
            like = f"%{q}%"
            params.extend([like, like, like, f"%{q}%", q.lstrip("#")])
        if species_id:
            clauses.append("species_id = ?")
            params.append(species_id)
        if gen:
            clauses.append("generation = ?")
            params.append(gen)
        if legal == "1":
            clauses.append("legal = 1")
        elif legal == "0":
            clauses.append("legal = 0")
        if shiny == "1":
            clauses.append("shiny = 1")
        elif shiny == "0":
            clauses.append("shiny = 0")

        where = " AND ".join(clauses)
        order = self._SORT_ORDERS.get(sort, self._SORT_ORDERS["recent"])
        total = self.index.execute(
            f"SELECT COUNT(*) c FROM pokemon_index WHERE {where}", params
        ).fetchone()["c"]
        ids = [
            r["id"]
            for r in self.index.execute(
                f"SELECT id FROM pokemon_index WHERE {where} "
                f"ORDER BY {order} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        ]
        if not ids:
            return self._json(
                200,
                {"total": total, "page": page, "pages": 0, "pokemon": []},
            )

        placeholders = ",".join("?" * len(ids))
        rows = {
            r["id"]: r
            for r in self.source.execute(
                f"SELECT * FROM pokemons WHERE id IN ({placeholders})",
                ids,
            )
        }
        ordered = [rows[i] for i in ids if i in rows]
        pokemon = [row_to_entry(r, self.dex) for r in ordered]
        pages = (total + limit - 1) // limit if total else 0
        self._json(
            200,
            {"total": total, "page": page, "pages": pages, "pokemon": pokemon},
        )

    def _detail(self, pid: int) -> None:
        row = self.source.execute(
            "SELECT * FROM pokemons WHERE id = ?", (pid,)
        ).fetchone()
        if not row:
            return self._json(404, {"error": "not found"})
        entry = row_to_entry(row, self.dex)
        entry["showdown_paste"] = export_showdown_set(entry)
        self._json(200, entry)

    def _legality(self, pid: int) -> None:
        row = self.source.execute(
            "SELECT id, base_64, generation, legal FROM pokemons WHERE id = ?",
            (pid,),
        ).fetchone()
        if not row:
            return self._json(404, {"error": "not found"})

        legal_db = bool(row["legal"])
        out: dict = {
            "legal_db": legal_db,
            "legal": legal_db,
            "report": [],
            "live": False,
            "generation_checked": legality_generation(row["generation"]),
            "message": None,
        }

        major = row["generation"].split(".")[0]
        is_gen12 = major in ("1", "2")

        if not self.gpss_backend and gpss_console_bin() is None:
            out["message"] = (
                "Live legality check requires GPSS (not connected). "
                "Showing database flag only."
            )
            return self._json(200, out)

        try:
            pkm_bytes = base64.b64decode(row["base_64"])
            result = legality_check_pkm(
                row["generation"], pkm_bytes, self.gpss_backend or None
            )
            if "error" in result:
                err = str(result["error"])
                if err == "not a pokemon!":
                    err = (
                        "PKHeX could not read this Pokémon's data "
                        f"(generation {row['generation']})."
                    )
                out["message"] = err
                out["report"] = [err]
                return self._json(200, out)
            report = [
                line.strip()
                for line in result.get("report", [])
                if line and line.strip()
            ]
            if is_gen12:
                _GEN12_DATA_GAPS = ("Nickname", "OT Name")
                report = [
                    f"{r} (not stored by GPSS)" if any(g in r for g in _GEN12_DATA_GAPS) else r
                    for r in report
                ]
                out["gen12_note"] = "Gen 1/2: OT name and nickname are not stored by GPSS — errors about those fields are expected."
            out["report"] = report
            out["legal"] = bool(result.get("legal", legal_db))
            out["live"] = True
        except Exception as err:
            out["message"] = f"Legality check failed: {err}"

        self._json(200, out)

    def _status(self) -> None:
        """Extended status: engine version, db size, uptime."""
        db_file = Path(os.environ.get("GPSS_DB", ""))
        db_size = db_file.stat().st_size if db_file.is_file() else 0
        total = self.index.execute(
            "SELECT COUNT(*) c FROM pokemon_index"
        ).fetchone()["c"]

        self._json(200, {
            "engine_version": _engine_version(),
            "db_size_bytes": db_size,
            "db_size_human": f"{db_size / 1024 / 1024:.1f} MB",
            "total_pokemon": total,
            "services": _service_status(self.gpss_backend),
        })

    def _updates(self) -> None:
        """Check for PKHeX engine updates (cached 1 hour)."""
        now = time.time()
        if _update_cache["result"] and now - _update_cache["checked_at"] < 3600:
            return self._json(200, _update_cache["result"])

        current = _engine_version()

        latest = None
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/santacrab2/PKHeX-Plugins/releases/latest",
                headers={"User-Agent": "gpss-viewer/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                latest = data.get("tag_name")
        except Exception:
            pass

        result = {
            "current_version": current,
            "latest_version": latest,
            "update_available": bool(
                latest and latest != current and current not in ("bundled", "unknown")
            ),
        }
        _update_cache["checked_at"] = now
        _update_cache["result"] = result
        self._json(200, result)

    def _download(self, pid: int) -> None:
        row = self.source.execute(
            "SELECT id, base_64, generation FROM pokemons WHERE id = ?", (pid,)
        ).fetchone()
        if not row:
            return self._json(404, {"error": "not found"})

        data = base64.b64decode(row["base_64"])
        parsed = parse_pokemon(row["base_64"], row["generation"])
        species = self.dex.species_name(parsed["species_id"])
        safe = "".join(c for c in species if c.isalnum() or c in "-_")
        filename = f"{safe}_{pid}.pkm" if safe else f"pokemon_{pid}.pkm"

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _legalize_id(self, pid: int) -> None:
        row = self.source.execute(
            "SELECT id, base_64, generation FROM pokemons WHERE id = ?", (pid,)
        ).fetchone()
        if not row:
            return self._json(404, {"error": "not found"})

        if gpss_console_bin() is None:
            return self._json(503, {"error": "legality engine not available"})

        try:
            pkm_bytes = base64.b64decode(row["base_64"])
            generation = row["generation"]

            check = legality_check_pkm(generation, pkm_bytes, None)
            report_before = [
                line.strip()
                for line in check.get("report", [])
                if line and line.strip() and line.strip() != "Legal!"
            ] if "error" not in check else []

            result = legalize_pkm(generation, pkm_bytes, "Any")
            if "error" in result:
                return self._json(200, {"error": str(result["error"])})

            report_after = [
                line.strip()
                for line in result.get("report", [])
                if line and line.strip() and line.strip() != "Legal!"
            ]

            return self._json(200, {
                "legal": bool(result.get("legal", False)),
                "modified": bool(result.get("ran", False)),
                "pokemon": result.get("pokemon"),
                "report_before": report_before,
                "report_after": report_after,
            })
        except Exception as err:
            return self._json(500, {"error": f"legalization failed: {err}"})


class LegalityOnlyHandler(BaseHTTPRequestHandler):
    """Minimal handler: only POST /api/legality."""

    gpss_backend: str = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/status":
            return self._json(200, {
                "mode": "legality-only",
                "engine": gpss_console_bin() is not None,
            })
        self.send_error(HTTPStatus.NOT_FOUND)

    def _read_pkm_request(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            self._json(400, {"error": "empty body"})
            return None, None, None
        if length > 1_000_000:
            self._json(413, {"error": "payload too large"})
            return None, None, None
        generation = self.headers.get("X-Generation", "").strip()
        if not generation:
            self._json(400, {"error": "missing X-Generation header"})
            return None, None, None
        if gpss_console_bin() is None:
            self._json(503, {"error": "legality engine not available"})
            return None, None, None
        pkm_bytes = self.rfile.read(length)
        return pkm_bytes, generation, self.headers.get("X-Version", "Any").strip()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/legality":
            pkm_bytes, generation, _ = self._read_pkm_request()
            if pkm_bytes is None:
                return
            try:
                result = legality_check_pkm(generation, pkm_bytes, None)
                if "error" in result:
                    return self._json(200, {
                        "legal": False,
                        "report": [str(result["error"])],
                        "error": str(result["error"]),
                    })
                report = [
                    line.strip()
                    for line in result.get("report", [])
                    if line and line.strip() and line.strip() != "Legal!"
                ]
                return self._json(200, {
                    "legal": bool(result.get("legal", False)),
                    "report": report,
                })
            except Exception as err:
                return self._json(500, {"error": f"legality check failed: {err}"})
        if path == "/api/legalize":
            pkm_bytes, generation, version = self._read_pkm_request()
            if pkm_bytes is None:
                return
            try:
                check = legality_check_pkm(generation, pkm_bytes, None)
                report_before = [
                    line.strip()
                    for line in check.get("report", [])
                    if line and line.strip() and line.strip() != "Legal!"
                ] if "error" not in check else []

                result = legalize_pkm(generation, pkm_bytes, version)
                if "error" in result:
                    return self._json(200, {"error": str(result["error"])})
                report_after = [
                    line.strip()
                    for line in result.get("report", [])
                    if line and line.strip() and line.strip() != "Legal!"
                ]
                return self._json(200, {
                    "legal": bool(result.get("legal", False)),
                    "modified": bool(result.get("ran", False)),
                    "pokemon": result.get("pokemon"),
                    "report_before": report_before,
                    "report_after": report_after,
                })
            except Exception as err:
                return self._json(500, {"error": f"legalization failed: {err}"})
        self.send_error(HTTPStatus.NOT_FOUND)
