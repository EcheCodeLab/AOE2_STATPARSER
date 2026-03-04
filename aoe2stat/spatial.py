from __future__ import annotations

import pandas as pd

from .pipeline import spatial_frames_from_events


def build_spatial_frames(
    events_raw: pd.DataFrame,
    map_dimension: float,
    grid_size: int,
    window_sec: int,
) -> pd.DataFrame:
    return spatial_frames_from_events(
        events_raw,
        map_dimension=map_dimension,
        grid_size=grid_size,
        window_sec=window_sec,
    )

