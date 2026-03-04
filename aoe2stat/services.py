from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .features import FeatureRegistry, default_feature_registry
from .io import read_match
from .pipeline import build_match_meta, extract_raw_events
from .schema import DataFrameBundle, dataclass_to_dict
from .spatial import build_spatial_frames
from .validation import validate_events_raw, validate_spatial_frames


class ReplayAnalysisService:
    def __init__(self, config: AppConfig | None = None, feature_registry: FeatureRegistry | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.feature_registry = feature_registry or default_feature_registry()

    def analyze(
        self,
        replay_path: str | Path,
        grid_size: int | None = None,
        window_sec: int | None = None,
    ) -> DataFrameBundle:
        replay_path = Path(replay_path)
        match = read_match(replay_path)
        meta = build_match_meta(match, replay_path)
        events_raw = extract_raw_events(match, match_id=meta.match_id)
        spatial_frames = build_spatial_frames(
            events_raw,
            map_dimension=meta.map_dimension,
            grid_size=int(grid_size or self.config.default_grid_size),
            window_sec=int(window_sec or self.config.default_window_sec),
        )
        features = self.feature_registry.run_all(match, events_raw)
        validation = {
            "events_raw": validate_events_raw(events_raw),
            "spatial_frames": validate_spatial_frames(spatial_frames),
        }
        return DataFrameBundle(
            match_meta=dataclass_to_dict(meta),
            events_raw=events_raw,
            spatial_frames=spatial_frames,
            features=features,
            validation=validation,
        )

