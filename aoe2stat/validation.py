from __future__ import annotations

from typing import Any

import pandas as pd


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_match_meta(match_meta: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = ["match_id", "duration_sec", "map_dimension", "players"]
    for c in required:
        if c not in match_meta:
            issues.append(_issue("missing_field", f"Missing required match_meta field: {c}"))

    if "match_id" in match_meta and not str(match_meta.get("match_id") or "").strip():
        issues.append(_issue("empty_match_id", "match_meta.match_id is empty."))
    if "duration_sec" in match_meta:
        try:
            if float(match_meta.get("duration_sec", 0.0)) < 0.0:
                issues.append(_issue("negative_duration", "match_meta.duration_sec is negative."))
        except Exception:
            issues.append(_issue("invalid_duration", "match_meta.duration_sec is not numeric."))
    if "map_dimension" in match_meta:
        try:
            if float(match_meta.get("map_dimension", 0.0)) <= 0.0:
                issues.append(_issue("invalid_map_dimension", "match_meta.map_dimension must be > 0."))
        except Exception:
            issues.append(_issue("invalid_map_dimension", "match_meta.map_dimension is not numeric."))
    players = match_meta.get("players", [])
    if not isinstance(players, list):
        issues.append(_issue("invalid_players_list", "match_meta.players must be a list."))
        players = []
    return {"ok": len(issues) == 0, "issues": issues, "rows": int(len(players))}


def validate_players(players: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(players, list):
        return {"ok": False, "issues": [_issue("invalid_players", "players must be a list of dicts.")], "rows": 0}
    seen_ids: set[int] = set()
    for idx, p in enumerate(players):
        if not isinstance(p, dict):
            issues.append(_issue("invalid_player_row", f"players[{idx}] is not a dict."))
            continue
        pid_raw = p.get("player_id")
        pname = str(p.get("player_name") or "").strip()
        try:
            pid = int(pid_raw)
        except Exception:
            issues.append(_issue("invalid_player_id", f"players[{idx}].player_id is not an integer."))
            continue
        if pid <= 0:
            issues.append(_issue("invalid_player_id", f"players[{idx}].player_id must be > 0."))
        if pid in seen_ids:
            issues.append(_issue("duplicate_player_id", f"Duplicate player_id in players: {pid}."))
        seen_ids.add(pid)
        if not pname:
            issues.append(_issue("empty_player_name", f"players[{idx}].player_name is empty."))
    return {"ok": len(issues) == 0, "issues": issues, "rows": int(len(players))}


def validate_events_raw(events_raw: pd.DataFrame) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = ["event_id", "match_id", "t_ms", "time_sec", "action_type", "action_family"]
    for c in required:
        if c not in events_raw.columns:
            issues.append(_issue("missing_column", f"Missing required column: {c}"))
    if not events_raw.empty and "t_ms" in events_raw.columns:
        if (events_raw["t_ms"] < 0).any():
            issues.append(_issue("negative_time", "Negative timestamps found in events_raw."))
    if not events_raw.empty and "time_sec" in events_raw.columns:
        if (events_raw["time_sec"] < 0).any():
            issues.append(_issue("negative_time_sec", "Negative time_sec found in events_raw."))
    if not events_raw.empty and "event_id" in events_raw.columns:
        if events_raw["event_id"].duplicated().any():
            issues.append(_issue("duplicate_event_id", "Duplicate event_id values detected."))
    if not events_raw.empty and "match_id" in events_raw.columns:
        if events_raw["match_id"].nunique(dropna=True) > 1:
            issues.append(_issue("multiple_match_ids", "events_raw contains multiple match_id values."))
    if not events_raw.empty and "action_family" in events_raw.columns:
        allowed = {"movement", "build", "production", "research", "economy", "military", "other"}
        invalid = set(str(v) for v in events_raw["action_family"].dropna().unique()) - allowed
        if invalid:
            issues.append(_issue("invalid_action_family", f"Unknown action_family values: {sorted(invalid)}"))
    if not events_raw.empty and "event_type_semantic" in events_raw.columns:
        allowed_semantic = {
            "age_up",
            "tech_research",
            "building_build",
            "build_command",
            "unit_train",
            "move_command",
            "economy_command",
            "military_command",
            "delete_command",
            "other",
        }
        invalid_semantic = set(str(v) for v in events_raw["event_type_semantic"].dropna().unique()) - allowed_semantic
        if invalid_semantic:
            issues.append(
                _issue("invalid_event_type_semantic", f"Unknown event_type_semantic values: {sorted(invalid_semantic)}")
            )
    if not events_raw.empty and {"x", "y"}.issubset(events_raw.columns):
        xna = events_raw["x"].isna()
        yna = events_raw["y"].isna()
        mismatch = (xna ^ yna).any()
        if mismatch:
            issues.append(_issue("partial_xy", "Some events have only one coordinate (x or y)."))
    return {"ok": len(issues) == 0, "issues": issues, "rows": int(len(events_raw))}


def validate_spatial_frames(spatial_frames: pd.DataFrame) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = ["time_bin_sec", "grid_size", "cell_x", "cell_y", "event_count"]
    for c in required:
        if c not in spatial_frames.columns:
            issues.append(_issue("missing_column", f"Missing required column: {c}"))
    if not spatial_frames.empty and "event_count" in spatial_frames.columns:
        if (spatial_frames["event_count"] < 0).any():
            issues.append(_issue("negative_event_count", "Negative event_count detected."))
    if not spatial_frames.empty and "grid_size" in spatial_frames.columns:
        if (spatial_frames["grid_size"] < 4).any():
            issues.append(_issue("invalid_grid_size", "grid_size must be >= 4."))
    if not spatial_frames.empty and "window_sec" in spatial_frames.columns:
        if (spatial_frames["window_sec"] < 1).any():
            issues.append(_issue("invalid_window_sec", "window_sec must be >= 1."))
    if not spatial_frames.empty and {"cell_x", "cell_y", "grid_size"}.issubset(spatial_frames.columns):
        oob_x = (spatial_frames["cell_x"] < 0) | (spatial_frames["cell_x"] >= spatial_frames["grid_size"])
        oob_y = (spatial_frames["cell_y"] < 0) | (spatial_frames["cell_y"] >= spatial_frames["grid_size"])
        if oob_x.any() or oob_y.any():
            issues.append(_issue("cell_out_of_bounds", "Found cell_x/cell_y out of [0, grid_size-1]."))
    if not spatial_frames.empty and "match_id" in spatial_frames.columns:
        if spatial_frames["match_id"].nunique(dropna=True) > 1:
            issues.append(_issue("multiple_match_ids", "spatial_frames contains multiple match_id values."))
    return {"ok": len(issues) == 0, "issues": issues, "rows": int(len(spatial_frames))}


def validate_integrity(
    match_meta: dict[str, Any],
    events_raw: pd.DataFrame,
    spatial_frames: pd.DataFrame,
) -> dict[str, Any]:
    out = {
        "matches": validate_match_meta(match_meta),
        "players": validate_players(match_meta.get("players", [])),
        "events_raw": validate_events_raw(events_raw),
        "spatial_frames": validate_spatial_frames(spatial_frames),
    }

    issues: list[dict[str, str]] = []
    meta_match_id = str(match_meta.get("match_id") or "")
    if meta_match_id and not events_raw.empty and "match_id" in events_raw.columns:
        ev_ids = {str(v) for v in events_raw["match_id"].dropna().unique()}
        if ev_ids != {meta_match_id}:
            issues.append(_issue("events_match_id_mismatch", f"events_raw match_id set != match_meta.match_id ({meta_match_id})."))
    if meta_match_id and not spatial_frames.empty and "match_id" in spatial_frames.columns:
        sp_ids = {str(v) for v in spatial_frames["match_id"].dropna().unique()}
        if sp_ids != {meta_match_id}:
            issues.append(_issue("spatial_match_id_mismatch", f"spatial_frames match_id set != match_meta.match_id ({meta_match_id})."))

    meta_player_ids = set()
    for p in match_meta.get("players", []) if isinstance(match_meta.get("players", []), list) else []:
        try:
            meta_player_ids.add(int(p.get("player_id")))
        except Exception:
            pass
    if meta_player_ids and not events_raw.empty and "player_id" in events_raw.columns:
        ev_pids = {int(v) for v in events_raw["player_id"].dropna().unique() if int(v) > 0}
        extra = ev_pids - meta_player_ids
        if extra:
            issues.append(_issue("events_unknown_player_id", f"events_raw has player_id not present in match_meta.players: {sorted(extra)}"))

    out["integrity_cross_table"] = {
        "ok": len(issues) == 0,
        "issues": issues,
        "rows": int(len(events_raw) + len(spatial_frames)),
    }
    out["ok"] = all(bool(v.get("ok")) for k, v in out.items() if isinstance(v, dict) and "ok" in v)
    return out
