"""Gen 3 PKM parser (GBA, XD, Colosseum)."""
from __future__ import annotations
from .common import u16, u16_be, u32, u32_be, iv_field, is_shiny, default_out
from .strings import read_utf16_be

# Gen 3 internal species index to National Dex (from PKHeX SpeciesConverter)
_FIRST_UNALIGNED_INTERNAL3 = 277

_TABLE3_INTERNAL_TO_NATIONAL: tuple[int, ...] = (
    -25, -25, -25, -25, -25, -25, -25, -25, -25, -25, -25, -25, -25, -25, -25,
    -25, -25, -25, -25, -25, -25, -25, -25, -25, -25, -25, -11, -11, -11, -28,
    -28, -21, -21, 19, -31, -31, -28, -28, 7, 7, -15, -15, 35, 25, 25, -21, 3,
    -20, 16, 16, 45, 15, 15, 21, 21, -12, -12, -4, -4, -4, -39, -39, -28, -28,
    -17, -17, 22, 22, 22, -13, -13, 15, 15, -11, -11, -52, -26, -26, -42, -42,
    -52, -49, -49, -25, -25, 0, -6, -6, -48, -77, -77, -77, -51, -51, -12, -77,
    -77, -77, -7, -7, -7, -17, -24, -24, -43, -45, -12, -78, -78, -78, -34, -73,
    -73, -43, -43, -43, -43, -112, -112, -112, -24, -24, -24, -24, -24, -24,
    -24, -24, -24, -22, -22, -22, -27, -27, -24, -24, -53,
)


def national_from_internal3(internal: int) -> int:
    if internal < _FIRST_UNALIGNED_INTERNAL3:
        return internal
    shift = internal - _FIRST_UNALIGNED_INTERNAL3
    if shift >= len(_TABLE3_INTERNAL_TO_NATIONAL):
        return 0
    return internal + _TABLE3_INTERNAL_TO_NATIONAL[shift]


def parse_gen3(raw: bytes) -> dict:
    out = default_out("gen3")
    out["pid"] = u32(raw, 0x00)
    out["tid"] = u16(raw, 0x04)
    out["sid"] = u16(raw, 0x06)
    out["language"] = raw[0x12]
    internal = u16(raw, 0x20)
    out["species_id"] = national_from_internal3(internal)
    out["held_item_id"] = u16(raw, 0x22)
    out["moves"] = [u16(raw, 0x2C + i * 2) for i in range(4)]
    out["move_pp"] = [raw[0x34 + i] for i in range(4)]
    out["met_level"] = raw[0x45] & 0x7F
    out["ball_id"] = (raw[0x46] >> 3) & 0xF if len(raw) > 0x47 else 0
    iv32 = u32(raw, 0x48)
    out["is_egg"] = bool((iv32 >> 30) & 1)
    out["level"] = raw[0x54] if len(raw) > 0x54 and raw[0x54] else out["met_level"]
    out["ivs"] = {
        "hp": iv_field(iv32, 0),
        "atk": iv_field(iv32, 5),
        "def": iv_field(iv32, 10),
        "spe": iv_field(iv32, 15),
        "spa": iv_field(iv32, 20),
        "spd": iv_field(iv32, 25),
    }
    out["evs"] = {
        "hp": raw[0x38],
        "atk": raw[0x39],
        "def": raw[0x3A],
        "spe": raw[0x3B],
        "spa": raw[0x3C],
        "spd": raw[0x3D],
    }
    out["nature_id"] = out["pid"] % 25
    out["shiny"] = is_shiny(out["pid"], out["tid"], out["sid"])
    return out


def parse_gen3xd(raw: bytes) -> dict:
    out = default_out("gen3xd")
    internal = u16_be(raw, 0x00)
    out["species_id"] = national_from_internal3(internal)
    out["held_item_id"] = u16_be(raw, 0x02)
    out["met_level"] = raw[0x0E]
    out["ball_id"] = raw[0x0F]
    out["tid"] = u16_be(raw, 0x26)
    out["sid"] = u16_be(raw, 0x24)
    out["pid"] = u32_be(raw, 0x28)
    out["language"] = raw[0x37] if len(raw) > 0x37 else 0
    out["level"] = raw[0x11]
    flags = raw[0x1D]
    out["is_egg"] = bool(flags & 0x80)
    out["ability_id"] = 1 if flags & 0x40 else 0
    out["nature_id"] = out["pid"] % 25
    out["moves"] = [u16_be(raw, 0x80 + i * 4) for i in range(4)]
    out["move_pp"] = [raw[0x82 + i * 4] for i in range(4)]
    out["nickname"] = read_utf16_be(raw, 0x64, 11)
    out["original_trainer"] = read_utf16_be(raw, 0x38, 11)
    out["ivs"] = {
        "hp": raw[0xA8] & 0x1F,
        "atk": raw[0xA9] & 0x1F,
        "def": raw[0xAA] & 0x1F,
        "spa": raw[0xAB] & 0x1F,
        "spd": raw[0xAC] & 0x1F,
        "spe": raw[0xAD] & 0x1F,
    }
    out["evs"] = {
        "hp": min(255, u16_be(raw, 0x9C)),
        "atk": min(255, u16_be(raw, 0x9E)),
        "def": min(255, u16_be(raw, 0xA0)),
        "spa": min(255, u16_be(raw, 0xA2)),
        "spd": min(255, u16_be(raw, 0xA4)),
        "spe": min(255, u16_be(raw, 0xA6)),
    }
    out["shiny"] = is_shiny(out["pid"], out["tid"], out["sid"])
    return out


def parse_gen3col(raw: bytes) -> dict:
    out = default_out("gen3col")
    internal = u16_be(raw, 0x00)
    out["species_id"] = national_from_internal3(internal)
    out["pid"] = u32_be(raw, 0x04)
    out["language"] = raw[0x0B] if len(raw) > 0x0B else 0
    out["met_level"] = raw[0x0E]
    out["ball_id"] = raw[0x0F]
    out["tid"] = u16_be(raw, 0x16)
    out["sid"] = u16_be(raw, 0x14)
    out["level"] = raw[0x60]
    out["is_egg"] = raw[0xCB] == 1 if len(raw) > 0xCB else False
    out["ability_id"] = 1 if len(raw) > 0xCC and raw[0xCC] == 1 else 0
    out["nature_id"] = out["pid"] % 25
    out["moves"] = [u16_be(raw, 0x78 + i * 4) for i in range(4)]
    out["move_pp"] = [raw[0x7A + i * 4] for i in range(4)]
    out["held_item_id"] = u16_be(raw, 0x88)
    out["nickname"] = read_utf16_be(raw, 0x44, 11)
    out["original_trainer"] = read_utf16_be(raw, 0x18, 11)
    out["ivs"] = {
        "hp": min(31, u16_be(raw, 0xA4)),
        "atk": min(31, u16_be(raw, 0xA6)),
        "def": min(31, u16_be(raw, 0xA8)),
        "spa": min(31, u16_be(raw, 0xAA)),
        "spd": min(31, u16_be(raw, 0xAC)),
        "spe": min(31, u16_be(raw, 0xAE)),
    }
    out["evs"] = {
        "hp": min(255, u16_be(raw, 0x98)),
        "atk": min(255, u16_be(raw, 0x9A)),
        "def": min(255, u16_be(raw, 0x9C)),
        "spa": min(255, u16_be(raw, 0x9E)),
        "spd": min(255, u16_be(raw, 0xA0)),
        "spe": min(255, u16_be(raw, 0xA2)),
    }
    out["shiny"] = is_shiny(out["pid"], out["tid"], out["sid"])
    return out
