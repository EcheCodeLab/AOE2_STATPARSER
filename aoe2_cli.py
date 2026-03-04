"""Unified CLI for AoE2 replay parsing and inspection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aoe2stat.core import load_match
from aoe2stat.layers import ParserLayer
from aoe2stat.kpis import kpis_at_minute, kpis_by_window
from aoe2stat.metrics import apm_timeseries, tc_idle_time, villager_counts
from aoe2stat.patterns import base_unit_patterns
from aoe2stat.pipeline import (
    build_parse_warnings,
    build_match_meta,
    export_id_mappings,
    export_events,
    export_spatial_frames,
    extract_base_timelines,
    extract_id_mappings,
    extract_raw_events,
    source_lib_version,
    spatial_frames_from_events,
)

DEFAULT_SCHEMA_VERSION = "v1"
DEFAULT_PARSER_VERSION = "mvp"


def _warning(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _has_severe_warnings(warnings: list[dict[str, str]]) -> bool:
    return any(w.get("severity") == "severe" for w in warnings)


def _severe_warning_codes(warnings: list[dict[str, str]]) -> list[str]:
    return [w["code"] for w in warnings if w.get("severity") == "severe"]


def _error_code_from_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "FILE_NOT_FOUND"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, ValueError):
        return "VALUE_ERROR"
    if isinstance(exc, RuntimeError):
        return "RUNTIME_ERROR"
    return "PARSE_ERROR"


def _warnings_for_parse_output(data: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    players = summary.get("players", []) if isinstance(summary, dict) else []
    duration_seconds = summary.get("duration_seconds")
    map_name = summary.get("map_name")
    if not players:
        warnings.append(_warning("W_PARSE_NO_PLAYERS", "severe", "Replay parsed without players."))
    if isinstance(duration_seconds, (int, float)) and duration_seconds <= 0:
        warnings.append(_warning("W_PARSE_NONPOSITIVE_DURATION", "severe", "Replay duration is not positive."))
    if not map_name:
        warnings.append(_warning("W_PARSE_MISSING_MAP_NAME", "medium", "Map name is empty."))

    structured = data.get("structured", {}) if isinstance(data, dict) else {}
    if isinstance(structured, dict) and structured:
        events_count = int(structured.get("events_count", 0) or 0)
        if events_count <= 0:
            warnings.append(_warning("W_PARSE_NO_EVENTS", "severe", "Structured parse produced zero events."))
        if (
            ("spatial_csv" in structured or "spatial_parquet" in structured)
            and int(structured.get("spatial_frames_count", 0) or 0) <= 0
        ):
            warnings.append(_warning("W_PARSE_NO_SPATIAL_FRAMES", "medium", "Spatial export requested but no frames found."))
    return warnings


def _warnings_for_inspect_output(data: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    events_count = int(data.get("events_count", 0) or 0)
    if events_count <= 0:
        warnings.append(_warning("W_INSPECT_NO_EVENTS", "severe", "Inspect found zero events."))
    return warnings


def _warnings_for_metrics_output(data: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if not data.get("apm_avg"):
        warnings.append(_warning("W_METRICS_EMPTY_APM", "severe", "APM time series is empty."))
    if not data.get("villagers_created"):
        warnings.append(_warning("W_METRICS_EMPTY_VILLAGERS", "medium", "Villager creation metrics are empty."))
    return warnings


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return {k: _to_jsonable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    return obj


def _resolve_replay_path(replay: str | None, download: int | None) -> Path:
    if download is not None:
        return ParserLayer.download_replay(download)
    if replay:
        path = Path(replay)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        return path
    raise SystemExit("No replay file provided.")


def _add_replay_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("replay", nargs="?", help="Path to .aoe2record file.")
    parser.add_argument("--download", type=int, help="Download replay by game id.")


def _add_output_args(parser: argparse.ArgumentParser, hidden: bool = False) -> None:
    h = argparse.SUPPRESS if hidden else None
    parser.add_argument(
        "--json",
        choices=("compact", "detailed"),
        default="detailed",
        help=h or "JSON output format: compact or detailed (default: detailed).",
    )
    parser.add_argument(
        "--schema-version",
        default=DEFAULT_SCHEMA_VERSION,
        help=h or f"Schema version to include in output (default: {DEFAULT_SCHEMA_VERSION}).",
    )
    parser.add_argument(
        "--parser-version",
        default=DEFAULT_PARSER_VERSION,
        help=h or f"Parser version to include in output (default: {DEFAULT_PARSER_VERSION}).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=h or "Fail when severe warnings are detected.",
    )
    # Backward compatible alias kept for existing commands.
    parser.add_argument("--compact", action="store_true", help=argparse.SUPPRESS)


def cmd_parse(args: argparse.Namespace) -> dict[str, Any]:
    replay_path = _resolve_replay_path(args.replay, args.download)
    summary = ParserLayer.parse_summary(replay_path)
    output: dict[str, Any] = {"summary": _to_jsonable(summary)}

    wants_structured = bool(
        args.export_events_csv
        or args.export_events_jsonl
        or args.export_events_parquet
        or args.export_spatial_csv
        or args.export_spatial_parquet
        or args.export_idmap_csv
        or args.export_idmap_jsonl
        or args.export_idmap_parquet
    )
    if not wants_structured:
        return output

    match = load_match(replay_path)
    meta = build_match_meta(match, replay_path)
    events_df = extract_raw_events(match, match_id=meta.match_id)
    export_events(
        events_df,
        csv_path=args.export_events_csv,
        jsonl_path=args.export_events_jsonl,
        parquet_path=args.export_events_parquet,
    )
    output["structured"] = {
        "match_meta": meta.__dict__,
        "parser_version": str(args.parser_version),
        "source_lib_version": source_lib_version(),
        "events_count": int(len(events_df)),
        "events_csv": args.export_events_csv,
        "events_jsonl": args.export_events_jsonl,
        "events_parquet": args.export_events_parquet,
        "parse_warnings": build_parse_warnings(events_df),
    }
    if args.export_idmap_csv or args.export_idmap_jsonl or args.export_idmap_parquet:
        mapping_df = extract_id_mappings(
            match,
            match_id=meta.match_id,
            parser_version=str(args.parser_version),
            source_lib_version="mgz",
        )
        export_id_mappings(
            mapping_df,
            csv_path=args.export_idmap_csv,
            jsonl_path=args.export_idmap_jsonl,
            parquet_path=args.export_idmap_parquet,
        )
        output["structured"]["id_mapping_count"] = int(len(mapping_df))
        output["structured"]["id_mapping_kind_counts"] = (
            mapping_df["mapping_kind"].value_counts().to_dict() if not mapping_df.empty else {}
        )
        output["structured"]["idmap_csv"] = args.export_idmap_csv
        output["structured"]["idmap_jsonl"] = args.export_idmap_jsonl
        output["structured"]["idmap_parquet"] = args.export_idmap_parquet
    if args.export_spatial_csv or args.export_spatial_parquet:
        spatial_df = spatial_frames_from_events(
            events_df,
            map_dimension=meta.map_dimension,
            grid_size=args.grid_size,
            window_sec=args.window_sec,
        )
        export_spatial_frames(
            spatial_df,
            csv_path=args.export_spatial_csv,
            parquet_path=args.export_spatial_parquet,
        )
        output["structured"]["spatial_frames_count"] = int(len(spatial_df))
        output["structured"]["spatial_csv"] = args.export_spatial_csv
        output["structured"]["spatial_parquet"] = args.export_spatial_parquet
        output["structured"]["grid_size"] = int(args.grid_size)
        output["structured"]["window_sec"] = int(args.window_sec)
    return output


def cmd_inspect(args: argparse.Namespace) -> dict[str, Any]:
    replay_path = _resolve_replay_path(args.replay, args.download)
    match = load_match(replay_path)
    meta = build_match_meta(match, replay_path)
    events_df = extract_raw_events(match, match_id=meta.match_id)

    action_counts = (
        events_df["action_type"].value_counts().head(args.top).to_dict()
        if not events_df.empty
        else {}
    )
    family_counts = events_df["action_family"].value_counts().to_dict() if not events_df.empty else {}
    semantic_counts = events_df["event_type_semantic"].value_counts().to_dict() if ("event_type_semantic" in events_df.columns and not events_df.empty) else {}
    timelines = extract_base_timelines(events_df)
    id_mapping_df = extract_id_mappings(match, match_id=meta.match_id)
    id_mapping_kind_counts = id_mapping_df["mapping_kind"].value_counts().to_dict() if not id_mapping_df.empty else {}
    per_player_counts = (
        events_df.groupby(["player_id", "player_name"]).size().reset_index(name="events").to_dict(orient="records")
        if not events_df.empty
        else []
    )
    return {
        "match_meta": meta.__dict__,
        "events_count": int(len(events_df)),
        "action_type_top": action_counts,
        "action_family_counts": family_counts,
        "event_type_semantic_counts": semantic_counts,
        "timeline_counts": {
            "age_ups": int(len(timelines["age_ups"])),
            "units": int(len(timelines["units"])),
            "buildings": int(len(timelines["buildings"])),
            "techs": int(len(timelines["techs"])),
        },
        "timeline_samples": {
            "age_ups": timelines["age_ups"].head(5).to_dict(orient="records"),
            "units": timelines["units"].head(5).to_dict(orient="records"),
            "buildings": timelines["buildings"].head(5).to_dict(orient="records"),
            "techs": timelines["techs"].head(5).to_dict(orient="records"),
        },
        "id_mapping_count": int(len(id_mapping_df)),
        "id_mapping_kind_counts": id_mapping_kind_counts,
        "events_per_player": per_player_counts,
    }


def cmd_metrics(args: argparse.Namespace) -> dict[str, Any]:
    replay_path = _resolve_replay_path(args.replay, args.download)
    match = load_match(replay_path)
    villager_pattern = base_unit_patterns()["Villager"]

    apm_ts = apm_timeseries(match, window_sec=args.window_sec)
    villager_created = villager_counts(match, villager_pattern)
    tc_idle = tc_idle_time(match, villager_pattern)

    apm_avg: dict[str, float] = {}
    apm_peak: dict[str, float] = {}
    if not apm_ts.empty:
        for pid in apm_ts.columns:
            series = apm_ts[pid].astype(float)
            apm_avg[str(int(pid))] = float(series.mean())
            apm_peak[str(int(pid))] = float(series.max())

    kpi_window_df = kpis_by_window(match, window_sec=args.window_sec)
    kpi_at_min = kpis_at_minute(match, minute=args.minute, window_sec=args.window_sec)

    return {
        "window_sec": int(args.window_sec),
        "minute": int(args.minute),
        "players": [
            {
                "player_id": int(p.number),
                "player_name": str(p.name),
                "civilization": str(getattr(getattr(p, "civilization", None), "name", "") or ""),
            }
            for p in match.players
        ],
        "apm_avg": apm_avg,
        "apm_peak": apm_peak,
        "villagers_created": {str(k): int(v) for k, v in villager_created.items()},
        "tc_idle_sec": {str(k): float(v) for k, v in tc_idle.items()},
        "kpi_rows_window": int(len(kpi_window_df)),
        "kpis_at_minute": kpi_at_min,
    }


def _collect_batch_replays(paths: list[str], input_dir: str | None, glob_pattern: str) -> list[Path]:
    found: list[Path] = []
    for p in paths:
        candidate = Path(p)
        if candidate.exists():
            found.append(candidate)
    if input_dir:
        found.extend(sorted(Path(input_dir).glob(glob_pattern)))
    # Deduplicate while preserving order.
    unique: list[Path] = []
    seen: set[str] = set()
    for p in found:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def cmd_batch(args: argparse.Namespace) -> dict[str, Any]:
    replays = _collect_batch_replays(args.replays, args.input_dir, args.glob)
    if not replays:
        raise SystemExit("No replays found. Provide paths and/or --input-dir.")

    ok = 0
    failed = 0
    severe_warnings = 0
    error_summary: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    for replay_path in replays:
        try:
            summary = ParserLayer.parse_summary(replay_path)
            item = {
                "replay": str(replay_path),
                "ok": True,
                "duration_seconds": float(summary.duration_seconds),
                "players": len(summary.players),
            }
            item_warnings = _warnings_for_parse_output({"summary": _to_jsonable(summary)})
            if item_warnings:
                item["warnings"] = item_warnings
            if args.strict and _has_severe_warnings(item_warnings):
                severe_warnings += 1
                item["ok"] = False
                item["error_code"] = "STRICT_SEVERE_WARNING"
                item["error"] = "Strict mode failed due to severe warnings."
                failed += 1
                error_summary["STRICT_SEVERE_WARNING"] = error_summary.get("STRICT_SEVERE_WARNING", 0) + 1
                if not args.continue_on_error:
                    items.append(item)
                    break
            else:
                ok += 1
            items.append(item)
        except Exception as exc:
            failed += 1
            error_code = _error_code_from_exception(exc)
            error_summary[error_code] = error_summary.get(error_code, 0) + 1
            items.append(
                {
                    "replay": str(replay_path),
                    "ok": False,
                    "error_code": error_code,
                    "error": str(exc),
                }
            )
            if not args.continue_on_error:
                break
    return {
        "total": len(items),
        "ok": ok,
        "failed": failed,
        "strict_failed": bool(args.strict and severe_warnings > 0),
        "items": items,
        "error_summary": error_summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aoe2_cli",
        description="Unified AoE2 replay CLI with subcommands: parse, metrics, batch, inspect.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    parse_p = sub.add_parser("parse", help="Parse one replay and optionally export structured outputs.")
    _add_replay_args(parse_p)
    parse_p.add_argument("--export-events-csv")
    parse_p.add_argument("--export-events-jsonl")
    parse_p.add_argument("--export-events-parquet")
    parse_p.add_argument("--export-spatial-csv")
    parse_p.add_argument("--export-spatial-parquet")
    parse_p.add_argument("--export-idmap-csv")
    parse_p.add_argument("--export-idmap-jsonl")
    parse_p.add_argument("--export-idmap-parquet")
    parse_p.add_argument("--grid-size", type=int, default=32)
    parse_p.add_argument("--window-sec", type=int, default=10)
    _add_output_args(parse_p, hidden=True)
    parse_p.set_defaults(func=cmd_parse)

    metrics_p = sub.add_parser("metrics", help="Compute core metrics for one replay.")
    _add_replay_args(metrics_p)
    metrics_p.add_argument("--window-sec", type=int, default=30)
    metrics_p.add_argument("--minute", type=int, default=20, help="Minute N for cumulative KPI snapshot.")
    _add_output_args(metrics_p, hidden=True)
    metrics_p.set_defaults(func=cmd_metrics)

    inspect_p = sub.add_parser("inspect", help="Inspect canonical events and action distribution.")
    _add_replay_args(inspect_p)
    inspect_p.add_argument("--top", type=int, default=15, help="Top N action types to return.")
    _add_output_args(inspect_p, hidden=True)
    inspect_p.set_defaults(func=cmd_inspect)

    batch_p = sub.add_parser("batch", help="Run parse summary over multiple replay files.")
    batch_p.add_argument("replays", nargs="*", help="Replay file paths.")
    batch_p.add_argument("--input-dir", help="Directory to scan for replay files.")
    batch_p.add_argument("--glob", default="*.aoe2record", help="Glob pattern used with --input-dir.")
    batch_p.add_argument("--continue-on-error", action="store_true", help="Continue when one replay fails.")
    _add_output_args(batch_p, hidden=True)
    batch_p.set_defaults(func=cmd_batch)

    _add_output_args(parser, hidden=False)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    payload = args.func(args)
    warnings: list[dict[str, str]] = []
    if args.command == "parse":
        warnings = _warnings_for_parse_output(payload)
    elif args.command == "inspect":
        warnings = _warnings_for_inspect_output(payload)
    elif args.command == "metrics":
        warnings = _warnings_for_metrics_output(payload)

    strict_failed = False
    if args.command == "batch":
        strict_failed = bool(payload.get("strict_failed", False))
    elif args.strict and _has_severe_warnings(warnings):
        strict_failed = True

    result: dict[str, Any] = {
        "meta": {
            "command": str(args.command),
            "schema_version": str(args.schema_version),
            "parser_version": str(args.parser_version),
            "output_json": "compact" if args.compact else str(args.json),
            "strict": bool(args.strict),
            "strict_failed": strict_failed,
        },
        "data": payload,
    }
    if warnings:
        result["warnings"] = warnings

    json_mode = "compact" if args.compact else str(args.json)
    if json_mode == "compact":
        print(json.dumps(result, default=str, separators=(",", ":")))
    else:
        print(json.dumps(result, indent=2, default=str))

    if strict_failed:
        if args.command == "batch":
            raise SystemExit("Strict mode failed: severe warnings found in batch items.")
        codes = ",".join(_severe_warning_codes(warnings))
        raise SystemExit(f"Strict mode failed due to severe warnings: {codes}")


if __name__ == "__main__":
    main()
