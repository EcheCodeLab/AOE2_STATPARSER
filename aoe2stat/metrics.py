from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .core import payload_matches, payload_count
from .costs import unit_cost, building_cost, tech_cost


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
    """Extract per-player resource totals (food/wood/gold/stone) from postgame data.

    Returns mapping: pid -> {'food': x, 'wood': y, 'gold': z, 'stone': w}
    Tries multiple known shapes from mgz.fast.postgame output. Falls back to
    sequential player indexing (1..N) when explicit ids are absent.
    """
    # 1) Try fast postgame first
    try:
        import mgz.fast as _mgz_fast  # type: ignore
        with open(path, 'rb') as fh:
            data = _mgz_fast.postgame(fh)
    except Exception:
        data = {}  # type: ignore

    results: Dict[int, Dict[str, float]] = {}
    ordered_buckets: list[Dict[str, float]] = []

    def as_float(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def norm_bucket(d: Dict[str, Any]) -> Dict[str, float] | None:
        # Direct keys
        keys = {k.lower() for k in d.keys()}
        def pick(*names: str) -> float | None:
            for n in names:
                if n in d:
                    return as_float(d[n])
                # try case-insensitive
                for k in d.keys():
                    if k.lower() == n:
                        return as_float(d[k])
            return None

        # Nested under 'total_collected'
        if 'total_collected' in d and isinstance(d['total_collected'], dict):
            td = d['total_collected']
            if all(k in {kk.lower() for kk in td.keys()} for k in ('food', 'wood', 'gold', 'stone')):
                return {
                    'food': as_float(td.get('food', 0.0)),
                    'wood': as_float(td.get('wood', 0.0)),
                    'gold': as_float(td.get('gold', 0.0)),
                    'stone': as_float(td.get('stone', 0.0)),
                }

        # Flat variants
        food = pick('food', 'food_collected', 'total_food')
        wood = pick('wood', 'wood_collected', 'total_wood')
        gold = pick('gold', 'gold_collected', 'total_gold')
        stone = pick('stone', 'stone_collected', 'total_stone')
        vals = [v for v in (food, wood, gold, stone) if v is not None]
        if len(vals) >= 2 or (len(vals) == 1 and vals[0] and vals[0] > 0):  # some signal
            return {
                'food': float(food or 0.0),
                'wood': float(wood or 0.0),
                'gold': float(gold or 0.0),
                'stone': float(stone or 0.0),
            }
        # Nested economy dict
        if 'economy' in d and isinstance(d['economy'], dict):
            return norm_bucket(d['economy'])
        return None

    def maybe_record(d: Dict[str, Any], idx_for_fallback: int | None = None):
        bucket = norm_bucket(d)
        if bucket is None:
            return
        # Determine pid if present
        pid = d.get('player_id') or d.get('player') or d.get('id') or d.get('profile_id')
        try:
            pid = int(pid)  # type: ignore
        except Exception:
            pid = None
        if pid is not None:
            results[int(pid)] = bucket
        elif idx_for_fallback is not None:
            # keep ordered fallback for later mapping
            # ensure list long enough
            while len(ordered_buckets) <= idx_for_fallback:
                ordered_buckets.append({'food': 0.0, 'wood': 0.0, 'gold': 0.0, 'stone': 0.0})
            ordered_buckets[idx_for_fallback] = bucket

    # First, inspect common containers
    if isinstance(data, dict):
        for key in ('players', 'player', 'achievements', 'postgame', 'summary'):
            obj = data.get(key)
            if isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, dict):
                        maybe_record(item, idx_for_fallback=i)
            elif isinstance(obj, dict):
                # Sometimes achievements keyed by player id
                for k, v in obj.items():
                    if isinstance(v, dict):
                        try:
                            pid = int(k)
                        except Exception:
                            pid = None
                        if pid is not None:
                            b = norm_bucket(v)
                            if b is not None:
                                results[pid] = b

    # Generic deep walk as a last resort
    def walk(obj: Any):
        if isinstance(obj, dict):
            maybe_record(obj)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, dict):
                    maybe_record(v, idx_for_fallback=i)
                walk(v)

    if not results:
        walk(data)

    if results:
        return results

    # 2) Try achievements via mgz.summary Summary/FullSummary
    try:
        import mgz.summary as _mgz_summary  # type: ignore
        with open(path, 'rb') as fh:
            # Summary is cheaper; FullSummary may have more filled fields in some cases
            summ = _mgz_summary.Summary(fh)
            players = summ.get_players()
            if not players:
                fh.seek(0)
                summ = _mgz_summary.FullSummary(fh)
                players = summ.get_players()
        tmp: Dict[int, Dict[str, float]] = {}
        for p in players or []:
            pid = int(p.get('number')) if p.get('number') is not None else None
            ach = (p.get('achievements') or {}).get('economy') or {}
            vals = {
                'food': float(ach.get('food_collected') or 0.0),
                'wood': float(ach.get('wood_collected') or 0.0),
                'gold': float(ach.get('gold_collected') or 0.0),
                'stone': float(ach.get('stone_collected') or 0.0),
            }
            if pid is not None and any(v > 0 for v in vals.values()):
                tmp[pid] = vals
        if tmp:
            return tmp
    except Exception:
        pass

    # Fallback: map discovered buckets by order to player ids 1..N
    out: Dict[int, Dict[str, float]] = {}
    for i, b in enumerate(ordered_buckets):
        if any(v > 0 for v in b.values()):
            out[i + 1] = b
    return out


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


# ---- Estimated spend/balance based on actions ----

def _resource_delta_for_action(act) -> Tuple[int, int, int, int] | None:
    """Return resource deltas (food, wood, gold, stone) for a single action.
    Spends are negative; market BUY/SELL applies delta only to the named resource.
    """
    tname = getattr(getattr(act, 'type', None), 'name', '') or ''
    payload = getattr(act, 'payload', {}) or {}

    if tname in ('DE_QUEUE', 'QUEUE', 'ORDER', 'TRAIN', 'CREATE'):
        # Units (we key off unit if present)
        name = payload.get('unit') or payload.get('unit_name') or payload.get('object_name')
        if name:
            cost = unit_cost(str(name))
            if cost:
                amt = int(payload.get('amount') or 1)
                f, w, g, s = cost
                return (-f * amt, -w * amt, -g * amt, -s * amt)
    if tname == 'BUILD':
        name = payload.get('building') or payload.get('building_name')
        if name:
            cost = building_cost(str(name))
            if cost:
                amt = 1
                f, w, g, s = cost
                return (-f * amt, -w * amt, -g * amt, -s * amt)
    if tname == 'RESEARCH':
        name = payload.get('technology') or payload.get('tech')
        if name:
            cost = tech_cost(str(name))
            if cost:
                f, w, g, s = cost
                return (-f, -w, -g, -s)
    if tname in ('BUY', 'SELL'):
        res = str(payload.get('resource', '')).lower()
        amt = int(payload.get('amount') or 0)
        if amt:
            sign = 1 if tname == 'BUY' else -1
            if 'food' in res:
                return (sign * amt, 0, 0, 0)
            if 'wood' in res:
                return (0, sign * amt, 0, 0)
            if 'gold' in res:
                return (0, 0, sign * amt, 0)
            if 'stone' in res:
                return (0, 0, 0, sign * amt)
    return None


def resource_spend_timeseries(match, resource: str, window_sec: int) -> pd.DataFrame:
    """Estimated spend per window for a resource based on actions.

    Returns a DataFrame indexed by time (window start) and columns=player ids
    with positive values meaning absolute spend magnitude (so curves go up).
    """
    res = resource.lower()
    idx = {'food': 0, 'wood': 1, 'gold': 2, 'stone': 3}.get(res)
    if idx is None:
        raise ValueError('Recurso no soportado')

    rows: List[Tuple[float, int, float]] = []
    for act in match.actions:
        pid = getattr(getattr(act, 'player', None), 'number', None)
        if pid is None:
            continue
        delta = _resource_delta_for_action(act)
        if not delta:
            continue
        val = float(delta[idx])
        if val >= 0:
            # spend is negative; skip non-spend deltas here
            continue
        rows.append((act.timestamp.total_seconds(), int(pid), -val))  # store as positive spend
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=['t', 'player', 'w'])
    max_t = df['t'].max()
    bins = np.arange(0, max_t + window_sec, window_sec)
    out: Dict[int, Any] = {}
    for pid in df['player'].unique():
        mask = df['player'] == pid
        sums, _ = np.histogram(df.loc[mask, 't'], bins=bins, weights=df.loc[mask, 'w'])
        out[int(pid)] = sums.astype(float)
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts


def resource_balance_timeseries(match, resource: str, window_sec: int, start_at: float = 0.0) -> pd.DataFrame:
    """Approximate stock over time from spends (negative) and market (BUY/SELL) deltas.

    Starts at 0 by default (relative balance). This is not exact income; villager gathering
    is not exposed in actions and would require sync parsing. Use this as an approximation.
    """
    res = resource.lower()
    idx = {'food': 0, 'wood': 1, 'gold': 2, 'stone': 3}.get(res)
    if idx is None:
        raise ValueError('Recurso no soportado')
    rows: List[Tuple[float, int, float]] = []
    for act in match.actions:
        pid = getattr(getattr(act, 'player', None), 'number', None)
        if pid is None:
            continue
        delta = _resource_delta_for_action(act)
        if not delta:
            continue
        rows.append((act.timestamp.total_seconds(), int(pid), float(delta[idx])))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=['t', 'player', 'delta'])
    max_t = df['t'].max()
    bins = np.arange(0, max_t + window_sec, window_sec)
    out: Dict[int, Any] = {}
    for pid in df['player'].unique():
        mask = df['player'] == pid
        sums, _ = np.histogram(df.loc[mask, 't'], bins=bins, weights=df.loc[mask, 'delta'])
        bal = np.cumsum(sums.astype(float))
        bal = bal + start_at
        out[int(pid)] = bal
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts


def total_spend_timeseries(match, window_sec: int, cumulative: bool = True) -> pd.DataFrame:
    """Total spend across all resources per player per window.

    If cumulative=True, returns cumulative sum over windows (monotonic increasing curves).
    """
    rows: List[Tuple[float, int, float]] = []
    for act in match.actions:
        pid = getattr(getattr(act, 'player', None), 'number', None)
        if pid is None:
            continue
        delta = _resource_delta_for_action(act)
        if not delta:
            continue
        # spend is negative across any resource; sum absolute spend
        spend = sum((-v) for v in delta if v < 0)
        if spend <= 0:
            continue
        rows.append((act.timestamp.total_seconds(), int(pid), float(spend)))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=['t', 'player', 'w'])
    max_t = df['t'].max()
    bins = np.arange(0, max_t + window_sec, window_sec)
    out: Dict[int, Any] = {}
    for pid in df['player'].unique():
        mask = df['player'] == pid
        sums, _ = np.histogram(df.loc[mask, 't'], bins=bins, weights=df.loc[mask, 'w'])
        series = sums.astype(float)
        if cumulative:
            series = np.cumsum(series)
        out[int(pid)] = series
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts


def important_events(match) -> pd.DataFrame:
    """Extract important game events for annotation: age-ups, castles, elite techs.

    Returns a DataFrame with columns: time_sec, player, label, kind
    kind in {age, castle, elite, tech}
    """
    rows: List[Tuple[float, int, str, str]] = []
    for act in match.actions:
        pid = getattr(getattr(act, 'player', None), 'number', None)
        if pid is None:
            continue
        t = act.timestamp.total_seconds()
        tname = getattr(getattr(act, 'type', None), 'name', '') or ''
        payload = getattr(act, 'payload', {}) or {}
        if tname == 'RESEARCH':
            tech = str(payload.get('technology') or '')
            lname = tech.lower()
            if lname in ('feudal age', 'castle age', 'imperial age'):
                rows.append((t, int(pid), tech, 'age'))
            elif lname.startswith('elite '):
                rows.append((t, int(pid), tech, 'elite'))
            else:
                # Mark some high-impact techs
                hi = {
                    'bracer', 'chemistry', 'hand cart', 'wheelbarrow', 'conscription',
                    'ballistics', 'siege engineers', 'architecture', 'thumb ring'
                }
                if any(k in lname for k in hi):
                    rows.append((t, int(pid), tech, 'tech'))
        elif tname == 'BUILD':
            b = str(payload.get('building') or '')
            lb = b.lower()
            if lb == 'castle':
                rows.append((t, int(pid), b, 'castle'))
            if lb == 'town center':
                rows.append((t, int(pid), b, 'tc'))
    if not rows:
        return pd.DataFrame(columns=['time_sec', 'player', 'label', 'kind'])
    df = pd.DataFrame(rows, columns=['time_sec', 'player', 'label', 'kind'])
    df = df.sort_values('time_sec').drop_duplicates(subset=['player','label'], keep='first')
    return df


def sync_total_resources_timeseries(path: Path, window_sec: int) -> pd.DataFrame:
    """Parse sync packets to build per-player total resource stock over time (sum of f+w+g+s).

    Returns DataFrame indexed by window start seconds with columns=player ids.
    Values are forward-filled snapshots aggregated into bins.
    """
    import mgz.fast as fast
    times: List[float] = []
    per_pid: Dict[int, List[Tuple[float, float]]] = {}
    with open(path, 'rb') as fh:
        # Advance to start of body
        try:
            fast.start(fh)
        except Exception:
            pass
        while True:
            try:
                op_type, payload = fast.operation(fh)
            except EOFError:
                break
            except Exception:
                # Skip unknown
                continue
            if op_type != fast.Operation.SYNC:
                continue
            increment, checksum, pl = payload
            # Only DE payload has dict of players
            if not isinstance(pl, dict):
                continue
            t_ms = pl.get('current_time')
            if t_ms is None:
                continue
            t = float(t_ms) / 1000.0
            times.append(t)
            for k, v in pl.items():
                if k == 'current_time':
                    continue
                try:
                    pid = int(k)
                except Exception:
                    continue
                total_res = float(v.get('total_res', 0.0)) if isinstance(v, dict) else 0.0
                per_pid.setdefault(pid, []).append((t, total_res))
    if not per_pid:
        return pd.DataFrame()
    max_t = max(times) if times else 0.0
    bins = np.arange(0, max_t + window_sec, window_sec)
    out: Dict[int, Any] = {}
    for pid, pairs in per_pid.items():
        pairs.sort(key=lambda x: x[0])
        t_arr = np.array([t for t, _ in pairs], dtype=float)
        val_arr = np.array([v for _, v in pairs], dtype=float)
        s = pd.Series(val_arr, index=t_arr)
        out[int(pid)] = s.reindex(bins, method='ffill').fillna(method='bfill').fillna(0.0).values[:-1]
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = 'time_sec'
    return ts


def approximate_total_balance_timeseries(match, window_sec: int, start_at: Tuple[int, int, int, int] = (200, 200, 100, 200)) -> pd.DataFrame:
    """Approximate total (food+wood+gold+stone) balance from action-based balance per resource.

    Returns DataFrame with per-player total balance across resources.
    """
    # Compute per-resource balances
    res_names = ['food', 'wood', 'gold', 'stone']
    starts = dict(zip(res_names, start_at))
    frames = []
    for r in res_names:
        try:
            ts = resource_balance_timeseries(match, resource=r, window_sec=window_sec, start_at=float(starts.get(r, 0)))
        except Exception:
            ts = pd.DataFrame()
        frames.append(ts)
    # Align by index
    idx = None
    for f in frames:
        if f is not None and not f.empty:
            idx = f.index if idx is None else idx.union(f.index)
    if idx is None:
        return pd.DataFrame()
    total: Dict[int, Any] = {}
    for f in frames:
        if f is None or f.empty:
            continue
        for col in f.columns:
            total[col] = total.get(col, 0) + f.reindex(idx).fillna(method='ffill').fillna(0)[col]
    out = pd.DataFrame(total, index=idx)
    out.index.name = 'time_sec'
    return out
