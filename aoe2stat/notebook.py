from __future__ import annotations

from pathlib import Path
from typing import Any

from .services import ReplayAnalysisService


def analyze_replay_for_notebook(
    replay_path: str | Path,
    grid_size: int = 32,
    window_sec: int = 10,
) -> dict[str, Any]:
    """Convenience wrapper for notebook usage.

    Returns a dict with metadata, features, validation and DataFrames
    (`events_raw`, `spatial_frames`) ready for EDA/plotting.
    """
    service = ReplayAnalysisService()
    bundle = service.analyze(replay_path, grid_size=grid_size, window_sec=window_sec)
    return {
        "match_meta": bundle.match_meta,
        "features": bundle.features,
        "validation": bundle.validation,
        "events_raw": bundle.events_raw,
        "spatial_frames": bundle.spatial_frames,
    }

