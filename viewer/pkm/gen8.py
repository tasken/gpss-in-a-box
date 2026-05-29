"""Gen 8 (PK8/PB8) and Gen 9 (PK9) parser — 344-byte party format."""
from __future__ import annotations
from .common import u16, u32, iv_field, is_shiny, default_out
from .strings import read_utf16


def _parse_g8_common(raw: bytes, out: dict) -> None:
    """Shared parsing for all 344-byte Gen 8+ formats (PK8/PB8/PK9)."""
    out["species_id"] = u16(raw, 0x08)
    out["held_item_id"] = u16(raw, 0x0A)
    out["tid"] = u16(raw, 0x0C)
    out["sid"] = u16(raw, 0x0E)
    out["ability_id"] = u16(raw, 0x14)
    out["pid"] = u32(raw, 0x1C)
    out["nature_id"] = raw[0x20]
    out["stat_nature_id"] = raw[0x21]
    out["form"] = raw[0x24]
    out["evs"] = {
        "hp": raw[0x26], "atk": raw[0x27], "def": raw[0x28],
        "spe": raw[0x29], "spa": raw[0x2A], "spd": raw[0x2B],
    }
    out["nickname"] = read_utf16(raw, 0x58, 13)
    out["moves"] = [u16(raw, 0x72 + i * 2) for i in range(4)]
    out["move_pp"] = [raw[0x7A + i] for i in range(4)]
    iv32 = u32(raw, 0x8C)
    out["ivs"] = {
        "hp": iv_field(iv32, 0), "atk": iv_field(iv32, 5),
        "def": iv_field(iv32, 10), "spe": iv_field(iv32, 15),
        "spa": iv_field(iv32, 20), "spd": iv_field(iv32, 25),
    }
    out["is_egg"] = bool((iv32 >> 30) & 1)
    out["original_trainer"] = read_utf16(raw, 0xF8, 13)
    out["ball_id"] = raw[0x124]
    out["met_level"] = raw[0x125] & 0x7F
    out["level"] = raw[0x148] if len(raw) > 0x148 and raw[0x148] else out["met_level"]
    out["shiny"] = is_shiny(out["pid"], out["tid"], out["sid"])


def parse_gen8(raw: bytes) -> dict:
    """Parse PK8 (Sword/Shield) or PB8 (BDSP) — 344 bytes."""
    out = default_out("gen8")
    _parse_g8_common(raw, out)
    out["gender"] = (raw[0x22] >> 2) & 3
    out["language"] = raw[0xE2]
    return out


def parse_gen9(raw: bytes) -> dict:
    """Parse PK9 (Scarlet/Violet) — 344 bytes."""
    out = default_out("gen9")
    _parse_g8_common(raw, out)
    out["gender"] = (raw[0x22] >> 1) & 3
    out["language"] = raw[0xD5]
    return out
