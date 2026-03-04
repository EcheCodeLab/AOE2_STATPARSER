from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import mgz.fast
import mgz.summary
import requests

from .core import load_match
from .pipeline import (
    build_parse_warnings,
    export_events,
    export_id_mappings,
    export_spatial_frames,
    extract_id_mappings,
    source_lib_version,
)
from .services import ReplayAnalysisService


@dataclass
class PlayerInfo:
    name: str
    civilization: int
    winner: bool
    eapm: int | None


@dataclass
class ReplaySummary:
    path: str
    version: Any
    duration_seconds: float
    map_id: int | None
    map_name: str
    players: list[PlayerInfo]
    parse_warnings: list[dict[str, Any]]


def _warn(code: str, severity: str, message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message}


def _compute_offsets(bundle) -> dict[str, Any]:
    events = bundle.events_raw
    if events is None or events.empty or "t_ms" not in events.columns:
        return {
            "start_offset_ms": 0,
            "end_offset_ms": 0,
            "event_start_ms": None,
            "event_end_ms": None,
            "expected_end_ms": int(float(bundle.match_meta.get("duration_sec", 0.0)) * 1000.0),
            "looks_incomplete": False,
        }
    event_start = int(events["t_ms"].min())
    event_end = int(events["t_ms"].max())
    expected_end = int(float(bundle.match_meta.get("duration_sec", 0.0)) * 1000.0)
    start_offset = max(0, event_start)
    end_offset = max(0, expected_end - event_end) if expected_end > 0 else 0
    return {
        "start_offset_ms": int(start_offset),
        "end_offset_ms": int(end_offset),
        "event_start_ms": int(event_start),
        "event_end_ms": int(event_end),
        "expected_end_ms": int(expected_end),
        "looks_incomplete": bool(end_offset > 10_000),
    }


class ParserLayer:
    """Parser layer: source replay IO and low-level extraction."""

    @staticmethod
    def download_replay(game_id: int, dest: str | Path | None = None) -> Path:
        if dest is None:
            dest = Path(f"AgeIIDE_Replay_{game_id}.aoe2record")
        else:
            dest = Path(dest)
        url = f"https://aoe.ms/replay/?gameId={game_id}"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        dest.write_bytes(response.content)
        return dest

    @staticmethod
    def parse_summary(path: str | Path) -> ReplaySummary:
        replay_path = Path(path)
        warnings: list[dict[str, Any]] = []
        players: list[PlayerInfo] = []
        version: Any = None
        map_id: int | None = None
        map_name = ""
        duration_seconds = 0.0
        summary_obj = None

        try:
            with replay_path.open("rb") as data:
                summary_obj = mgz.summary.Summary(data)
                player_dicts = summary_obj.get_players()
                players = [
                    PlayerInfo(
                        name=p["name"],
                        civilization=p["civilization"],
                        winner=p["winner"],
                        eapm=p.get("eapm"),
                    )
                    for p in player_dicts
                ]
                version = summary_obj.get_version()
                map_info = summary_obj.get_map()
                map_id = map_info.get("id")
                map_name = str(map_info.get("name") or "")
        except Exception as exc:
            warnings.append(_warn("W_SUMMARY_PARSE_FAILED", "severe", f"mgz.summary failed: {type(exc).__name__}: {exc}"))

        try:
            with replay_path.open("rb") as data:
                postgame = mgz.fast.postgame(data)
                duration_seconds = float(postgame.get("world_time", 0) or 0) / 1000.0
        except Exception as exc:
            warnings.append(_warn("W_POSTGAME_PARSE_FAILED", "medium", f"mgz.fast.postgame failed: {type(exc).__name__}: {exc}"))
            if summary_obj is not None:
                try:
                    duration_seconds = float(summary_obj.get_duration() or 0.0) / 1000.0
                except Exception:
                    duration_seconds = 0.0

        return ReplaySummary(
            path=str(replay_path),
            version=version,
            duration_seconds=duration_seconds,
            map_id=map_id,
            map_name=map_name,
            players=players,
            parse_warnings=warnings,
        )


class TransformLayer:
    """Transform layer: canonical datasets and derived features/validation."""

    def __init__(self) -> None:
        self._service = ReplayAnalysisService()

    def analyze(self, replay_path: str | Path, grid_size: int, window_sec: int):
        return self._service.analyze(replay_path=replay_path, grid_size=grid_size, window_sec=window_sec)

    @staticmethod
    def extract_id_mapping(replay_path: str | Path, match_id: str):
        match = load_match(replay_path)
        return extract_id_mappings(match, match_id=match_id)


class PresentationLayer:
    """Presentation layer: shape output payload and export artifacts."""

    @staticmethod
    def summary_to_payload(summary: ReplaySummary) -> dict[str, Any]:
        data = asdict(summary)
        return data

    @staticmethod
    def export_structured(
        bundle,
        events_csv: str | None,
        events_jsonl: str | None,
        events_parquet: str | None,
        spatial_csv: str | None,
        spatial_parquet: str | None,
        idmap_csv: str | None,
        idmap_jsonl: str | None,
        idmap_parquet: str | None,
        grid_size: int,
        window_sec: int,
        replay_path: str | Path,
    ) -> dict[str, Any]:
        meta = bundle.match_meta
        export_events(
            bundle.events_raw,
            csv_path=events_csv,
            jsonl_path=events_jsonl,
            parquet_path=events_parquet,
        )

        payload: dict[str, Any] = {
            "match_meta": meta,
            "parser_version": "mvp",
            "source_lib_version": source_lib_version(),
            "events_count": int(len(bundle.events_raw)),
            "events_csv": events_csv,
            "events_jsonl": events_jsonl,
            "events_parquet": events_parquet,
            "parse_warnings": build_parse_warnings(bundle.events_raw),
            "offsets": _compute_offsets(bundle),
            "features": bundle.features,
            "validation": bundle.validation,
        }

        if payload["offsets"]["looks_incomplete"]:
            payload["parse_warnings"].append(
                _warn(
                    "W_REPLAY_POSSIBLY_INCOMPLETE",
                    "medium",
                    f"Large end_offset_ms detected: {payload['offsets']['end_offset_ms']}",
                )
            )

        if spatial_csv or spatial_parquet:
            export_spatial_frames(
                bundle.spatial_frames,
                csv_path=spatial_csv,
                parquet_path=spatial_parquet,
            )
            payload["spatial_frames_count"] = int(len(bundle.spatial_frames))
            payload["spatial_csv"] = spatial_csv
            payload["spatial_parquet"] = spatial_parquet
            payload["grid_size"] = int(grid_size)
            payload["window_sec"] = int(window_sec)

        if idmap_csv or idmap_jsonl or idmap_parquet:
            mapping_df = TransformLayer.extract_id_mapping(
                replay_path=replay_path,
                match_id=str(meta.get("match_id", "")),
            )
            export_id_mappings(
                mapping_df,
                csv_path=idmap_csv,
                jsonl_path=idmap_jsonl,
                parquet_path=idmap_parquet,
            )
            payload["id_mapping_count"] = int(len(mapping_df))
            payload["id_mapping_kind_counts"] = (
                mapping_df["mapping_kind"].value_counts().to_dict() if not mapping_df.empty else {}
            )
            payload["idmap_csv"] = idmap_csv
            payload["idmap_jsonl"] = idmap_jsonl
            payload["idmap_parquet"] = idmap_parquet

        return payload


def dumps_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)
