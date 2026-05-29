"""Search index building and management."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from pkm import clean, effective_nickname, parse_pokemon, sanitize_pkm_string

INDEX_VERSION = "7"

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT.parent / ".local" / "local-gpss.db"


def db_path() -> Path:
    return Path(os.environ.get("GPSS_DB", DEFAULT_DB))


def index_path() -> Path:
    if os.environ.get("GPSS_INDEX"):
        return Path(os.environ["GPSS_INDEX"])
    return db_path().parent / "viewer-index.db"


def ensure_index(source: Path, dex) -> sqlite3.Connection:
    """Build or reuse the search index for the given source database."""
    idx_path = index_path()
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    src_mtime = source.stat().st_mtime if source.exists() else 0
    rebuild = True
    if idx_path.exists():
        idx = sqlite3.connect(idx_path, check_same_thread=False)
        idx.row_factory = sqlite3.Row
        meta_mtime = idx.execute(
            "SELECT value FROM meta WHERE key='source_mtime'"
        ).fetchone()
        meta_ver = idx.execute(
            "SELECT value FROM meta WHERE key='index_version'"
        ).fetchone()
        if (
            meta_mtime
            and float(meta_mtime["value"]) == src_mtime
            and meta_ver
            and meta_ver["value"] == INDEX_VERSION
        ):
            count = idx.execute("SELECT COUNT(*) c FROM pokemon_index").fetchone()["c"]
            if count > 0:
                rebuild = False
        if not rebuild:
            return idx
        idx.close()
        idx_path.unlink()

    print(f"Building search index from {source} …", flush=True)
    t0 = time.time()
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    idx = sqlite3.connect(idx_path, check_same_thread=False)
    idx.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE pokemon_index (
            id INTEGER PRIMARY KEY,
            species_id INTEGER,
            species_name TEXT,
            nickname TEXT,
            original_trainer TEXT,
            download_code TEXT,
            generation TEXT,
            legal INTEGER,
            shiny INTEGER,
            level INTEGER,
            upload_datetime TEXT,
            download_count INTEGER
        );
        CREATE INDEX idx_species ON pokemon_index(species_name);
        CREATE INDEX idx_gen ON pokemon_index(generation);
        CREATE INDEX idx_legal ON pokemon_index(legal);
        """
    )
    batch: list[tuple] = []
    total = 0
    for row in src.execute(
        "SELECT id, base_64, generation, legal, download_code, upload_datetime, "
        "download_count FROM pokemons"
    ):
        parsed = parse_pokemon(row["base_64"], row["generation"])
        sid = parsed["species_id"]
        batch.append(
            (
                row["id"],
                sid,
                clean(dex.species_name(sid)),
                clean(
                    effective_nickname(
                        parsed["nickname"], dex.species_name(sid)
                    )
                ),
                clean(sanitize_pkm_string(parsed["original_trainer"])),
                row["download_code"],
                row["generation"],
                int(row["legal"]),
                int(parsed["shiny"]),
                parsed["level"],
                row["upload_datetime"],
                int(row["download_count"] or 0),
            )
        )
        if len(batch) >= 2000:
            idx.executemany(
                """INSERT INTO pokemon_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                batch,
            )
            total += len(batch)
            batch.clear()
            print(f"  … {total}", flush=True)
    if batch:
        idx.executemany(
            """INSERT INTO pokemon_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            batch,
        )
        total += len(batch)
    idx.execute(
        "INSERT INTO meta VALUES ('source_mtime', ?), ('index_version', ?)",
        (str(src_mtime), INDEX_VERSION),
    )
    idx.commit()
    src.close()
    print(f"Index ready: {total} Pokémon in {time.time() - t0:.1f}s", flush=True)
    idx.row_factory = sqlite3.Row
    return idx
