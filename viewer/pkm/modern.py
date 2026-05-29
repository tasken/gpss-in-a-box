"""Gen 6/7 PKM parser (PK6/PK7, 260-byte format)."""
from __future__ import annotations
from .common import u16, u32, iv_field, is_shiny, default_out
from .strings import read_utf16


def parse_modern(raw: bytes) -> dict:
    """Parse PK6 (X/Y/ORAS) or PK7 (Sun/Moon/USUM) — 260 bytes."""
    out = default_out("modern")
    out["species_id"] = u16(raw, 0x08)
    out["held_item_id"] = u16(raw, 0x0A)
    out["tid"] = u16(raw, 0x0C)
    out["sid"] = u16(raw, 0x0E)
    out["pid"] = u32(raw, 0x18)
    out["ability_id"] = raw[0x14]
    out["nature_id"] = raw[0x1C]
    fd = raw[0x1D]
    out["form"] = fd >> 3
    out["gender"] = (fd >> 1) & 3
    out["language"] = raw[0xE3] if len(raw) > 0xE3 else 0
    iv32 = u32(raw, 0x74)
    out["moves"] = [u16(raw, 0x5A + i * 2) for i in range(4)]
    out["move_pp"] = [raw[0x62 + i] for i in range(4)]
    out["nickname"] = read_utf16(raw, 0x40, 13)
    out["original_trainer"] = read_utf16(raw, 0xB0, 13)
    out["met_level"] = raw[0xDD] & 0x7F
    out["ball_id"] = raw[0xDC]
    out["is_egg"] = bool((iv32 >> 30) & 1)
    out["level"] = raw[0xEC] if len(raw) > 0xEC and raw[0xEC] else out["met_level"]
    out["ivs"] = {
        "hp": iv_field(iv32, 0),
        "atk": iv_field(iv32, 5),
        "def": iv_field(iv32, 10),
        "spe": iv_field(iv32, 15),
        "spa": iv_field(iv32, 20),
        "spd": iv_field(iv32, 25),
    }
    out["evs"] = {
        "hp": raw[0x1E],
        "atk": raw[0x1F],
        "def": raw[0x20],
        "spe": raw[0x21],
        "spa": raw[0x22],
        "spd": raw[0x23],
    }
    out["shiny"] = is_shiny(out["pid"], out["tid"], out["sid"])
    return out
