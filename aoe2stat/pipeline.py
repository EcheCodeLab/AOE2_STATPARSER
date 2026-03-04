from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import mgz


@dataclass
class MatchMeta:
    match_id: str
    replay_path: str
    duration_sec: float
    map_name: str
    map_dimension: float
    players: list[dict[str, Any]]
    map_id: int | None = None
    game_type: str | None = None
    patch_version: str | None = None
    map_seed: int | None = None
    random_seed: int | None = None


def build_match_meta(match, replay_path: str | Path) -> MatchMeta:
    def _to_int_or_none(value: Any) -> int | None:
        try:
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                if not value:
                    return None
                return int(value[0])
            return int(value)
        except Exception:
            return None

    def _to_str_or_none(value: Any) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    map_obj = getattr(match, "map", None)
    rp = Path(replay_path)
    players = []
    for p in match.players:
        team_id = _to_int_or_none(getattr(p, "team_id", None))
        if team_id is None:
            team_id = _to_int_or_none(getattr(p, "team", None))
        rating = _to_int_or_none(getattr(p, "rating", None))
        if rating is None:
            rating = _to_int_or_none(getattr(p, "elo", None))
        if rating is None:
            rating = _to_int_or_none(getattr(p, "elo_rating", None))
        players.append(
            {
                "player_id": int(getattr(p, "number", 0)),
                "player_name": str(getattr(p, "name", "")),
                "civilization": str(getattr(getattr(p, "civilization", None), "name", "") or ""),
                "color_id": int(getattr(p, "color_id", 0) or 0),
                "team_id": team_id,
                "rating": rating,
                "profile_id": _to_int_or_none(getattr(p, "profile_id", None)),
            }
        )
    return MatchMeta(
        match_id=rp.stem,
        replay_path=str(rp),
        duration_sec=float(match.duration.total_seconds()),
        map_name=str(getattr(map_obj, "name", "") or ""),
        map_dimension=float(getattr(map_obj, "dimension", 120) or 120),
        map_id=_to_int_or_none(getattr(map_obj, "id", None)),
        game_type=_to_str_or_none(
            getattr(match, "game_type", None)
            or getattr(match, "game_mode", None)
            or getattr(match, "mode", None)
        ),
        patch_version=_to_str_or_none(getattr(match, "version", None)),
        map_seed=_to_int_or_none(getattr(match, "map_seed", None)),
        random_seed=_to_int_or_none(getattr(match, "seed", None) or getattr(match, "random_seed", None)),
        players=players,
    )


def _action_family(action_type: str) -> str:
    t = (action_type or "").upper()
    if t in {"MOVE", "PATROL", "DE_ATTACK_MOVE", "GATHER_POINT", "DE_MULTI_GATHERPOINT"}:
        return "movement"
    if t in {"BUILD", "WALL", "DELETE"}:
        return "build"
    if t in {"DE_QUEUE", "QUEUE", "TRAIN", "CREATE", "ORDER"}:
        return "production"
    if t in {"RESEARCH"}:
        return "research"
    if t in {"BUY", "SELL", "BACK_TO_WORK"}:
        return "economy"
    if t in {"STOP", "STANCE", "FORMATION", "SPECIAL", "UNGARRISON"}:
        return "military"
    return "other"


def _semantic_event_type(action_type: str, payload: dict[str, Any]) -> str:
    t = (action_type or "").upper()
    research = str(payload.get("technology") or payload.get("research") or "").lower()
    building = str(payload.get("building") or "").lower()

    if t == "RESEARCH":
        if any(k in research for k in ("feudal age", "castle age", "imperial age")):
            return "age_up"
        return "tech_research"
    if t in {"BUILD", "WALL"}:
        if building:
            return "building_build"
        return "build_command"
    if t in {"DE_QUEUE", "QUEUE", "TRAIN", "CREATE", "ORDER"}:
        return "unit_train"
    if t in {"MOVE", "PATROL", "DE_ATTACK_MOVE", "GATHER_POINT", "DE_MULTI_GATHERPOINT"}:
        return "move_command"
    if t in {"BUY", "SELL", "BACK_TO_WORK"}:
        return "economy_command"
    if t in {"STOP", "STANCE", "FORMATION", "SPECIAL", "UNGARRISON"}:
        return "military_command"
    if t == "DELETE":
        return "delete_command"
    return "other"


def _event_label(action_type: str, event_type_semantic: str, payload: dict[str, Any]) -> str:
    if event_type_semantic in {"age_up", "tech_research"}:
        return str(payload.get("technology") or payload.get("research") or action_type or "").strip()
    if event_type_semantic in {"building_build", "build_command"}:
        return str(payload.get("building") or action_type or "").strip()
    if event_type_semantic == "unit_train":
        return str(payload.get("unit") or payload.get("object_name") or action_type or "").strip()
    if event_type_semantic in {"move_command", "economy_command", "military_command", "delete_command"}:
        return str(action_type or "").strip()
    return ""


def extract_raw_events(match, match_id: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for idx, act in enumerate(match.actions):
        tname = str(getattr(getattr(act, "type", None), "name", "") or "")
        player = getattr(act, "player", None)
        pid = int(getattr(player, "number", 0) or 0)
        pname = str(getattr(player, "name", "") or "")
        ts = getattr(act, "timestamp", None)
        time_sec = float(ts.total_seconds()) if ts is not None else 0.0
        t_ms = int(round(time_sec * 1000.0))
        pos = getattr(act, "position", None)
        x = float(getattr(pos, "x", np.nan)) if pos is not None else np.nan
        y = float(getattr(pos, "y", np.nan)) if pos is not None else np.nan
        payload = getattr(act, "payload", {}) or {}
        payload_json = json.dumps(payload, ensure_ascii=True, default=str, sort_keys=True)
        event_type_semantic = _semantic_event_type(tname, payload)
        event_label = _event_label(tname, event_type_semantic, payload)
        rows.append(
            {
                "event_id": idx,
                "match_id": match_id,
                "t_ms": t_ms,
                "time_sec": time_sec,
                "player_id": pid,
                "player_name": pname,
                "action_type": tname,
                "action_family": _action_family(tname),
                "event_type_semantic": event_type_semantic,
                "event_label": event_label,
                "x": x,
                "y": y,
                "payload_json": payload_json,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "event_id",
                "match_id",
                "t_ms",
                "time_sec",
                "player_id",
                "player_name",
                "action_type",
                "action_family",
                "event_type_semantic",
                "event_label",
                "x",
                "y",
                "payload_json",
            ]
        )
    return pd.DataFrame(rows)


def extract_base_timelines(events_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    cols = ["match_id", "t_ms", "time_sec", "player_id", "player_name", "action_type", "event_type_semantic", "event_label"]
    if events_df.empty:
        empty = pd.DataFrame(columns=cols)
        return {
            "age_ups": empty.copy(),
            "units": empty.copy(),
            "buildings": empty.copy(),
            "techs": empty.copy(),
        }
    base = events_df[cols].copy()
    return {
        "age_ups": base[base["event_type_semantic"] == "age_up"].copy(),
        "units": base[base["event_type_semantic"] == "unit_train"].copy(),
        "buildings": base[base["event_type_semantic"] == "building_build"].copy(),
        "techs": base[base["event_type_semantic"] == "tech_research"].copy(),
    }


def build_parse_warnings(events_df: pd.DataFrame) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if events_df.empty:
        return [{"code": "W_PARSE_NO_EVENTS", "severity": "severe", "message": "No events extracted from replay."}]

    unknown = events_df[events_df["event_type_semantic"] == "other"]
    if not unknown.empty:
        top_unknown = unknown["action_type"].value_counts().head(5).to_dict()
        warnings.append(
            {
                "code": "W_PARSE_UNKNOWN_EVENT_TYPES",
                "severity": "medium",
                "message": "Some actions are still unclassified in semantic taxonomy.",
                "count": int(len(unknown)),
                "top_action_types": top_unknown,
            }
        )

    missing_players = events_df[events_df["player_id"] <= 0]
    if not missing_players.empty:
        warnings.append(
            {
                "code": "W_PARSE_MISSING_PLAYER_ID",
                "severity": "medium",
                "message": "Some events do not have valid player_id.",
                "count": int(len(missing_players)),
            }
        )
    return warnings


def extract_raw_snapshots(events_df: pd.DataFrame, window_sec: int = 10) -> pd.DataFrame:
    """Build canonical per-window state snapshots from raw events.

    Snapshot granularity is player x time-window and acts as a baseline
    `RawSnapshot` representation for downstream analytics.
    """
    cols = [
        "snapshot_id",
        "match_id",
        "time_bin_sec",
        "t_start_ms",
        "t_end_ms",
        "window_sec",
        "player_id",
        "player_name",
        "actions_total",
        "movement_count",
        "build_count",
        "production_count",
        "research_count",
        "economy_count",
        "military_count",
        "other_count",
        "x_mean",
        "y_mean",
        "spatial_event_count",
    ]
    if events_df.empty:
        return pd.DataFrame(columns=cols)

    w = max(1, int(window_sec))
    df = events_df.copy()
    df["time_bin_sec"] = (np.floor(df["time_sec"].astype(float) / w) * w).astype(int)
    grouped = (
        df.groupby(["match_id", "time_bin_sec", "player_id", "player_name"], dropna=False)
        .agg(
            actions_total=("event_id", "count"),
            movement_count=("action_family", lambda s: int((s == "movement").sum())),
            build_count=("action_family", lambda s: int((s == "build").sum())),
            production_count=("action_family", lambda s: int((s == "production").sum())),
            research_count=("action_family", lambda s: int((s == "research").sum())),
            economy_count=("action_family", lambda s: int((s == "economy").sum())),
            military_count=("action_family", lambda s: int((s == "military").sum())),
            other_count=("action_family", lambda s: int((s == "other").sum())),
            x_mean=("x", "mean"),
            y_mean=("y", "mean"),
            spatial_event_count=("x", lambda s: int(s.notna().sum())),
        )
        .reset_index()
        .sort_values(["time_bin_sec", "player_id", "player_name"])
        .reset_index(drop=True)
    )
    grouped["window_sec"] = w
    grouped["t_start_ms"] = grouped["time_bin_sec"].astype(int) * 1000
    grouped["t_end_ms"] = (grouped["time_bin_sec"].astype(int) + w) * 1000
    grouped["snapshot_id"] = np.arange(len(grouped), dtype=int)
    return grouped[cols]


def extract_event_views(events_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Convenience views for Part 2 extraction milestones."""
    cols = [
        "event_id",
        "match_id",
        "t_ms",
        "time_sec",
        "player_id",
        "player_name",
        "action_type",
        "action_family",
        "event_type_semantic",
        "event_label",
        "x",
        "y",
        "payload_json",
    ]
    if events_df.empty:
        empty = pd.DataFrame(columns=cols)
        return {
            "combat_events": empty.copy(),
            "economy_events": empty.copy(),
            "player_commands": empty.copy(),
            "spatial_events": empty.copy(),
        }

    base = events_df[cols].copy()
    combat_mask = (
        (base["action_family"] == "military")
        | (base["action_type"].astype(str).str.contains("ATTACK|PATROL|STANCE|FORMATION", case=False, regex=True))
    )
    economy_mask = base["action_family"] == "economy"
    spatial_mask = base["x"].notna() & base["y"].notna()
    player_cmd = base[base["player_id"].astype(int) > 0].copy()
    player_cmd["command_index"] = np.arange(len(player_cmd), dtype=int)
    return {
        "combat_events": base[combat_mask].copy(),
        "economy_events": base[economy_mask].copy(),
        "player_commands": player_cmd,
        "spatial_events": base[spatial_mask].copy(),
    }


def source_lib_version() -> str:
    direct = str(getattr(mgz, "__version__", "") or "").strip()
    if direct:
        return direct
    for pkg in ("mgz", "aoc-mgz"):
        try:
            return str(metadata.version(pkg))
        except Exception:
            continue
    return "unknown"


def extract_id_mappings(
    match,
    match_id: str,
    parser_version: str = "mvp",
    source_lib_version: str = "mgz",
) -> pd.DataFrame:
    """Extract (id -> human name) mappings observed in action payloads.

    This baseline mapping is replay-derived and version-tagged to support
    incremental patch-aware dictionaries later (P2-019 / P2-020).
    """
    pairs = [
        ("unit", "unit_id", "unit"),
        ("building", "building_id", "building"),
        ("technology", "technology_id", "technology"),
    ]
    patch_version = str(getattr(match, "version", "") or "")
    agg: dict[tuple[str, int, str], dict[str, Any]] = {}

    for act in match.actions:
        payload = getattr(act, "payload", {}) or {}
        if not isinstance(payload, dict):
            continue
        ts = getattr(act, "timestamp", None)
        t_ms = int(round(float(ts.total_seconds()) * 1000.0)) if ts is not None else 0
        for mapping_kind, id_key, name_key in pairs:
            raw_id = payload.get(id_key)
            raw_name = payload.get(name_key)
            try:
                internal_id = int(raw_id)
            except Exception:
                continue
            human_name = str(raw_name or "").strip()
            if not human_name:
                continue
            k = (mapping_kind, internal_id, human_name)
            if k not in agg:
                agg[k] = {"seen_count": 0, "first_t_ms": t_ms}
            agg[k]["seen_count"] += 1
            if t_ms < int(agg[k]["first_t_ms"]):
                agg[k]["first_t_ms"] = t_ms

    rows: list[dict[str, Any]] = []
    for (mapping_kind, internal_id, human_name), meta in sorted(agg.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        rows.append(
            {
                "match_id": match_id,
                "mapping_kind": mapping_kind,
                "internal_id": int(internal_id),
                "human_name": human_name,
                "seen_count": int(meta["seen_count"]),
                "first_t_ms": int(meta["first_t_ms"]),
                "patch_version": patch_version,
                "parser_version": str(parser_version),
                "source_lib_version": str(source_lib_version),
                "mapping_confidence": "observed_payload",
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "match_id",
                "mapping_kind",
                "internal_id",
                "human_name",
                "seen_count",
                "first_t_ms",
                "patch_version",
                "parser_version",
                "source_lib_version",
                "mapping_confidence",
            ]
        )
    return pd.DataFrame(rows)


def spatial_frames_from_events(
    events_df: pd.DataFrame,
    map_dimension: float,
    grid_size: int = 32,
    window_sec: int = 10,
) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(
            columns=[
                "match_id",
                "time_bin_sec",
                "window_sec",
                "grid_size",
                "player_id",
                "player_name",
                "action_family",
                "cell_x",
                "cell_y",
                "event_count",
            ]
        )
    df = events_df.copy()
    df = df[df["x"].notna() & df["y"].notna()]
    if df.empty:
        return pd.DataFrame(
            columns=[
                "match_id",
                "time_bin_sec",
                "window_sec",
                "grid_size",
                "player_id",
                "player_name",
                "action_family",
                "cell_x",
                "cell_y",
                "event_count",
            ]
        )

    d = float(map_dimension or 120.0)
    d = d if d > 0 else 120.0
    n = int(grid_size)
    w = int(window_sec)
    n = max(4, n)
    w = max(1, w)

    nx = np.floor((df["x"].astype(float) / d) * n).astype(int)
    ny = np.floor((df["y"].astype(float) / d) * n).astype(int)
    df["cell_x"] = np.clip(nx, 0, n - 1)
    df["cell_y"] = np.clip(ny, 0, n - 1)
    df["time_bin_sec"] = (np.floor(df["time_sec"].astype(float) / w) * w).astype(int)

    grouped = (
        df.groupby(
            [
                "match_id",
                "time_bin_sec",
                "player_id",
                "player_name",
                "action_family",
                "cell_x",
                "cell_y",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="event_count")
    )
    grouped["window_sec"] = w
    grouped["grid_size"] = n
    return grouped[
        [
            "match_id",
            "time_bin_sec",
            "window_sec",
            "grid_size",
            "player_id",
            "player_name",
            "action_family",
            "cell_x",
            "cell_y",
            "event_count",
        ]
    ]


def _to_parquet(df: pd.DataFrame, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(out, index=False, compression="snappy")
    except Exception as exc:
        raise RuntimeError(
            "Parquet export failed. Install 'pyarrow' or 'fastparquet' to enable parquet output."
        ) from exc


def export_events(
    events_df: pd.DataFrame,
    csv_path: str | Path | None = None,
    jsonl_path: str | Path | None = None,
    parquet_path: str | Path | None = None,
) -> None:
    if csv_path:
        out = Path(csv_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        events_df.to_csv(out, index=False)
    if jsonl_path:
        out = Path(jsonl_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for row in events_df.to_dict(orient="records"):
                fh.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")
    if parquet_path:
        _to_parquet(events_df, parquet_path)


def export_spatial_frames(
    spatial_df: pd.DataFrame,
    csv_path: str | Path | None = None,
    parquet_path: str | Path | None = None,
) -> None:
    if csv_path:
        out = Path(csv_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        spatial_df.to_csv(out, index=False)
    if parquet_path:
        _to_parquet(spatial_df, parquet_path)


def export_id_mappings(
    mapping_df: pd.DataFrame,
    csv_path: str | Path | None = None,
    jsonl_path: str | Path | None = None,
    parquet_path: str | Path | None = None,
) -> None:
    if csv_path:
        out = Path(csv_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        mapping_df.to_csv(out, index=False)
    if jsonl_path:
        out = Path(jsonl_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for row in mapping_df.to_dict(orient="records"):
                fh.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")
    if parquet_path:
        _to_parquet(mapping_df, parquet_path)


def export_raw_snapshots(
    snapshot_df: pd.DataFrame,
    csv_path: str | Path | None = None,
    jsonl_path: str | Path | None = None,
    parquet_path: str | Path | None = None,
) -> None:
    if csv_path:
        out = Path(csv_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        snapshot_df.to_csv(out, index=False)
    if jsonl_path:
        out = Path(jsonl_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for row in snapshot_df.to_dict(orient="records"):
                fh.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")
    if parquet_path:
        _to_parquet(snapshot_df, parquet_path)
