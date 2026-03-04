from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd


@dataclass
class DataFrameBundle:
    match_meta: dict[str, Any]
    events_raw: pd.DataFrame
    spatial_frames: pd.DataFrame
    features: dict[str, Any]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_meta": self.match_meta,
            "events_count": int(len(self.events_raw)),
            "spatial_frames_count": int(len(self.spatial_frames)),
            "features": self.features,
            "validation": self.validation,
        }


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    try:
        return asdict(obj)
    except Exception:
        if hasattr(obj, "__dict__"):
            return dict(obj.__dict__)
        raise TypeError(f"Unsupported object type: {type(obj)}")

