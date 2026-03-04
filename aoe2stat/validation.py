from __future__ import annotations

from typing import Any

import pandas as pd


def validate_events_raw(events_raw: pd.DataFrame) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = ["event_id", "match_id", "t_ms", "time_sec", "action_type"]
    for c in required:
        if c not in events_raw.columns:
            issues.append({"code": "missing_column", "message": f"Missing required column: {c}"})
    if not events_raw.empty and "t_ms" in events_raw.columns:
        if (events_raw["t_ms"] < 0).any():
            issues.append({"code": "negative_time", "message": "Negative timestamps found in events_raw."})
    if not events_raw.empty and "event_id" in events_raw.columns:
        if events_raw["event_id"].duplicated().any():
            issues.append({"code": "duplicate_event_id", "message": "Duplicate event_id values detected."})
    return {"ok": len(issues) == 0, "issues": issues, "rows": int(len(events_raw))}


def validate_spatial_frames(spatial_frames: pd.DataFrame) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = ["time_bin_sec", "grid_size", "cell_x", "cell_y", "event_count"]
    for c in required:
        if c not in spatial_frames.columns:
            issues.append({"code": "missing_column", "message": f"Missing required column: {c}"})
    if not spatial_frames.empty and "event_count" in spatial_frames.columns:
        if (spatial_frames["event_count"] < 0).any():
            issues.append({"code": "negative_event_count", "message": "Negative event_count detected."})
    return {"ok": len(issues) == 0, "issues": issues, "rows": int(len(spatial_frames))}

