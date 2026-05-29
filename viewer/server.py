#!/usr/bin/env python3
"""Local GPSS Pokemon database viewer — bootstrap and server lifecycle."""
from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from http.server import HTTPServer, ThreadingHTTPServer
from pathlib import Path

from dex import DexData
from index import db_path, ensure_index
from routes import Handler

ROOT = Path(__file__).resolve().parent
VIEWER_PORT = 8082

_WATCH_EXTS = frozenset({".py", ".html", ".css", ".js"})
_WATCH_ROOTS = (ROOT, ROOT / "static")


def _default_bind() -> tuple[str, int]:
    host = os.environ.get("VIEWER_HOST", "0.0.0.0")
    port = int(os.environ.get("VIEWER_PORT", str(VIEWER_PORT)))
    return host, port


def _local_ipv4_addresses() -> list[str]:
    seen: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                seen.add(ip)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            seen.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(seen)


def _print_listen_urls(host: str, port: int) -> None:
    print(f"Viewer at http://127.0.0.1:{port}/", flush=True)
    if host in ("", "0.0.0.0"):
        for ip in _local_ipv4_addresses():
            print(f"  LAN  http://{ip}:{port}/", flush=True)
    elif host not in ("127.0.0.1", "localhost"):
        print(f"  bind http://{host}:{port}/", flush=True)


def _watch_snapshot() -> dict[str, float]:
    snap: dict[str, float] = {}
    for base in _WATCH_ROOTS:
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.suffix.lower() not in _WATCH_EXTS or not path.is_file():
                continue
            try:
                snap[str(path.resolve())] = path.stat().st_mtime
            except OSError:
                pass
    return snap


def _run_reloader() -> None:
    """Restart server.py when viewer source/static files change."""
    argv = [sys.executable, str(Path(__file__).resolve())]
    argv.extend(a for a in sys.argv[1:] if a not in ("--reload", "--no-reload"))
    child_env = {**os.environ, "VIEWER_RELOAD_CHILD": "1"}
    child: subprocess.Popen[bytes] | None = None

    def stop_child() -> None:
        nonlocal child
        if child is None or child.poll() is not None:
            return
        child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        child = None

    print(
        "Auto-reload enabled (.py .html .css .js under viewer/) · Ctrl+C to quit",
        flush=True,
    )
    baseline = _watch_snapshot()
    try:
        while True:
            if child is None or child.poll() is not None:
                code = child.returncode if child is not None else 0
                if child is not None and code not in (0, -signal.SIGTERM, -2):
                    sys.exit(code or 1)
                child = subprocess.Popen(argv, env=child_env)
                baseline = _watch_snapshot()

            time.sleep(0.4)
            current = _watch_snapshot()
            if current == baseline:
                continue
            for path in sorted(set(current) | set(baseline)):
                if current.get(path) != baseline.get(path):
                    print(f"\n↻ reload ({Path(path).name})", flush=True)
                    break
            stop_child()
            baseline = _watch_snapshot()
    except KeyboardInterrupt:
        stop_child()
        print("\nStopped.", flush=True)


def main() -> None:
    from routes import _runtime_mode
    runtime = _runtime_mode()
    default_host, default_port = _default_bind()

    parser = argparse.ArgumentParser(description="GPSS Pokemon viewer")
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument(
        "--gpss-backend",
        default=os.environ.get("GPSS_BACKEND", ""),
    )
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    use_reload = args.reload and not args.no_reload
    if use_reload and os.environ.get("VIEWER_RELOAD_CHILD") != "1":
        return _run_reloader()

    import sqlite3

    source_path = args.db or db_path()
    if not source_path.is_file():
        print(f"Database not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    print("Loading dex data …", flush=True)
    dex = DexData()
    index = ensure_index(source_path, dex)
    source = sqlite3.connect(
        f"file:{source_path}?mode=ro", uri=True, check_same_thread=False
    )
    source.row_factory = sqlite3.Row

    Handler.dex = dex
    Handler.index = index
    Handler.source = source
    Handler.gpss_backend = args.gpss_backend
    Handler._source_path = source_path

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Runtime: {runtime} · db {source_path}", flush=True)
    _print_listen_urls(args.host, args.port)
    if args.gpss_backend:
        print(f"GPSS API proxied at /api/v2/ → {args.gpss_backend}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    if (
        "--reload" in sys.argv
        and "--no-reload" not in sys.argv
        and os.environ.get("VIEWER_RELOAD_CHILD") != "1"
    ):
        _run_reloader()
    else:
        main()
