from __future__ import annotations

from typing import Protocol, Any

import pandas as pd

from .kpis import kpis_at_minute, kpis_by_window
from .metrics import apm_timeseries, tc_idle_time, villager_counts


class FeaturePlugin(Protocol):
    name: str

    def compute(self, match, events_raw: pd.DataFrame) -> dict[str, Any]:
        ...


class FeatureRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, FeaturePlugin] = {}

    def register(self, plugin: FeaturePlugin) -> None:
        self._plugins[plugin.name] = plugin

    def run_all(self, match, events_raw: pd.DataFrame) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, plugin in self._plugins.items():
            try:
                out[name] = plugin.compute(match, events_raw)
            except Exception as exc:
                out[name] = {"error": str(exc)}
        return out


class CoreKpiPlugin:
    name = "core_kpis"

    def compute(self, match, events_raw: pd.DataFrame) -> dict[str, Any]:
        import re

        vill_re = re.compile(r"villager|aldean", re.IGNORECASE)
        vills = villager_counts(match, villager_pattern=vill_re)
        idle = tc_idle_time(match, villager_pattern=vill_re)
        apm_ts = apm_timeseries(match, window_sec=60)
        apm_mean = {int(c): float(apm_ts[c].mean()) for c in apm_ts.columns} if not apm_ts.empty else {}
        kpi_window_df = kpis_by_window(match, window_sec=60)
        kpi_min20 = kpis_at_minute(match, minute=20, window_sec=60)
        return {
            "villagers_created": {int(k): int(v) for k, v in vills.items()},
            "idle_tc_seconds": {int(k): float(v) for k, v in idle.items()},
            "apm_mean_60s": apm_mean,
            "kpis_window_60s_rows": int(len(kpi_window_df)),
            "kpis_minute_20": kpi_min20,
        }


def default_feature_registry() -> FeatureRegistry:
    reg = FeatureRegistry()
    reg.register(CoreKpiPlugin())
    return reg
