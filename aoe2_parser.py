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

    print(json.dumps(to_dict(summary), indent=2, default=str))


if __name__ == "__main__":
    main()
