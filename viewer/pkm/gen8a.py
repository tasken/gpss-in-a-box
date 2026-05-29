"""Gen 8.1 (PA8) parser — Pokémon Legends: Arceus, 376-byte party format."""
from __future__ import annotations
from .common import u16, u32, iv_field, is_shiny, default_out
from .strings import read_utf16


def parse_gen8a(raw: bytes) -> dict:
    """Parse PA8 (Legends: Arceus) — 376 bytes."""
    out = default_out("gen8a")
    out["species_id"] = u16(raw, 0x08)
    out["held_item_id"] = u16(raw, 0x0A)
    out["tid"] = u16(raw, 0x0C)
    out["sid"] = u16(raw, 0x0E)
    out["ability_id"] = u16(raw, 0x14)
    out["pid"] = u32(raw, 0x1C)
    out["nature_id"] = raw[0x20]
    out["stat_nature_id"] = raw[0x21]
    out["gender"] = (raw[0x22] >> 2) & 3
    out["form"] = raw[0x24]
    out["evs"] = {
        "hp": raw[0x26], "atk": raw[0x27], "def": raw[0x28],
        "spe": raw[0x29], "spa": raw[0x2A], "spd": raw[0x2B],
    }
    out["moves"] = [u16(raw, 0x54 + i * 2) for i in range(4)]
    out["move_pp"] = [raw[0x5C + i] for i in range(4)]
    out["nickname"] = read_utf16(raw, 0x60, 13)
    iv32 = u32(raw, 0x94)
    out["ivs"] = {
        "hp": iv_field(iv32, 0), "atk": iv_field(iv32, 5),
        "def": iv_field(iv32, 10), "spe": iv_field(iv32, 15),
        "spa": iv_field(iv32, 20), "spd": iv_field(iv32, 25),
    }
    out["is_egg"] = bool((iv32 >> 30) & 1)
    out["language"] = raw[0xF2]
    out["original_trainer"] = read_utf16(raw, 0x110, 13)
    out["ball_id"] = raw[0x137]
    out["met_level"] = raw[0x13D] & 0x7F
    out["level"] = raw[0x168] if len(raw) > 0x168 and raw[0x168] else out["met_level"]
    out["shiny"] = is_shiny(out["pid"], out["tid"], out["sid"])
    return out
