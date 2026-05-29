"""Main parse_pokemon dispatch."""
from __future__ import annotations
import base64
from .common import layout, default_out
from .gen1 import parse_gen1
from .gen2 import parse_gen2
from .gen3 import parse_gen3, parse_gen3xd, parse_gen3col
from .gen4 import parse_gen4
from .gen5 import parse_gen5
from .modern import parse_modern
from .gen8 import parse_gen8, parse_gen9
from .gen8a import parse_gen8a

_DISPATCH = {
    "gen1": parse_gen1,
    "gen2": parse_gen2,
    "gen3": parse_gen3,
    "gen3xd": parse_gen3xd,
    "gen3col": parse_gen3col,
    "gen4": parse_gen4,
    "gen5": parse_gen5,
    "modern": parse_modern,
    "gen8": parse_gen8,
    "gen8a": parse_gen8a,
    "gen9": parse_gen9,
}


def parse_pokemon(base64_data: str, generation: str) -> dict:
    raw = base64.b64decode(base64_data)
    lyt = layout(raw, generation)
    parser = _DISPATCH.get(lyt)
    if parser is None:
        return default_out("unknown")
    return parser(raw)
