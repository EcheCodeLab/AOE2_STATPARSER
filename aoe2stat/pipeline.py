from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class MatchMeta:
    match_id: str
    replay_path: str
    duration_sec: float
    map_name: str
    map_dimension: float
    players: list[dict[str, Any]]


def build_match_meta(match, replay_path: str | Path) -> MatchMeta:
    rp = Path(replay_path)
    players = []
    for p in match.players:
        players.append(
            {
                "player_id": int(getattr(p, "number", 0)),
                "player_name": str(getattr(p, "name", "")),
                "civilization": str(getattr(getattr(p, "civilization", None), "name", "") or ""),
                "color_id": int(getattr(p, "color_id", 0) or 0),
            }
        )
    return MatchMeta(
        match_id=rp.stem,
        replay_path=str(rp),
        duration_sec=float(match.duration.total_seconds()),
        map_name=str(getattr(match.map, "name", "") or ""),
        map_dimension=float(getattr(match.map, "dimension", 120) or 120),
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
                "x",
                "y",
                "payload_json",
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


def export_events(events_df: pd.DataFrame, csv_path: str | Path | None = None, jsonl_path: str | Path | None = None) -> None:
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


def export_spatial_frames(spatial_df: pd.DataFrame, csv_path: str | Path) -> None:
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    spatial_df.to_csv(out, index=False)
