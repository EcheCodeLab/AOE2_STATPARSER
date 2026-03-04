from __future__ import annotations

from typing import Any

import pandas as pd

from .metrics import (
    apm_timeseries,
    approximate_total_balance_timeseries,
    tc_idle_cumulative_timeseries,
    unit_created_timeseries,
)
from .patterns import base_unit_patterns


def _empty_kpi_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "time_sec",
            "player_id",
            "apm",
            "villagers_created_window",
            "villagers_created_cum",
            "idle_tc_cum_sec",
            "floating_total",
        ]
    )


def _aligned_series(ts: pd.DataFrame, idx: pd.Index, pid: int, default: float = 0.0) -> pd.Series:
    if ts.empty or pid not in ts.columns:
        return pd.Series(default, index=idx, dtype=float)
    return ts[pid].reindex(idx).ffill().fillna(default).astype(float)


def kpis_by_window(match, window_sec: int = 30) -> pd.DataFrame:
    """Compute core KPI table by configurable windows.

    Output columns:
    - time_sec: window start in seconds
    - player_id
    - apm
    - villagers_created_window
    - villagers_created_cum
    - idle_tc_cum_sec
    - floating_total: approximate total resources (f+w+g+s)
    """
    w = max(1, int(window_sec))
    villager_pattern = base_unit_patterns()["Villager"]

    apm_ts = apm_timeseries(match, window_sec=w)
    vill_window_ts = unit_created_timeseries(match, villager_pattern, window_sec=w)
    idle_cum_ts = tc_idle_cumulative_timeseries(match, villager_pattern, window_sec=w)
    floating_ts = approximate_total_balance_timeseries(match, window_sec=w)

    idx: pd.Index | None = None
    for frame in (apm_ts, vill_window_ts, idle_cum_ts, floating_ts):
        if frame is not None and not frame.empty:
            idx = frame.index if idx is None else idx.union(frame.index)
    if idx is None:
        return _empty_kpi_frame()
    idx = idx.sort_values()

    rows: list[dict[str, Any]] = []
    for p in getattr(match, "players", []):
        pid = int(getattr(p, "number", 0))
        apm_s = _aligned_series(apm_ts, idx, pid)
        vill_window_s = _aligned_series(vill_window_ts, idx, pid)
        vill_cum_s = vill_window_s.cumsum()
        idle_cum_s = _aligned_series(idle_cum_ts, idx, pid)
        floating_s = _aligned_series(floating_ts, idx, pid)

        for t in idx:
            rows.append(
                {
                    "time_sec": int(t),
                    "player_id": pid,
                    "apm": float(apm_s.loc[t]),
                    "villagers_created_window": int(round(vill_window_s.loc[t])),
                    "villagers_created_cum": int(round(vill_cum_s.loc[t])),
                    "idle_tc_cum_sec": float(idle_cum_s.loc[t]),
                    "floating_total": float(floating_s.loc[t]),
                }
            )
    if not rows:
        return _empty_kpi_frame()
    return pd.DataFrame(rows).sort_values(["time_sec", "player_id"]).reset_index(drop=True)


def kpis_at_minute(match, minute: int = 20, window_sec: int = 30) -> dict[str, Any]:
    """Compute cumulative KPIs at minute N for each player."""
    target_sec = max(0, int(minute)) * 60
    df = kpis_by_window(match, window_sec=window_sec)
    if df.empty:
        return {
            "minute": int(minute),
            "target_time_sec": target_sec,
            "window_sec": int(window_sec),
            "players": {},
        }

    out: dict[str, Any] = {}
    for pid, g in df.groupby("player_id"):
        g2 = g[g["time_sec"] <= target_sec]
        if g2.empty:
            out[str(int(pid))] = {
                "time_sec": 0,
                "apm_avg_to_minute": 0.0,
                "villagers_created_cum": 0,
                "idle_tc_cum_sec": 0.0,
                "floating_total": 0.0,
            }
            continue
        last = g2.iloc[-1]
        out[str(int(pid))] = {
            "time_sec": int(last["time_sec"]),
            "apm_avg_to_minute": float(g2["apm"].mean()),
            "villagers_created_cum": int(last["villagers_created_cum"]),
            "idle_tc_cum_sec": float(last["idle_tc_cum_sec"]),
            "floating_total": float(last["floating_total"]),
        }

    return {
        "minute": int(minute),
        "target_time_sec": target_sec,
        "window_sec": int(window_sec),
        "players": out,
    }
