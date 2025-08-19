from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from mgz.model import parse_match


def load_match(replay_path: str | Path):
    with open(replay_path, 'rb') as fh:
        return parse_match(fh)


def payload_unit_name(payload: Dict[str, Any]) -> Optional[str]:
    unit_obj = payload.get('unit') or {}
    name = (
        getattr(unit_obj, 'name', None)
        or getattr(unit_obj, 'unit_name', None)
        or (unit_obj.get('name') if isinstance(unit_obj, dict) else None)
        or payload.get('unit_name')
        or payload.get('object_name')
        or payload.get('item')
    )
    return name


def _payload_strings(obj, depth=0, max_depth=2):
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _payload_strings(v, depth + 1, max_depth)
    else:
        name = getattr(obj, 'name', None) or getattr(obj, 'unit_name', None)
        if isinstance(name, str):
            yield name
        if isinstance(obj, str):
            yield obj


def payload_matches(payload: Dict[str, Any], pattern) -> bool:
    name = payload_unit_name(payload)
    if name and pattern.search(str(name)):
        return True
    for s in _payload_strings(payload):
        try:
            if pattern.search(str(s)):
                return True
        except Exception:
            continue
    return False


def payload_count(payload: Dict[str, Any]) -> int:
    for k in ('count', 'amount', 'quantity', 'num', 'n'):
        v = payload.get(k)
        try:
            iv = int(v)
            if iv > 0:
                return iv
        except Exception:
            pass
    return 1

