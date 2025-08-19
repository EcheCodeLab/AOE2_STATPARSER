from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from .core import payload_matches, payload_count


def _is_prod_event(tname: str) -> bool:
    return ('TRAIN' in tname) or ('CREATE' in tname) or ('QUEUE' in tname) or (tname == 'ORDER')


def villager_counts(match, villager_pattern) -> Dict[int, int]:
    counts: Dict[int, int] = {p.number: 0 for p in match.players}
    for act in match.actions:
        tname = getattr(getattr(act, 'type', None), 'name', '')
        if not _is_prod_event(tname):
            continue
        if not payload_matches(getattr(act, 'payload', {}) or {}, villager_pattern):
            continue
        pid = getattr(getattr(act, 'player', None), 'number', None)
        if pid is not None:
            counts[pid] += payload_count(getattr(act, 'payload', {}) or {})
    return counts


def apm_timeseries(match, window_sec: int) -> pd.DataFrame:
    rows = [(act.timestamp.total_seconds(), act.player.number)
            for act in match.actions if getattr(act, 'player', None)]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=['t', 'player'])
    max_t = df['t'].max()
    bins = np.arange(0, max_t + window_sec, window_sec)
    apm: Dict[int, Any] = {}
    for pid in df['player'].unique():
        counts, _ = np.histogram(df.loc[df['player'] == pid, 't'], bins=bins)
        apm[int(pid)] = counts * 60 / window_sec
    ts = pd.DataFrame(apm, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts


def unit_created_timeseries(match, unit_pattern, window_sec: int) -> pd.DataFrame:
    rows = []  # (t, player, w)
    for act in match.actions:
        tname = getattr(getattr(act, 'type', None), 'name', '')
        if not _is_prod_event(tname):
            continue
        payload = getattr(act, 'payload', {}) or {}
        if not payload_matches(payload, unit_pattern):
            continue
        if not getattr(act, 'player', None):
            continue
        rows.append((act.timestamp.total_seconds(), act.player.number, payload_count(payload)))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=['t', 'player', 'w'])
    max_t = df['t'].max()
    bins = np.arange(0, max_t + window_sec, window_sec)
    out: Dict[int, Any] = {}
    for pid in df['player'].unique():
        mask = (df['player'] == pid)
        counts, _ = np.histogram(df.loc[mask, 't'], bins=bins, weights=df.loc[mask, 'w'])
        out[int(pid)] = counts.astype(int)
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts


def tc_idle_time(match, villager_pattern, base_prod_time: float = 25.0, gap_threshold: float = 27.0):
    idle = {p.number: 0.0 for p in match.players}
    last_train = {p.number: None for p in match.players}
    for act in match.actions:
        tname = getattr(getattr(act, 'type', None), 'name', '')
        if not _is_prod_event(tname):
            continue
        payload = getattr(act, 'payload', {}) or {}
        if not payload_matches(payload, villager_pattern):
            continue
        pid = getattr(getattr(act, 'player', None), 'number', None)
        if pid is None:
            continue
        t = act.timestamp.total_seconds()
        if last_train[pid] is not None:
            gap = t - last_train[pid]
            if gap > gap_threshold:
                idle[pid] += max(0.0, gap - base_prod_time)
        last_train[pid] = t
    return idle


def tc_idle_cumulative_timeseries(match, villager_pattern, window_sec: int, base_prod_time: float = 25.0, gap_threshold: float = 27.0) -> pd.DataFrame:
    incs = {p.number: [] for p in match.players}
    last = {p.number: None for p in match.players}
    for act in match.actions:
        tname = getattr(getattr(act, 'type', None), 'name', '')
        if not _is_prod_event(tname):
            continue
        payload = getattr(act, 'payload', {}) or {}
        if not payload_matches(payload, villager_pattern):
            continue
        pid = getattr(getattr(act, 'player', None), 'number', None)
        if pid is None:
            continue
        t = act.timestamp.total_seconds()
        if last[pid] is not None:
            gap = t - last[pid]
            if gap > gap_threshold:
                inc = max(0.0, gap - base_prod_time)
                incs[pid].append((t, inc))
        last[pid] = t
    all_times = []
    for pairs in incs.values():
        all_times += [t for t, _ in pairs]
    if not all_times:
        return pd.DataFrame()
    max_t = max(all_times)
    bins = np.arange(0, max_t + window_sec, window_sec)
    out: Dict[int, Any] = {}
    for pid, pairs in incs.items():
        if not pairs:
            continue
        pairs.sort(key=lambda x: x[0])
        t_arr = np.array([t for t, _ in pairs], dtype=float)
        inc_arr = np.array([v for _, v in pairs], dtype=float)
        cum = np.cumsum(inc_arr)
        s = pd.Series(cum, index=t_arr)
        out[int(pid)] = s.reindex(bins, method='ffill').fillna(0.0).values[:-1]
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts


def resource_totals_postgame(path: Path) -> Dict[int, Dict[str, float]]:
    """Attempt to extract per-player resource totals from postgame data.
    Returns mapping: pid -> {'food': x, 'wood': y, 'gold': z, 'stone': w}
    If not found, returns empty dict.
    """
    import mgz.fast as _mgz_fast
    data: Dict[str, Any]
    with open(path, 'rb') as fh:
        data = _mgz_fast.postgame(fh)

    results: Dict[int, Dict[str, float]] = {}

    def walk(obj: Any):
        if isinstance(obj, dict):
            # Common shapes: per-player dicts with resource keys
            keys = set(k.lower() for k in obj.keys())
            if {'food', 'wood', 'gold', 'stone'}.issubset(keys):
                # try to get player id
                pid = obj.get('player_id') or obj.get('player') or obj.get('id')
                try:
                    pid = int(pid)
                except Exception:
                    pid = None
                bucket = {k.lower(): float(obj.get(k, 0.0)) for k in ('food', 'wood', 'gold', 'stone')}
                if pid is not None:
                    results[int(pid)] = bucket
                return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    return results


def resource_cumulative_timeseries(match, per_player_totals: Dict[int, Dict[str, float]], resource: str, window_sec: int) -> pd.DataFrame:
    res = resource.lower()
    if res not in ('food', 'wood', 'gold', 'stone'):
        raise ValueError('Recurso no soportado')
    max_t = match.duration.total_seconds()
    bins = np.arange(0, max_t + window_sec, window_sec)
    out: Dict[int, Any] = {}
    for p in match.players:
        pid = int(p.number)
        total_val = float((per_player_totals.get(pid) or {}).get(res, 0.0))
        out[pid] = np.linspace(0.0, total_val, num=len(bins) - 1)
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts

