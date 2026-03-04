"""AoE2 Stat parsing and visualization utilities."""

from .config import AppConfig
from .services import ReplayAnalysisService
from .features import FeatureRegistry, FeaturePlugin, default_feature_registry
from .kpis import kpis_by_window, kpis_at_minute
from .notebook import analyze_replay_for_notebook

__all__ = [
    "AppConfig",
    "ReplayAnalysisService",
    "FeatureRegistry",
    "FeaturePlugin",
    "default_feature_registry",
    "kpis_by_window",
    "kpis_at_minute",
    "analyze_replay_for_notebook",
]
