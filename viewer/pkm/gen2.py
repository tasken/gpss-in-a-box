"""Gen 2 PKM parser."""
from __future__ import annotations
from .common import u16_be, ivs_from_dv16_be, is_shiny_gen12, default_out


def parse_gen2(raw: bytes) -> dict:
    out = default_out("gen2")
    out["species_id"] = raw[0]
    if out["species_id"] > 251:
        out["species_id"] = 0
    out["held_item_id"] = raw[0x01]
    out["tid"] = u16_be(raw, 0x06)
    out["moves"] = [raw[0x02], raw[0x03], raw[0x04], raw[0x05]]
    out["move_pp"] = [raw[0x17] & 0x3F, raw[0x18] & 0x3F, raw[0x19] & 0x3F, raw[0x1A] & 0x3F]
    dv16 = u16_be(raw, 0x15)
    out["ivs"] = ivs_from_dv16_be(dv16)
    out["evs"] = {
        "hp": u16_be(raw, 0x0B),
        "atk": u16_be(raw, 0x0D),
        "def": u16_be(raw, 0x0F),
        "spe": u16_be(raw, 0x11),
        "spa": u16_be(raw, 0x13),
        "spd": u16_be(raw, 0x13),
    }
    out["level"] = raw[0x1F]
    if len(raw) > 0x1E:
        caught = u16_be(raw, 0x1D)
        out["met_level"] = (caught >> 8) & 0x3F
    out["shiny"] = is_shiny_gen12(dv16)
    return out
