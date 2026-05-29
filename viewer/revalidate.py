#!/usr/bin/env python3
"""Batch re-check legality for all Pokemon in the database via GpssConsole.

Uses parallel workers for throughput. Each worker spawns GpssConsole processes
and recycles after a batch (default 500) to avoid .NET memory buildup.

Usage (inside Docker):
    python3 /app/viewer/revalidate.py --db /app/host/.local/local-gpss.db

Usage (local, if GpssConsole is available):
    python3 viewer/revalidate.py --db .local/local-gpss.db
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from legality import gpss_console_bin, legality_generation
from pkm import wrap_gen1_party_for_legality, wrap_gen2_party_for_legality


def find_console() -> Path:
    p = gpss_console_bin()
    if p:
        return p
    print("ERROR: GpssConsole not found. Run this inside the Docker container", file=sys.stderr)
    print("  docker compose exec local-gpss python3 /app/viewer/revalidate.py --db /app/host/.local/local-gpss.db", file=sys.stderr)
    sys.exit(1)


def check_one(console: Path, generation: str, pkm_bytes: bytes) -> dict:
    gen = legality_generation(generation)
    major = generation.split(".")[0]

    if major == "1" and len(pkm_bytes) == 44:
        pkm_bytes = wrap_gen1_party_for_legality(pkm_bytes)
    elif major == "2" and len(pkm_bytes) == 48:
        pkm_bytes = wrap_gen2_party_for_legality(pkm_bytes)

    b64 = base64.b64encode(pkm_bytes).decode("ascii")
    proc = subprocess.run(
        [str(console), "--mode", "legality", "--pokemon", b64, "--generation", gen],
        capture_output=True, text=True, timeout=90,
    )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {"error": (proc.stderr or "").strip() or f"exit {proc.returncode}"}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"error": stdout[:200]}


def main():
    parser = argparse.ArgumentParser(description="Batch re-validate Pokemon legality")
    parser.add_argument("--db", type=Path, required=True, help="Path to local-gpss.db")
    parser.add_argument("--skip-gen12", action="store_true", default=True,
                        help="Skip Gen 1/2 (default: true)")
    parser.add_argument("--include-gen12", action="store_true",
                        help="Include Gen 1/2 (will fail on OT/nickname)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check but don't update the database")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only check N Pokemon (0 = all)")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel workers (default: 8)")
    parser.add_argument("--reverse", action="store_true",
                        help="Check newest Pokemon first")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"ERROR: Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    console = find_console()
    print(f"GpssConsole: {console}")
    print(f"Database: {args.db}")
    print(f"Workers: {args.workers}")

    db = sqlite3.connect(str(args.db))
    db.row_factory = sqlite3.Row

    where = "1=1"
    if not args.include_gen12:
        where = "generation NOT LIKE '1%' AND generation NOT LIKE '2%'"

    order = "id DESC" if args.reverse else "id"
    query = f"SELECT id, base_64, generation, legal FROM pokemons WHERE {where} ORDER BY {order}"
    if args.limit:
        query += f" LIMIT {args.limit}"

    print("Querying database...", flush=True)
    rows = db.execute(query).fetchall()
    total = len(rows)
    print(f"Pokemon to check: {total}")
    if args.dry_run:
        print("DRY RUN — no database updates")
    print(flush=True)

    lock = threading.Lock()
    stats = {"done": 0, "changed": 0, "errors": 0,
             "flipped_legal": 0, "flipped_illegal": 0}
    updates: list[tuple[int, int]] = []
    start = time.time()

    def process_one(row):
        pid = row["id"]
        gen = row["generation"]
        old_legal = bool(row["legal"])
        pkm_bytes = base64.b64decode(row["base_64"])

        try:
            result = check_one(console, gen, pkm_bytes)
        except Exception as e:
            with lock:
                stats["errors"] += 1
                if stats["errors"] <= 5:
                    print(f"  ERROR id={pid} gen={gen}: {e}", flush=True)
            return

        if "error" in result:
            with lock:
                stats["errors"] += 1
                if stats["errors"] <= 5:
                    print(f"  ERROR id={pid} gen={gen}: {result['error'][:100]}", flush=True)
            return

        new_legal = bool(result.get("legal", False))

        with lock:
            if new_legal != old_legal:
                stats["changed"] += 1
                direction = "illegal→legal" if new_legal else "legal→illegal"
                if new_legal:
                    stats["flipped_legal"] += 1
                else:
                    stats["flipped_illegal"] += 1

                report = result.get("report", [])
                if stats["changed"] <= 20:
                    print(f"  CHANGED id={pid} gen={gen}: {direction}", flush=True)
                    if report and not new_legal:
                        for line in report[:3]:
                            print(f"    {line}", flush=True)

                if not args.dry_run:
                    updates.append((1 if new_legal else 0, pid))

            stats["done"] += 1
            done = stats["done"]
            interval = 50 if total <= 500 else 500
            if done % interval == 0 or done == total:
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                pct = done * 100 // total
                print(f"  [{pct:3d}%] {done}/{total} — {rate:.0f}/s — "
                      f"ETA {eta:.0f}s — {stats['changed']} changed, "
                      f"{stats['errors']} errors", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(process_one, row) for row in rows]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass

    if not args.dry_run and updates:
        db.executemany("UPDATE pokemons SET legal = ? WHERE id = ?", updates)
        db.commit()

    elapsed = time.time() - start
    print()
    print(f"Done in {elapsed:.1f}s")
    print(f"  Checked:  {total}")
    print(f"  Changed:  {stats['changed']} ({stats['flipped_legal']} now legal, {stats['flipped_illegal']} now illegal)")
    print(f"  Errors:   {stats['errors']}")
    if args.dry_run:
        print(f"  (dry run — no updates written)")

    db.close()


if __name__ == "__main__":
    main()
