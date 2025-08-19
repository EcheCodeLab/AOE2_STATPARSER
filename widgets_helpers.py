from __future__ import annotations

from typing import Dict, Pattern

import numpy as np
import pandas as pd
import ipywidgets as widgets  # type: ignore
from IPython.display import display  # type: ignore
import matplotlib.pyplot as plt


def render_units_widget(match, unit_patterns: Dict[str, Pattern[str]], unit_created_timeseries, plot_units_created_ts):
    """Render a singleton widget to plot units created over time.

    - Avoids duplicate displays/observers on repeated execution
    - Adds player filter and window size selection
    """
    st = globals().get("UNITS_WIDGET_STATE")
    if st and isinstance(st, dict):
        try:
            st.get("unit_dropdown") and st["unit_dropdown"].unobserve(st.get("handler"), names="value")
            st.get("window_dropdown") and st["window_dropdown"].unobserve(st.get("handler"), names="value")
            st.get("player_select") and st["player_select"].unobserve(st.get("handler"), names="value")
        except Exception:
            pass
        out = st.get("out") or widgets.Output()
        unit_dropdown = st.get("unit_dropdown") or widgets.Dropdown(options=list(unit_patterns.keys()), value="Villager", description="Unidad:")
        window_dropdown = st.get("window_dropdown") or widgets.Dropdown(options=[15, 30, 45, 60, 90, 120], value=60, description="Ventana (s):")
        player_options = [(p.name, p.number) for p in match.players]
        player_select = st.get("player_select") or widgets.SelectMultiple(options=player_options, value=tuple(pid for _, pid in player_options), description="Jugadores:", rows=len(player_options))
    else:
        out = widgets.Output()
        unit_dropdown = widgets.Dropdown(options=list(unit_patterns.keys()), value="Villager", description="Unidad:")
        window_dropdown = widgets.Dropdown(options=[15, 30, 45, 60, 90, 120], value=60, description="Ventana (s):")
        player_options = [(p.name, p.number) for p in match.players]
        player_select = widgets.SelectMultiple(options=player_options, value=tuple(pid for _, pid in player_options), description="Jugadores:", rows=len(player_options))

    def handler(change=None):
        with out:
            out.clear_output(wait=True)
            unit = unit_dropdown.value
            w = int(window_dropdown.value)
            ts = unit_created_timeseries(match, unit_type=unit, window_sec=w)
            sel = list(player_select.value)
            if ts is not None and not ts.empty:
                keep = [pid for pid in ts.columns if pid in sel]
                if keep:
                    ts = ts[keep]
            plot_units_created_ts(ts, match, unit_type=unit, window_sec=w)

    unit_dropdown.observe(handler, names="value")
    window_dropdown.observe(handler, names="value")
    player_select.observe(handler, names="value")

    if not (st and st.get("displayed")):
        display(widgets.HBox([unit_dropdown, window_dropdown]))
        display(player_select)
        display(out)

    handler(None)
    globals()["UNITS_WIDGET_STATE"] = {
        "unit_dropdown": unit_dropdown,
        "window_dropdown": window_dropdown,
        "player_select": player_select,
        "out": out,
        "handler": handler,
        "displayed": True,
    }


def render_idle_widget(match, tc_idle_cumulative_timeseries, plot_tc_idle_cumulative):
    st = globals().get("IDLE_WIDGET_STATE")
    if st and isinstance(st, dict):
        try:
            st.get("window_dropdown") and st["window_dropdown"].unobserve(st.get("handler"), names="value")
        except Exception:
            pass
        out = st.get("out") or widgets.Output()
        window_dropdown = st.get("window_dropdown") or widgets.Dropdown(options=[15, 30, 45, 60, 90, 120], value=60, description="Ventana (s):")
    else:
        out = widgets.Output()
        window_dropdown = widgets.Dropdown(options=[15, 30, 45, 60, 90, 120], value=60, description="Ventana (s):")

    def handler(change=None):
        with out:
            out.clear_output(wait=True)
            w = int(window_dropdown.value)
            ts = tc_idle_cumulative_timeseries(match, window_sec=w)
            plot_tc_idle_cumulative(ts, match, window_sec=w)

    window_dropdown.observe(handler, names="value")
    if not (st and st.get("displayed")):
        display(window_dropdown)
        display(out)
    handler(None)
    globals()["IDLE_WIDGET_STATE"] = {
        "window_dropdown": window_dropdown,
        "out": out,
        "handler": handler,
        "displayed": True,
    }


def render_resources_widget(match, replay_path: str, resource_cumulative_timeseries, plot_resource_cumulative):
    st = globals().get("RES_WIDGET_STATE")
    if st and isinstance(st, dict):
        try:
            st.get("resource_dropdown") and st["resource_dropdown"].unobserve(st.get("handler"), names="value")
            st.get("window_dropdown") and st["window_dropdown"].unobserve(st.get("handler"), names="value")
        except Exception:
            pass
        out = st.get("out") or widgets.Output()
        resource_dropdown = st.get("resource_dropdown") or widgets.Dropdown(options=["food", "wood", "gold", "stone"], value="food", description="Recurso:")
        window_dropdown = st.get("window_dropdown") or widgets.Dropdown(options=[15, 30, 45, 60, 90, 120], value=60, description="Ventana (s):")
    else:
        out = widgets.Output()
        resource_dropdown = widgets.Dropdown(options=["food", "wood", "gold", "stone"], value="food", description="Recurso:")
        window_dropdown = widgets.Dropdown(options=[15, 30, 45, 60, 90, 120], value=60, description="Ventana (s):")

    def handler(change=None):
        with out:
            out.clear_output(wait=True)
            res = resource_dropdown.value
            w = int(window_dropdown.value)
            ts = resource_cumulative_timeseries(match, resource=res, window_sec=w)
            plot_resource_cumulative(ts, match, resource=res, window_sec=w)

    resource_dropdown.observe(handler, names="value")
    window_dropdown.observe(handler, names="value")
    if not (st and st.get("displayed")):
        display(widgets.HBox([resource_dropdown, window_dropdown]))
        display(out)
    handler(None)
    globals()["RES_WIDGET_STATE"] = {
        "resource_dropdown": resource_dropdown,
        "window_dropdown": window_dropdown,
        "out": out,
        "handler": handler,
        "displayed": True,
    }


# ---- Optional helpers to reduce notebook edits ----

def augment_unit_patterns(unit_patterns: Dict[str, Pattern[str]]) -> Dict[str, Pattern[str]]:
    """Ensure useful extra units exist (Knight line, etc.).

    Returns the same dict after (in-place) augmentation.
    """
    import re
    defaults: Dict[str, str] = {
        "Crossbowman": r"crossbow|ballestero",
        "Long Swordsman": r"long\s*sword|espad[oó]n|longsword",
        "Spearman": r"spearman|lancero",
        "Pikeman": r"pike|piquero",
        "Knight": r"knight|caballero",
        "Cavalier": r"cavalier|caballero\s*mejorado",
        "Paladin": r"paladin|palad[ií]n",
        "Camel": r"camel|camello",
        "Eagle": r"eagle|[áa]guila",
        "Cavalry Archer": r"cavalry\s*archer|ca|arquero\s*a\s*caballo",
        "Hand Cannoneer": r"hand\s*cannoneer|arcabucero|ca[ñn]onero\s*de\s*mano",
        "Hussar": r"hussar|husar",
    }
    for k, pattern in defaults.items():
        if k not in unit_patterns:
            unit_patterns[k] = __import__("re").compile(pattern, __import__("re").IGNORECASE)
    return unit_patterns


def tc_idle_cumulative_timeseries_auto(match, window_sec: int = 60, base_prod_time: float = 25.0, gap_threshold: float = 27.0):
    """Compute idle TC cumulative series using villager training events from match.actions.

    This mirrors the logic used in the notebook but self-contained here.
    """
    import numpy as np
    import pandas as pd
    import re

    villager_re = re.compile(r"villager|aldean", re.IGNORECASE)

    def payload_strings(obj, depth=0, max_depth=2):
        if depth > max_depth:
            return
        if isinstance(obj, dict):
            for v in obj.values():
                yield from payload_strings(v, depth + 1, max_depth)
        else:
            name = getattr(obj, "name", None) or getattr(obj, "unit_name", None)
            if isinstance(name, str):
                yield name
            if isinstance(obj, str):
                yield obj

    def payload_matches(payload, pattern):
        unit_obj = payload.get("unit") or {}
        name = (
            getattr(unit_obj, "name", None)
            or getattr(unit_obj, "unit_name", None)
            or (unit_obj.get("name") if isinstance(unit_obj, dict) else None)
            or payload.get("unit_name")
            or payload.get("object_name")
            or payload.get("item")
        )
        if name and pattern.search(str(name)):
            return True
        for s in payload_strings(payload):
            try:
                if pattern.search(str(s)):
                    return True
            except Exception:
                continue
        return False

    incs = {p.number: [] for p in match.players}
    last = {p.number: None for p in match.players}
    for act in match.actions:
        tname = getattr(getattr(act, "type", None), "name", "")
        if ("TRAIN" not in tname and "CREATE" not in tname and "QUEUE" not in tname and tname != "ORDER"):
            continue
        if not payload_matches(act.payload, villager_re):
            continue
        pid = getattr(getattr(act, "player", None), "number", None)
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
    out = {}
    for pid, pairs in incs.items():
        if not pairs:
            continue
        pairs.sort(key=lambda x: x[0])
        t_arr = np.array([t for t, _ in pairs], dtype=float)
        inc_arr = np.array([v for _, v in pairs], dtype=float)
        cum = np.cumsum(inc_arr)
        s = pd.Series(cum, index=t_arr)
        out[pid] = s.reindex(bins, method="ffill").fillna(0.0).values[:-1]
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = "time_sec"
    return ts


def plot_tc_idle_cumulative(ts, match, window_sec: int = 60):
    if ts.empty:
        print("Sin datos suficientes para idle TC acumulado.")
        return
    plt.figure(figsize=(10, 6))
    for pid in ts.columns:
        name = next(p.name for p in match.players if p.number == pid)
        plt.plot(ts.index / 60, ts[pid], label=name)
    plt.xlabel("Tiempo (min)")
    plt.ylabel("Idle TC acumulado (s)")
    plt.title(f"Idle TC acumulado — ventana {window_sec}s")
    plt.grid(True)
    plt.legend()
    plt.show()


def render_idle_widget_auto(match):
    return render_idle_widget(match, tc_idle_cumulative_timeseries_auto, plot_tc_idle_cumulative)


def resource_totals_postgame(replay_path: str):
    import mgz.fast as _mgz_fast
    with open(replay_path, "rb") as fh:
        data = _mgz_fast.postgame(fh)

    def find_totals(obj):
        if isinstance(obj, dict):
            keys = set(k.lower() for k in obj.keys())
            if {"food", "wood", "gold", "stone"}.issubset(keys):
                return obj
            for v in obj.values():
                r = find_totals(v)
                if r:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = find_totals(v)
                if r:
                    return r
        return None

    return data, find_totals(data)


def resource_cumulative_timeseries_auto(match, replay_path: str, resource: str = "food", window_sec: int = 60):
    import numpy as np
    import pandas as pd
    res = resource.lower()
    if res not in ("food", "wood", "gold", "stone"):
        raise ValueError("Recurso no soportado")
    try:
        _, totals = resource_totals_postgame(replay_path)
    except Exception:
        totals = None
    max_t = match.duration.total_seconds()
    bins = np.arange(0, max_t + window_sec, window_sec)
    out = {}
    for p in match.players:
        pid = p.number
        total_val = float((totals or {}).get(res, 0.0)) if isinstance(totals, dict) else 0.0
        out[pid] = np.linspace(0.0, total_val, num=len(bins) - 1)
    ts = pd.DataFrame(out, index=bins[:-1])
    ts.index.name = "time_sec"
    return ts


def plot_resource_cumulative(ts, match, resource: str, window_sec: int = 60):
    if ts.empty:
        print("Sin datos suficientes para recursos acumulados.")
        return
    plt.figure(figsize=(10, 6))
    for pid in ts.columns:
        name = next(p.name for p in match.players if p.number == pid)
        plt.plot(ts.index / 60, ts[pid], label=name)
    plt.xlabel("Tiempo (min)")
    plt.ylabel(f"{resource.title()} acumulado")
    plt.title(f"{resource.title()} acumulado — ventana {window_sec}s")
    plt.grid(True)
    plt.legend()
    plt.show()


def render_resources_widget_auto(match, replay_path: str):
    def _ts(match_, resource: str, window_sec: int):
        return resource_cumulative_timeseries_auto(match_, replay_path, resource=resource, window_sec=window_sec)
    return render_resources_widget(match, replay_path, _ts, plot_resource_cumulative)

