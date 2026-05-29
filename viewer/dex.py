"""Load Pokemon Showdown dex data + pokesprite assets + lookup tables."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Type colors
# ---------------------------------------------------------------------------

TYPE_COLORS: dict[str, str] = {
    "Normal": "#A8A77A",
    "Fire": "#EE8130",
    "Water": "#6390F0",
    "Electric": "#F7D02C",
    "Grass": "#7AC74C",
    "Ice": "#96D9D6",
    "Fighting": "#C22E28",
    "Poison": "#A33EA1",
    "Ground": "#E2BF65",
    "Flying": "#A98FF3",
    "Psychic": "#F95587",
    "Bug": "#A6B91A",
    "Rock": "#B6A136",
    "Ghost": "#735797",
    "Dragon": "#6F35FC",
    "Dark": "#705746",
    "Steel": "#B7B7CE",
    "Fairy": "#D685AD",
}

# ---------------------------------------------------------------------------
# Natures
# ---------------------------------------------------------------------------

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
]

_STAT_KEYS = ("atk", "def", "spe", "spa", "spd")

_NATURE_EFFECTS: list[tuple[str | None, str | None]] = []
for _i in range(25):
    _plus_idx = _i // 5
    _minus_idx = _i % 5
    if _plus_idx == _minus_idx:
        _NATURE_EFFECTS.append((None, None))
    else:
        _NATURE_EFFECTS.append((_STAT_KEYS[_plus_idx], _STAT_KEYS[_minus_idx]))


def nature_name(nature_id: int) -> str:
    if 0 <= nature_id < len(NATURES):
        return NATURES[nature_id]
    return str(nature_id)


def nature_stats(nature_id: int) -> tuple[str | None, str | None]:
    """Return (boosted_stat, hindered_stat) or (None, None) for neutral."""
    if 0 <= nature_id < len(_NATURE_EFFECTS):
        return _NATURE_EFFECTS[nature_id]
    return (None, None)

# ---------------------------------------------------------------------------
# Balls
# ---------------------------------------------------------------------------

BALL_NAMES: dict[int, str] = {
    1: "Poké Ball", 2: "Great Ball", 3: "Ultra Ball", 4: "Master Ball",
    5: "Safari Ball", 6: "Net Ball", 7: "Dive Ball", 8: "Nest Ball",
    9: "Repeat Ball", 10: "Timer Ball", 11: "Luxury Ball", 12: "Premier Ball",
    13: "Dusk Ball", 14: "Heal Ball", 15: "Quick Ball", 16: "Cherish Ball",
    17: "Fast Ball", 18: "Level Ball", 19: "Lure Ball", 20: "Heavy Ball",
    21: "Love Ball", 22: "Friend Ball", 23: "Moon Ball", 24: "Sport Ball",
    25: "Dream Ball", 26: "Beast Ball",
}

BALL_SLUGS: dict[int, str] = {
    1: "poke-ball", 2: "great-ball", 3: "ultra-ball", 4: "master-ball",
    5: "safari-ball", 6: "net-ball", 7: "dive-ball", 8: "nest-ball",
    9: "repeat-ball", 10: "timer-ball", 11: "luxury-ball", 12: "premier-ball",
    13: "dusk-ball", 14: "heal-ball", 15: "quick-ball", 16: "cherish-ball",
    17: "fast-ball", 18: "level-ball", 19: "lure-ball", 20: "heavy-ball",
    21: "love-ball", 22: "friend-ball", 23: "moon-ball", 24: "sport-ball",
    25: "dream-ball", 26: "beast-ball",
}


def ball_name(ball_id: int) -> str:
    return BALL_NAMES.get(ball_id, f"Ball #{ball_id}" if ball_id else "None")


def ball_slug(ball_id: int) -> str:
    return BALL_SLUGS.get(ball_id, "poke-ball")

# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------

LANGUAGE_NAMES: dict[int, str] = {
    1: "JPN", 2: "ENG", 3: "FRE", 4: "GER",
    5: "ITA", 6: "SPA", 7: "KOR", 8: "CHS", 9: "CHT",
}


def language_name(lang_id: int) -> str:
    return LANGUAGE_NAMES.get(lang_id, f"Lang {lang_id}" if lang_id else "—")

# ---------------------------------------------------------------------------
# Showdown data fetching
# ---------------------------------------------------------------------------

def _data_dir() -> Path:
    db = os.environ.get("GPSS_DB")
    if db:
        return Path(db).parent
    return Path(__file__).resolve().parent.parent / ".local"

CACHE_DIR = _data_dir() / "cache"


def _sprites_dir() -> Path:
    env = os.environ.get("SPRITES_DIR")
    if env:
        return Path(env)
    docker_path = Path("/app/sprites")
    if docker_path.is_dir():
        return docker_path
    return _data_dir() / "sprites"


SPRITES_DIR = _sprites_dir()
POKEDEX_URL = "https://play.pokemonshowdown.com/data/pokedex.json"
MOVES_URL = "https://play.pokemonshowdown.com/data/moves.json"
ABILITIES_URL = "https://play.pokemonshowdown.com/data/abilities.js"
ITEMS_URL = "https://play.pokemonshowdown.com/data/items.js"
_JS_EXPORT_RE = re.compile(r"^exports\.\w+\s*=\s*")
_JS_KEY_RE = re.compile(r"(?<=[{,])(\w+):")

BALL_SPRITE_SLUGS: dict[int, str] = {
    1: "poke", 2: "great", 3: "ultra", 4: "master",
    5: "safari", 6: "net", 7: "dive", 8: "nest",
    9: "repeat", 10: "timer", 11: "luxury", 12: "premier",
    13: "dusk", 14: "heal", 15: "quick", 16: "cherish",
    17: "fast", 18: "level", 19: "lure", 20: "heavy",
    21: "love", 22: "friend", 23: "moon", 24: "sport",
    25: "dream", 26: "beast",
}


def _parse_js_object(text: str) -> dict:
    body = _JS_EXPORT_RE.sub("", text).rstrip().rstrip(";")
    body = _JS_KEY_RE.sub(r'"\1":', body)
    return json.loads(body)


def _fetch(url: str, path: Path) -> dict | None:
    if path.exists():
        raw = path.read_text()
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        return _parse_js_object(raw)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; gpss-viewer/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            path.write_bytes(raw)
        text = raw.decode("utf-8")
        if text.lstrip().startswith("{"):
            return json.loads(text)
        return _parse_js_object(text)
    except Exception:
        return None


class DexData:
    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        pokedex = _fetch(POKEDEX_URL, CACHE_DIR / "pokedex.json") or {}
        moves = _fetch(MOVES_URL, CACHE_DIR / "moves.json") or {}
        abilities = _fetch(ABILITIES_URL, CACHE_DIR / "abilities.json") or {}
        items = _fetch(ITEMS_URL, CACHE_DIR / "items.json") or {}

        self.num_to_slug: dict[int, str] = {}
        self.num_to_name: dict[int, str] = {}
        self.num_to_types: dict[int, list[str]] = {}
        self.num_to_base_stats: dict[int, dict[str, int]] = {}
        self._form_data: dict[str, dict] = {}

        for slug, entry in pokedex.items():
            num = entry.get("num")
            if num is None or num <= 0:
                continue
            if num not in self.num_to_slug:
                self.num_to_slug[num] = slug
                self.num_to_name[num] = entry.get("name", slug)
                self.num_to_types[num] = entry.get("types", [])
                self.num_to_base_stats[num] = entry.get("baseStats", {})
            forme = entry.get("forme")
            if forme:
                self._form_data[f"{num}:{forme.lower()}"] = {
                    "name": forme,
                    "types": entry.get("types", []),
                    "base_stats": entry.get("baseStats", {}),
                }

        self.move_names: dict[int, str] = {
            e["num"]: e.get("name", k) for k, e in moves.items() if "num" in e
        }
        self.ability_names: dict[int, str] = {
            e["num"]: e.get("name", k) for k, e in abilities.items() if "num" in e
        }
        self.item_names: dict[int, str] = {
            e["num"]: e.get("name", k) for k, e in items.items() if "num" in e
        }
        self.item_slugs: dict[int, str] = {
            e["num"]: re.sub(r"[^a-z0-9]+", "-", e.get("name", k).lower()).strip("-")
            for k, e in items.items() if "num" in e
        }

        self.num_to_sprite_slug: dict[int, str] = {}
        ps_pokemon = SPRITES_DIR / "data" / "pokemon.json"
        if ps_pokemon.is_file():
            for idx_str, entry in json.loads(ps_pokemon.read_text()).items():
                try:
                    num = int(idx_str)
                except ValueError:
                    continue
                slug = entry.get("slug", {}).get("eng", "")
                if num > 0 and slug:
                    self.num_to_sprite_slug[num] = slug

        self.item_sprite_paths: dict[int, str] = {}
        ps_items = SPRITES_DIR / "data" / "item-map.json"
        if ps_items.is_file():
            for key, path in json.loads(ps_items.read_text()).items():
                if key.startswith("item_"):
                    try:
                        item_id = int(key[5:])
                    except ValueError:
                        continue
                    self.item_sprite_paths[item_id] = path
                    if item_id not in self.item_names:
                        slug = path.rsplit("/", 1)[-1]
                        name = slug.replace("-", " ").title()
                        for abbr in ("Hp", "Pp", "Tm", "Hm", "Xl", "Xs"):
                            name = name.replace(abbr, abbr.upper())
                        self.item_names[item_id] = name

    def species_name(self, species_id: int) -> str:
        return self.num_to_name.get(species_id, f"#{species_id}")

    def species_slug(self, species_id: int) -> str:
        return self.num_to_slug.get(species_id, "missingno")

    def species_types(self, species_id: int) -> list[str]:
        return self.num_to_types.get(species_id, [])

    def species_base_stats(self, species_id: int) -> dict[str, int]:
        return self.num_to_base_stats.get(species_id, {})

    def form_name(self, species_id: int, form_id: int) -> str:
        if not form_id:
            return ""
        forms = [v["name"] for k, v in self._form_data.items() if k.startswith(f"{species_id}:")]
        if form_id <= len(forms):
            return forms[form_id - 1]
        return f"Form {form_id}"

    def move_name(self, move_id: int) -> str:
        return self.move_names.get(move_id, f"Move {move_id}")

    def item_name(self, item_id: int) -> str:
        if item_id == 0:
            return "None"
        return self.item_names.get(item_id, f"Item #{item_id}")

    def item_slug(self, item_id: int) -> str:
        return self.item_slugs.get(item_id, "")

    def ability_name(self, ability_id: int) -> str:
        return self.ability_names.get(ability_id, f"Ability {ability_id}")

    def sprite_slug(self, species_id: int) -> str:
        return self.num_to_sprite_slug.get(species_id, "unknown")

    def item_sprite(self, item_id: int) -> str:
        path = self.item_sprite_paths.get(item_id)
        return f"/sprites/items/{path}.png" if path else ""

    def ball_sprite(self, ball_id: int) -> str:
        slug = BALL_SPRITE_SLUGS.get(ball_id)
        return f"/sprites/items/ball/{slug}.png" if slug else ""

    nature_name = staticmethod(nature_name)
    nature_stats = staticmethod(nature_stats)
    ball_name = staticmethod(ball_name)
    ball_slug = staticmethod(ball_slug)
    language_name = staticmethod(language_name)
