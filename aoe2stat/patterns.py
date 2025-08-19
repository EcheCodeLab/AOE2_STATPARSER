import re
from typing import Dict, Pattern


def base_unit_patterns() -> Dict[str, Pattern[str]]:
    return {
        'Villager': re.compile(r'villager|aldean', re.IGNORECASE),
        'Archer': re.compile(r'archer|arquero', re.IGNORECASE),
        'Crossbowman': re.compile(r'crossbow|ballestero', re.IGNORECASE),
        'Skirmisher': re.compile(r'skirm|guerrillero|hostigador', re.IGNORECASE),
        'Militia': re.compile(r'militia|milicia|man.?at.?arms|hombre.?de.?armas', re.IGNORECASE),
        'Long Swordsman': re.compile(r'long\s*sword|espad[oó]n|longsword', re.IGNORECASE),
        'Spearman': re.compile(r'spearman|lancero', re.IGNORECASE),
        'Pikeman': re.compile(r'pike|piquero', re.IGNORECASE),
        'Scout': re.compile(r'scout|explorador|light\s*cav', re.IGNORECASE),
        'Knight': re.compile(r'knight|caballero', re.IGNORECASE),
        'Cavalier': re.compile(r'cavalier|caballero\s*mejorado', re.IGNORECASE),
        'Paladin': re.compile(r'paladin|palad[ií]n', re.IGNORECASE),
        'Camel': re.compile(r'camel|camello', re.IGNORECASE),
        'Eagle': re.compile(r'eagle|[áa]guila', re.IGNORECASE),
        'Cavalry Archer': re.compile(r'cavalry\s*archer|arquero\s*a\s*caballo', re.IGNORECASE),
        'Hand Cannoneer': re.compile(r'hand\s*cannoneer|arcabucero|ca[ñn]onero\s*de\s*mano', re.IGNORECASE),
        'Hussar': re.compile(r'hussar|husar', re.IGNORECASE),
    }


def augment_unit_patterns(patterns: Dict[str, Pattern[str]]) -> Dict[str, Pattern[str]]:
    """Ensure useful extra units exist (Knight line, etc.). Returns the same dict after augmentation."""
    defaults = base_unit_patterns()
    for k, pat in defaults.items():
        if k not in patterns:
            patterns[k] = pat
    return patterns

