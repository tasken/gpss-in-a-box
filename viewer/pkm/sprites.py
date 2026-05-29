"""Sprite URL generation (local: Showdown animated + pokesprite fallback)."""
from __future__ import annotations

FALLBACK_SPRITE_URL = "/sprites/pokemon-gen8/unknown.png"
EGG_SPRITE_URL = "/sprites/pokemon-gen8/egg.png"

_GEN1_PARTY_SIZE = 44
_GEN1_LIST_SIZE = 69  # 1 + 1 + 1 + 44 + 11(OT) + 11(Nick)
_GEN2_PARTY_SIZE = 48
_GEN2_LIST_SIZE = 73  # 1 + 1 + 1 + 48 + 11(OT) + 11(Nick)


def sprite_url_for(species_id: int, slug: str, generation: str, shiny: bool = False) -> str:
    """Animated GIF URL (Showdown slug format)."""
    if species_id <= 0 or slug == "missingno":
        return FALLBACK_SPRITE_URL
    folder = "ani-shiny" if shiny else "ani"
    return f"/sprites/{folder}/{slug}.gif"


def sprite_url_static(species_id: int, slug: str, generation: str, shiny: bool = False) -> str:
    """Static PNG fallback (pokesprite slug format)."""
    if species_id <= 0 or slug == "unknown":
        return FALLBACK_SPRITE_URL
    folder = "shiny" if shiny else "regular"
    return f"/sprites/pokemon-gen8/{folder}/{slug}.png"


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
