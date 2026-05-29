"""Export Pokémon sets as Showdown / PokePaste text.

Format matches pokemon-showdown-client ``Teams.exportSet`` (classic / pokepast.es):
https://github.com/smogon/pokemon-showdown-client/blob/master/play.pokemonshowdown.com/src/battle-teams.ts
https://pokepast.es/syntax.html
"""
from __future__ import annotations

STAT_LABELS = {
    "hp": "HP",
    "atk": "Atk",
    "def": "Def",
    "spa": "SpA",
    "spd": "SpD",
    "spe": "Spe",
}
NEUTRAL_NATURES = frozenset({"Hardy", "Docile", "Serious", "Bashful", "Quirky"})


def _gender_suffix(gender: int, generation: str) -> str:
    major = str(generation).split(".")[0]
    if gender == 1:
        return " (F)"
    if gender == 0 and major not in ("1", "2", "3"):
        return " (M)"
    return ""


def _format_move(move: str) -> str:
    if move.startswith("Hidden Power ") and "[" not in move:
        hp_type = move[13:].strip()
        if hp_type:
            return f"Hidden Power [{hp_type}]"
    return move


def _placeholder_ability(name: str) -> bool:
    return not name or name == "No Ability" or name.startswith("Ability ")


def _placeholder_item(name: str) -> bool:
    return not name or name == "None" or name.startswith("Item #")


def _stat_line(prefix: str, stats: dict, keys: tuple[str, ...], skip_val: int) -> str | None:
    parts: list[str] = []
    for key in keys:
        val = stats.get(key)
        if val is None or val == skip_val:
            continue
        parts.append(f"{val} {STAT_LABELS[key]}")
    if not parts:
        return None
    return f"{prefix}: " + " / ".join(parts)


def export_showdown_set(p: dict) -> str:
    """Build one PokePaste-style set block from a viewer detail dict."""
    lines: list[str] = []
    species = p.get("species_name") or "Unknown"
    form = (p.get("form_name") or "").strip()
    if form:
        species = f"{species}-{form}"
    nickname = (p.get("nickname") or "").strip()

    if nickname and nickname.lower() != species.lower():
        head = f"{nickname} ({species})"
    else:
        head = species
    head += _gender_suffix(int(p.get("gender", 2)), str(p.get("generation", "9")))

    item = p.get("held_item") or ""
    if not _placeholder_item(item):
        head += f" @ {item}"
    lines.append(head)

    ability = p.get("ability") or ""
    if not _placeholder_ability(ability):
        lines.append(f"Ability: {ability}")

    ev_line = _stat_line("EVs", p.get("evs") or {}, STAT_LABELS.keys(), 0)
    if ev_line:
        lines.append(ev_line)

    nature = (p.get("nature") or "").strip()
    if nature and nature not in NEUTRAL_NATURES:
        lines.append(f"{nature} Nature")

    iv_line = _stat_line("IVs", p.get("ivs") or {}, STAT_LABELS.keys(), 31)
    if iv_line:
        lines.append(iv_line)

    level = int(p.get("level") or 100)
    if level != 100:
        lines.append(f"Level: {level}")

    if p.get("shiny"):
        lines.append("Shiny: Yes")

    for move in p.get("moves") or []:
        if move and str(move).strip():
            lines.append(f"- {_format_move(str(move).strip())}")

    return "\n".join(lines) + "\n"
