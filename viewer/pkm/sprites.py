"""Sprite URL generation (local: Showdown animated + pokesprite fallback)."""
from __future__ import annotations

import os
from pathlib import Path

FALLBACK_SPRITE_URL = "/sprites/pokemon-gen8/unknown.png"
EGG_SPRITE_URL = "/sprites/pokemon-gen8/egg.png"

_GEN1_PARTY_SIZE = 44
_GEN1_LIST_SIZE = 69  # 1 + 1 + 1 + 44 + 11(OT) + 11(Nick)
_GEN2_PARTY_SIZE = 48
_GEN2_LIST_SIZE = 73  # 1 + 1 + 1 + 48 + 11(OT) + 11(Nick)


def get_sprites_dir() -> Path:
    """Locate the sprites directory."""
    env = os.environ.get("SPRITES_DIR")
    if env:
        return Path(env)
    docker_path = Path("/app/sprites")
    if docker_path.is_dir():
        return docker_path
    db = os.environ.get("GPSS_DB")
    if db:
        return Path(db).parent / "sprites"
    return Path(__file__).resolve().parent.parent.parent / ".local" / "sprites"


def sprite_url_for(species_id: int, slug: str, generation: str, shiny: bool = False, sprite_slug: str | None = None) -> str:
    """Animated GIF URL (Showdown slug format) with static PNG fallback if missing."""
    if species_id <= 0 or slug == "missingno":
        return FALLBACK_SPRITE_URL

    # Smogon/Showdown CDN filename anomalies
    NORMALIZED_SLUGS = {
        "porygonz": "porygon-z",
    }

    slug_norm = NORMALIZED_SLUGS.get(slug, slug)

    # Handle Nidoran anomalies
    if slug == "nidoranf":
        slug_norm = "nidoran_f" if shiny else "nidoran-f"
    elif slug == "nidoranm":
        slug_norm = "nidoran_m" if shiny else "nidoranm"

    # Handle hooh / ho-oh shiny naming drift
    if slug == "hooh" and shiny:
        slug_norm = "ho-oh"
    elif slug == "ho-oh" and not shiny:
        slug_norm = "hooh"

    folder = "ani-shiny" if shiny else "ani"

    # Check if the animated GIF actually exists on disk
    sprites_dir = get_sprites_dir()
    gif_file = sprites_dir / folder / f"{slug_norm}.gif"
    if gif_file.is_file():
        return f"/sprites/{folder}/{slug_norm}.gif"

    # Otherwise, fall back to the static PNG
    fallback_slug = sprite_slug if sprite_slug is not None else slug
    return sprite_url_static(species_id, fallback_slug, generation, shiny)


def sprite_url_static(species_id: int, slug: str, generation: str, shiny: bool = False) -> str:
    """Static PNG fallback (pokesprite slug format)."""
    if species_id <= 0 or slug == "unknown":
        return FALLBACK_SPRITE_URL
    folder = "shiny" if shiny else "regular"
    sprites_dir = get_sprites_dir()
    png_file = sprites_dir / "pokemon-gen8" / folder / f"{slug}.png"
    if png_file.is_file():
        return f"/sprites/pokemon-gen8/{folder}/{slug}.png"
    return FALLBACK_SPRITE_URL


def _wrap_gen12_party(data: bytes, party_size: int, list_size: int) -> bytes:
    """Wrap a Gen 1/2 party struct into the list format PKHeX expects.

    Gen 1/2 use 0x50 as string terminator for OT name and nickname."""
    out = bytearray(list_size)
    out[0] = 1                                       # party count
    out[1] = data[0] if data[0] else 0xFF            # species
    out[2] = 0xFF                                     # list terminator
    out[3:3 + party_size] = data                      # party data
    ot_offset = 3 + party_size
    nick_offset = ot_offset + 11
    out[ot_offset] = 0x50
    out[nick_offset] = 0x50
    return bytes(out)


def wrap_gen1_party_for_legality(data: bytes) -> bytes:
    if len(data) != _GEN1_PARTY_SIZE:
        return data
    return _wrap_gen12_party(data, _GEN1_PARTY_SIZE, _GEN1_LIST_SIZE)


def wrap_gen2_party_for_legality(data: bytes) -> bytes:
    if len(data) != _GEN2_PARTY_SIZE:
        return data
    return _wrap_gen12_party(data, _GEN2_PARTY_SIZE, _GEN2_LIST_SIZE)
