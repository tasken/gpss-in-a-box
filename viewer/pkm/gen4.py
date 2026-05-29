"""Gen 4 PKM parser."""
from __future__ import annotations
from .common import u16, u32, iv_field, is_shiny, default_out
from .strings import read_gen4_str


def parse_gen4(raw: bytes) -> dict:
    out = default_out("gen4")
    out["species_id"] = u16(raw, 0x08)
    out["held_item_id"] = u16(raw, 0x0A)
    out["tid"] = u16(raw, 0x0C)
    out["sid"] = u16(raw, 0x0E)
    out["pid"] = u32(raw, 0x00)
    out["ability_id"] = raw[0x15]
    out["language"] = raw[0x17]
    fg = raw[0x40]
    out["form"] = fg >> 3
    out["gender"] = (fg >> 1) & 3
    iv32 = u32(raw, 0x38)
    out["moves"] = [u16(raw, 0x28 + i * 2) for i in range(4)]
    out["move_pp"] = [raw[0x30 + i] for i in range(4)]
    out["nickname"] = read_gen4_str(raw, 0x48, 11)
    out["original_trainer"] = read_gen4_str(raw, 0x68, 8)
    out["met_level"] = raw[0x84] & 0x7F
    out["ball_id"] = raw[0x83]
    out["is_egg"] = bool((iv32 >> 30) & 1)
    out["level"] = raw[0x8C] if len(raw) >= 0x8D and raw[0x8C] else out["met_level"]
    out["ivs"] = {
        "hp": iv_field(iv32, 0),
        "atk": iv_field(iv32, 5),
        "def": iv_field(iv32, 10),
        "spe": iv_field(iv32, 15),
        "spa": iv_field(iv32, 20),
        "spd": iv_field(iv32, 25),
    }
    out["evs"] = {
        "hp": raw[0x18],
        "atk": raw[0x19],
        "def": raw[0x1A],
        "spe": raw[0x1B],
        "spa": raw[0x1C],
        "spd": raw[0x1D],
    }
    out["nature_id"] = out["pid"] % 25
    out["shiny"] = is_shiny(out["pid"], out["tid"], out["sid"])
    return out
