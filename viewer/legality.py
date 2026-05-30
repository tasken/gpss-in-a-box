"""Legality checking via GpssConsole binary or GPSS HTTP API."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from pkm import wrap_gen1_party_for_legality, wrap_gen2_party_for_legality

_KNOWN_LEGALITY_GENS = frozenset(
    {"1", "2", "3", "4", "5", "6", "7", "8", "9", "BDSP", "PLA", "GO"}
)

ROOT = Path(__file__).resolve().parent


def legality_generation(generation: str) -> str:
    """Map DB generation (e.g. 3.2) to a value GpssConsole accepts."""
    if generation in _KNOWN_LEGALITY_GENS:
        return generation
    major = generation.split(".")[0]
    if major in _KNOWN_LEGALITY_GENS:
        return major
    return major


def gpss_console_bin() -> Path | None:
    """Find the GpssConsole binary, or None."""
    candidates = [
        os.environ.get("GPSS_CONSOLE"),
        "/app/bin/GpssConsole",
        ROOT.parent / "bin" / "GpssConsole",
        Path("bin/GpssConsole"),
    ]
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw)
        if path.is_file():
            return path
    return None


def _legality_via_console(generation: str, pkm_bytes: bytes) -> dict:
    """Run GpssConsole directly (returns PKHeX JSON, including error details)."""
    bin_path = gpss_console_bin()
    if not bin_path:
        raise FileNotFoundError("GpssConsole binary not found")

    b64 = base64.b64encode(pkm_bytes).decode("ascii")
    proc = subprocess.run(
        [
            str(bin_path),
            "--mode",
            "legality",
            "--pokemon",
            b64,
            "--generation",
            generation,
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        err = (proc.stderr or "").strip() or f"GpssConsole exited {proc.returncode}"
        raise RuntimeError(err)
    return json.loads(stdout)


def _gpss_legality_http(backend: str, generation: str, pkm_bytes: bytes) -> dict:
    """POST PKM bytes to GPSS /api/v2/pksm/legality."""
    boundary = f"----gpss-viewer-{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="pkmn"; filename="pkmn"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + pkm_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = backend.rstrip("/") + "/api/v2/pksm/legality"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("generation", generation)
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; gpss-viewer/1.0)")

    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _legality_payloads(pkm_bytes: bytes, generation: str) -> list[bytes]:
    """Candidate PKM byte buffers for PKHeX (Gen 1/2 party needs list wrap)."""
    major = generation.split(".")[0]
    if major == "1" and len(pkm_bytes) == 44:
        return [wrap_gen1_party_for_legality(pkm_bytes)]
    if major == "2" and len(pkm_bytes) == 48:
        return [wrap_gen2_party_for_legality(pkm_bytes)]
    return [pkm_bytes]


def _is_generic_gpss_error(msg: str) -> bool:
    return msg.strip().lower() == "gpss console returned an error"


def _legalize_via_console(generation: str, pkm_bytes: bytes, version: str) -> dict:
    """Run GpssConsole in legalize mode."""
    bin_path = gpss_console_bin()
    if not bin_path:
        raise FileNotFoundError("GpssConsole binary not found")

    b64 = base64.b64encode(pkm_bytes).decode("ascii")
    proc = subprocess.run(
        [
            str(bin_path),
            "--mode",
            "legalize",
            "--pokemon",
            b64,
            "--generation",
            generation,
            "--ver",
            version,
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        err = (proc.stderr or "").strip() or f"GpssConsole exited {proc.returncode}"
        raise RuntimeError(err)
    return json.loads(stdout)


def legalize_pkm(generation: str, pkm_bytes: bytes, version: str) -> dict:
    """Auto-legalize a Pokemon via GpssConsole."""
    gen = legality_generation(generation)
    for payload in _legality_payloads(pkm_bytes, generation):
        try:
            return _legalize_via_console(gen, payload, version)
        except (json.JSONDecodeError, RuntimeError, OSError) as err:
            return {"error": str(err)}
    return {"error": "Could not parse PKM for legalization"}


def legality_check_pkm(
    generation: str, pkm_bytes: bytes, backend: str | None
) -> dict:
    """Run PKHeX legality via GpssConsole (preferred) or GPSS HTTP."""
    gen = legality_generation(generation)
    console_err: str | None = None

    for payload in _legality_payloads(pkm_bytes, generation):
        if gpss_console_bin() is not None:
            try:
                result = _legality_via_console(gen, payload)
                if "error" not in result:
                    return result
                console_err = str(result["error"])
            except (json.JSONDecodeError, RuntimeError, OSError) as err:
                console_err = str(err)
        break  # one wrapped payload is enough

    if console_err and not _is_generic_gpss_error(console_err):
        return {"error": console_err}

    if backend:
        for payload in _legality_payloads(pkm_bytes, generation):
            try:
                result = _gpss_legality_http(backend, gen, payload)
                if "error" not in result:
                    return result
                http_err = str(result["error"])
                if not _is_generic_gpss_error(http_err):
                    return result
            except urllib.error.HTTPError as err:
                body = err.read().decode("utf-8", errors="replace")
                try:
                    http_err = json.loads(body).get("error", body)
                except json.JSONDecodeError:
                    http_err = body or err.reason or str(err)
                if not _is_generic_gpss_error(str(http_err)):
                    return {"error": str(http_err)}
            except Exception as err:
                if not _is_generic_gpss_error(str(err)):
                    return {"error": str(err)}

    if console_err:
        return {"error": console_err}
    return {"error": "Could not parse PKM for legality check"}
