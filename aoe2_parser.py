"""Simple Age of Empires II DE replay utilities.

This module allows downloading a replay (``.aoe2record``) from the
official Microsoft servers and extracting a small summary using the
`mgz` Python library.  It is intentionally small and heavily commented so
that people who are new to programming can follow the logic.

Typical usage from the command line::

    # Download a match by id and show a JSON summary
    python aoe2_parser.py --download 396581946

    # Or parse an existing file
    python aoe2_parser.py AgeIIDE_Replay_396581946.aoe2record

The :func:`parse_replay` function can also be imported and used inside a
Jupyter/Colab notebook to build plots or perform more advanced analysis.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Any, Optional, Union

import requests
import mgz.summary
import mgz.fast

from aoe2stat.core import load_match
from aoe2stat.pipeline import (
    build_match_meta,
    extract_raw_events,
    spatial_frames_from_events,
    export_events,
    export_spatial_frames,
)


@dataclass
class PlayerInfo:
    """Information extracted for a single player."""

    name: str
    civilization: int
    winner: bool
    eapm: Optional[int]


@dataclass
class ReplaySummary:
    """Top level information extracted from a replay."""

    path: Path
    version: Any
    duration_seconds: float
    map_id: int
    map_name: str
    players: List[PlayerInfo]


def download_replay(game_id: int, dest: Optional[Path] = None) -> Path:
    """Download a replay from the official servers.

    Parameters
    ----------
    game_id: Identifier of the match.
    dest: Optional path to save the file.
    """

    if dest is None:
        dest = Path(f"AgeIIDE_Replay_{game_id}.aoe2record")

    url = f"https://aoe.ms/replay/?gameId={game_id}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return dest


def parse_replay(path: Union[Path, str]) -> ReplaySummary:
    """Parse basic information from a ``.aoe2record`` file."""

    path = Path(path)

    with path.open('rb') as data:
        summary = mgz.summary.Summary(data)
        player_dicts = summary.get_players()
        players = [
            PlayerInfo(
                name=p['name'],
                civilization=p['civilization'],
                winner=p['winner'],
                eapm=p.get('eapm'),
            )
            for p in player_dicts
        ]
        version = summary.get_version()
        map_info = summary.get_map()
        map_id = map_info.get('id')
        map_name = map_info.get('name')

    with path.open('rb') as data:
        postgame = mgz.fast.postgame(data)
        duration_seconds = postgame.get('world_time', 0) / 1000

    return ReplaySummary(
        path=path,
        version=version,
        duration_seconds=duration_seconds,
        map_id=map_id,
        map_name=map_name,
        players=players,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse AoE2 DE replay")
    parser.add_argument(
        "replay",
        nargs="?",
        help="Path to a .aoe2record file to parse.  Not needed if --download is used.",
    )
    parser.add_argument(
        "--download",
        type=int,
        help="Download the given game id before parsing.",
    )
    parser.add_argument(
        "--export-events-csv",
        help="Export canonical raw events to CSV path.",
    )
    parser.add_argument(
        "--export-events-jsonl",
        help="Export canonical raw events to JSONL path.",
    )
    parser.add_argument(
        "--export-events-parquet",
        help="Export canonical raw events to Parquet path.",
    )
    parser.add_argument(
        "--export-spatial-csv",
        help="Export NxN spatial frames to CSV path.",
    )
    parser.add_argument(
        "--export-spatial-parquet",
        help="Export NxN spatial frames to Parquet path.",
    )
    parser.add_argument(
        "--grid-size",
        type=int,
        default=32,
        help="Grid resolution for spatial export (default: 32).",
    )
    parser.add_argument(
        "--window-sec",
        type=int,
        default=10,
        help="Window size in seconds for spatial export (default: 10).",
    )
    args = parser.parse_args()

    if args.download is not None:
        replay_path = download_replay(args.download)
    elif args.replay is not None:
        replay_path = Path(args.replay)
        if not replay_path.exists():
            raise SystemExit(f"File not found: {replay_path}")
    else:
        raise SystemExit("No replay file provided.")

    summary = parse_replay(replay_path)

    def to_dict(obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list):
            return [to_dict(x) for x in obj]
        return obj

    output: dict[str, Any] = {"summary": to_dict(summary)}

    wants_structured = bool(
        args.export_events_csv
        or args.export_events_jsonl
        or args.export_events_parquet
        or args.export_spatial_csv
        or args.export_spatial_parquet
    )
    if wants_structured:
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
            "events_count": int(len(events_df)),
            "events_csv": args.export_events_csv,
            "events_jsonl": args.export_events_jsonl,
            "events_parquet": args.export_events_parquet,
        }
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

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
