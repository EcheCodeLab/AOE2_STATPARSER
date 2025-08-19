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

