"""Shared helpers for PKM binary parsing."""
from __future__ import annotations
import struct


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u16_be(data: bytes, off: int) -> int:
    return struct.unpack_from(">H", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def u32_be(data: bytes, off: int) -> int:
    return struct.unpack_from(">I", data, off)[0]


def iv_field(iv32: int, shift: int) -> int:
    return (iv32 >> shift) & 0x1F


def is_shiny(pid: int, tid: int, sid: int) -> bool:
    xor = pid ^ ((tid & 0xFFFF) | (sid << 16))
    return (xor & 0xFFFF) < 8


def is_shiny_gen12(dv16: int) -> bool:
    """Gen 1/2: shiny when Defense, Speed, and Special IVs are all 10."""
    return (
        ((dv16 >> 8) & 0xF) == 10
        and ((dv16 >> 4) & 0xF) == 10
        and (dv16 & 0xF) == 10
    )


def ivs_from_dv16_be(dv16: int) -> dict[str, int]:
    return {
        "hp": 0,
        "atk": (dv16 >> 12) & 0xF,
        "def": (dv16 >> 8) & 0xF,
        "spe": (dv16 >> 4) & 0xF,
        "spa": dv16 & 0xF,
        "spd": dv16 & 0xF,
    }


def default_out(layout: str) -> dict:
    """Default empty parsed pokemon dict."""
    return {
        "species_id": 0,
        "form": 0,
        "gender": 0,
        "level": 0,
        "held_item_id": 0,
        "ability_id": 0,
        "nature_id": 0,
        "stat_nature_id": 0,
        "nickname": "",
        "original_trainer": "",
        "tid": 0,
        "sid": 0,
        "pid": 0,
        "shiny": False,
        "moves": [],
        "move_pp": [],
        "is_egg": False,
        "ball_id": 0,
        "met_level": 0,
        "language": 0,
        "ivs": {},
        "evs": {},
        "parse_layout": layout,
    }


def layout(data: bytes, generation: str) -> str:
    major = generation.split(".")[0]
    minor = generation.split(".")[1] if "." in generation else ""
    n = len(data)
    if major == "1":
        return "gen1"
    if major == "2":
        return "gen2"
    if major == "3":
        if minor == "2" or n == 196:
            return "gen3xd"
        if minor == "1" or n == 312:
            return "gen3col"
        return "gen3"
    if major == "4":
        return "gen4"
    if major == "5":
        return "gen5"
    if major == "6" or major == "7":
        return "modern"
    if major == "8":
        if minor == "1" or n == 376:
            return "gen8a"
        return "gen8"
    if major == "9":
        return "gen9"
    if major.isdigit() and int(major) >= 10:
        return "gen9"
    if n == 376:
        return "gen8a"
    if n == 344:
        return "gen8"
    if n >= 260:
        return "modern"
    if n >= 236:
        return "gen4"
    if n in (136, 220):
        return "gen5"
    if n == 196:
        return "gen3xd"
    if n == 312:
        return "gen3col"
    if n in (80, 100):
        return "gen3"
    if n == 44:
        return "gen1"
    if n == 48:
        return "gen2"
    return "unknown"
