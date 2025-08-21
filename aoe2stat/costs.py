from __future__ import annotations

from typing import Dict, Tuple
import re

ResourceCost = Tuple[int, int, int, int]  # food, wood, gold, stone


def _norm(name: str) -> str:
    return name.strip().lower()


# Minimal but practical cost tables for common units/buildings/techs.
# Values are from standard RM; civ/tech discounts not applied.
_UNIT_COSTS: Dict[str, ResourceCost] = {
    # Eco / infantry / archers
    'villager': (50, 0, 0, 0),
    'militia': (60, 0, 20, 0),
    'man-at-arms': (60, 0, 20, 0),  # trained as militia pre-upgrade; kept for matching
    'spearman': (35, 25, 0, 0),
    'pikeman': (35, 25, 0, 0),
    'halberdier': (35, 25, 0, 0),
    'archer': (0, 25, 45, 0),
    'crossbowman': (0, 25, 45, 0),
    'skirmisher': (25, 35, 0, 0),
    'elite skirmisher': (25, 35, 0, 0),
    'hand cannoneer': (45, 0, 50, 0),
    'cavalry archer': (0, 40, 60, 0),
    # Cavalry / camels / eagles
    'scout': (80, 0, 0, 0),
    'scout cavalry': (80, 0, 0, 0),
    'light cavalry': (80, 0, 0, 0),
    'hussar': (80, 0, 0, 0),
    'knight': (60, 0, 75, 0),
    'cavalier': (60, 0, 75, 0),
    'paladin': (60, 0, 75, 0),
    'camel': (55, 0, 60, 0),
    'camel rider': (55, 0, 60, 0),
    'eagle': (20, 0, 50, 0),
    'eagle scout': (20, 0, 50, 0),
    'eagle warrior': (20, 0, 50, 0),
    # Siege (common)
    'battering ram': (0, 160, 75, 0),
    'mangonel': (0, 160, 135, 0),
    'onager': (0, 160, 135, 0),
    'scorpion': (0, 75, 75, 0),
    'siege ram': (0, 0, 0, 0),  # upgrade, not a unit cost
}

_BUILDING_COSTS: Dict[str, ResourceCost] = {
    'house': (0, 25, 0, 0),
    'lumber camp': (0, 100, 0, 0),
    'mill': (0, 100, 0, 0),
    'mining camp': (0, 100, 0, 0),
    'barracks': (0, 175, 0, 0),
    'archery range': (0, 175, 0, 0),
    'stable': (0, 175, 0, 0),
    'blacksmith': (0, 150, 0, 0),
    'market': (0, 175, 0, 0),
    'monastery': (0, 175, 0, 0),
    'siege workshop': (0, 200, 0, 0),
    'university': (0, 200, 0, 0),
    'town center': (0, 275, 0, 100),
    'watch tower': (0, 25, 0, 125),
    'guard tower': (0, 25, 0, 125),
    'keep': (0, 25, 0, 125),
    'castle': (0, 0, 0, 650),
    # walls / gates omitted
}

_TECH_COSTS: Dict[str, ResourceCost] = {
    # Economy
    'loom': (0, 0, 50, 0),
    'double-bit axe': (0, 100, 0, 0),
    'bow saw': (100, 150, 0, 0),
    'two-man saw': (300, 300, 0, 0),
    'horse collar': (75, 75, 0, 0),
    'heavy plow': (125, 125, 0, 0),
    'crop rotation': (250, 250, 0, 0),
    'wheelbarrow': (175, 50, 0, 0),
    'hand cart': (300, 200, 0, 0),
    'gold mining': (100, 75, 0, 0),
    'gold shaft mining': (200, 150, 0, 0),
    'stone mining': (100, 75, 0, 0),
    'stone shaft mining': (200, 150, 0, 0),
    # Vision / town
    'town watch': (75, 0, 0, 0),
    'town patrol': (300, 0, 100, 0),
    # Blacksmith (archery)
    'fletching': (50, 0, 100, 0),
    'bodkin arrow': (200, 0, 100, 0),
    'bracer': (300, 0, 200, 0),
    # Blacksmith (melee)
    'forging': (150, 0, 0, 0),
    'iron casting': (220, 0, 120, 0),
    'blast furnace': (275, 0, 225, 0),
    # Armor (inf/cav/arch)
    'scale mail armor': (100, 0, 0, 0),
    'chain mail armor': (200, 0, 0, 0),
    'plate mail armor': (300, 0, 0, 0),
    'scale barding armor': (150, 0, 0, 0),
    'chain barding armor': (250, 0, 0, 0),
    'plate barding armor': (350, 0, 0, 0),
    'leather archer armor': (100, 0, 0, 0),
    'chain archer armor': (150, 0, 0, 0),
    'ring archer armor': (250, 0, 0, 0),
}


def _lookup(name: str, table: Dict[str, ResourceCost]) -> ResourceCost | None:
    n = _norm(name)
    if n in table:
        return table[n]
    # loose match by substring
    for k, v in table.items():
        if n == k:
            return v
        if k in n or n in k:
            return v
    # regex match start word
    for k, v in table.items():
        if re.search(rf"\b{re.escape(k)}\b", n):
            return v
    return None


def unit_cost(name: str) -> ResourceCost | None:
    return _lookup(name, _UNIT_COSTS)


def building_cost(name: str) -> ResourceCost | None:
    return _lookup(name, _BUILDING_COSTS)


def tech_cost(name: str) -> ResourceCost | None:
    return _lookup(name, _TECH_COSTS)

