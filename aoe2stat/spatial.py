from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .pipeline import spatial_frames_from_events

SPATIAL_CHANNELS_V1 = ["own_units", "enemy_units", "buildings", "combat", "risk_proxy"]


def build_spatial_frames(
    events_raw: pd.DataFrame,
    map_dimension: float,
    grid_size: int,
    window_sec: int,
) -> pd.DataFrame:
    return spatial_frames_from_events(
        events_raw,
        map_dimension=map_dimension,
        grid_size=grid_size,
        window_sec=window_sec,
    )


def normalize_coordinates(events_raw: pd.DataFrame, map_dimension: float) -> pd.DataFrame:
    """Normalize x/y to [0,1] using the shared AoE2 map dimension."""
    out = events_raw.copy()
    if out.empty:
        out["x_norm"] = pd.Series(dtype=float)
        out["y_norm"] = pd.Series(dtype=float)
        return out
    d = float(map_dimension or 120.0)
    if d <= 0:
        d = 120.0
    out["x_norm"] = (out["x"].astype(float) / d).clip(0.0, 1.0)
    out["y_norm"] = (out["y"].astype(float) / d).clip(0.0, 1.0)
    return out


def _to_cell_index(norm: pd.Series, grid_size: int) -> pd.Series:
    n = max(4, int(grid_size))
    cells = np.floor(norm.astype(float) * n).astype(int)
    return cells.clip(0, n - 1)


def _military_mask(df: pd.DataFrame) -> pd.Series:
    if "action_family" in df.columns:
        return df["action_family"].astype(str).str.lower().eq("military")
    if "action_type" in df.columns:
        return df["action_type"].astype(str).str.contains("ATTACK|PATROL|STANCE|FORMATION|SPECIAL", case=False, regex=True)
    return pd.Series(False, index=df.index)


def _building_mask(df: pd.DataFrame) -> pd.Series:
    if "event_type_semantic" in df.columns:
        return df["event_type_semantic"].astype(str).str.lower().eq("building_build")
    if "action_type" in df.columns:
        return df["action_type"].astype(str).str.upper().isin(["BUILD", "WALL"])
    return pd.Series(False, index=df.index)


def _unit_mask(df: pd.DataFrame) -> pd.Series:
    if "event_type_semantic" in df.columns:
        return df["event_type_semantic"].astype(str).str.lower().eq("unit_train")
    if "action_family" in df.columns:
        return df["action_family"].astype(str).str.lower().eq("production")
    return pd.Series(False, index=df.index)


def _risk_proxy(enemy_grid: np.ndarray) -> np.ndarray:
    up = np.roll(enemy_grid, -1, axis=0)
    down = np.roll(enemy_grid, 1, axis=0)
    left = np.roll(enemy_grid, -1, axis=1)
    right = np.roll(enemy_grid, 1, axis=1)
    up[-1, :] = 0.0
    down[0, :] = 0.0
    left[:, -1] = 0.0
    right[:, 0] = 0.0
    return enemy_grid + 0.5 * (up + down + left + right)


def build_perspective_spatial_frames(
    events_raw: pd.DataFrame,
    map_dimension: float,
    grid_size: int = 32,
    window_sec: int = 10,
) -> pd.DataFrame:
    """Build per-player spatial channels over time bins.

    Output schema is Parquet/NPZ friendly:
    match_id, player_id, time_bin_sec, grid_size, window_sec, channel, cell_x, cell_y, value.
    """
    cols = [
        "match_id",
        "player_id",
        "time_bin_sec",
        "grid_size",
        "window_sec",
        "channel",
        "cell_x",
        "cell_y",
        "value",
    ]
    if events_raw.empty:
        return pd.DataFrame(columns=cols)

    n = max(4, int(grid_size))
    w = max(1, int(window_sec))
    df = normalize_coordinates(events_raw, map_dimension=map_dimension)
    df = df[df["x_norm"].notna() & df["y_norm"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=cols)

    df["cell_x"] = _to_cell_index(df["x_norm"], n)
    df["cell_y"] = _to_cell_index(df["y_norm"], n)
    df["time_bin_sec"] = (np.floor(df["time_sec"].astype(float) / w) * w).astype(int)
    df["is_unit"] = _unit_mask(df)
    df["is_building"] = _building_mask(df)
    df["is_combat"] = _military_mask(df)

    match_id = str(df["match_id"].iloc[0]) if "match_id" in df.columns else "unknown_match"
    player_ids = sorted([int(p) for p in df["player_id"].dropna().unique().tolist() if int(p) > 0])
    time_bins = sorted(df["time_bin_sec"].unique().tolist())

    out_rows: list[dict[str, Any]] = []
    for pid in player_ids:
        own = df[df["player_id"] == pid]
        enemy = df[df["player_id"] != pid]
        for t in time_bins:
            own_t = own[own["time_bin_sec"] == t]
            enemy_t = enemy[enemy["time_bin_sec"] == t]
            all_t = df[df["time_bin_sec"] == t]

            own_grid = np.zeros((n, n), dtype=float)
            enemy_grid = np.zeros((n, n), dtype=float)
            building_grid = np.zeros((n, n), dtype=float)
            combat_grid = np.zeros((n, n), dtype=float)

            for row in own_t[own_t["is_unit"]].itertuples(index=False):
                own_grid[int(row.cell_y), int(row.cell_x)] += 1.0
            for row in enemy_t[enemy_t["is_unit"]].itertuples(index=False):
                enemy_grid[int(row.cell_y), int(row.cell_x)] += 1.0
            for row in all_t[all_t["is_building"]].itertuples(index=False):
                building_grid[int(row.cell_y), int(row.cell_x)] += 1.0
            for row in all_t[all_t["is_combat"]].itertuples(index=False):
                combat_grid[int(row.cell_y), int(row.cell_x)] += 1.0

            risk_grid = _risk_proxy(enemy_grid)
            channel_to_grid = {
                "own_units": own_grid,
                "enemy_units": enemy_grid,
                "buildings": building_grid,
                "combat": combat_grid,
                "risk_proxy": risk_grid,
            }

            for channel, grid in channel_to_grid.items():
                ys, xs = np.nonzero(grid > 0)
                for y, x in zip(ys.tolist(), xs.tolist()):
                    out_rows.append(
                        {
                            "match_id": match_id,
                            "player_id": int(pid),
                            "time_bin_sec": int(t),
                            "grid_size": int(n),
                            "window_sec": int(w),
                            "channel": channel,
                            "cell_x": int(x),
                            "cell_y": int(y),
                            "value": float(grid[y, x]),
                        }
                    )

    if not out_rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(out_rows, columns=cols)


def overlay_player_layers(
    perspective_frames: pd.DataFrame,
    player_a: int,
    player_b: int,
    channel: str = "own_units",
    time_bin_sec: int | None = None,
) -> pd.DataFrame:
    """Return two separated layers (A/B) for comparison on same grid/time."""
    if perspective_frames.empty:
        return pd.DataFrame(columns=["layer", "player_id", "time_bin_sec", "cell_x", "cell_y", "value"])
    df = perspective_frames[perspective_frames["channel"] == channel].copy()
    if time_bin_sec is not None:
        df = df[df["time_bin_sec"] == int(time_bin_sec)]
    a = df[df["player_id"] == int(player_a)].copy()
    b = df[df["player_id"] == int(player_b)].copy()
    a["layer"] = "A"
    b["layer"] = "B"
    out = pd.concat([a, b], ignore_index=True)
    return out[["layer", "player_id", "time_bin_sec", "cell_x", "cell_y", "value"]]


def spatial_frames_to_tensor(
    perspective_frames: pd.DataFrame,
    player_id: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Dense tensor [T, C, H, W] for one player from perspective frames."""
    if perspective_frames.empty:
        return np.zeros((0, len(SPATIAL_CHANNELS_V1), 0, 0), dtype=np.float32), {
            "time_bins": [],
            "channels": list(SPATIAL_CHANNELS_V1),
            "grid_size": 0,
            "player_id": int(player_id),
        }
    df = perspective_frames[perspective_frames["player_id"] == int(player_id)].copy()
    if df.empty:
        n = int(perspective_frames["grid_size"].iloc[0])
        return np.zeros((0, len(SPATIAL_CHANNELS_V1), n, n), dtype=np.float32), {
            "time_bins": [],
            "channels": list(SPATIAL_CHANNELS_V1),
            "grid_size": n,
            "player_id": int(player_id),
        }

    n = int(df["grid_size"].iloc[0])
    time_bins = sorted(df["time_bin_sec"].unique().tolist())
    channel_index = {c: i for i, c in enumerate(SPATIAL_CHANNELS_V1)}
    tensor = np.zeros((len(time_bins), len(SPATIAL_CHANNELS_V1), n, n), dtype=np.float32)
    t_index = {t: i for i, t in enumerate(time_bins)}
    for r in df.itertuples(index=False):
        ci = channel_index.get(str(r.channel))
        if ci is None:
            continue
        ti = t_index[int(r.time_bin_sec)]
        y = int(r.cell_y)
        x = int(r.cell_x)
        if 0 <= y < n and 0 <= x < n:
            tensor[ti, ci, y, x] = float(r.value)
    meta = {
        "time_bins": time_bins,
        "channels": list(SPATIAL_CHANNELS_V1),
        "grid_size": n,
        "player_id": int(player_id),
    }
    return tensor, meta


def export_spatial_tensor_npz(
    perspective_frames: pd.DataFrame,
    player_id: int,
    output_path: str | Path,
) -> None:
    tensor, meta = spatial_frames_to_tensor(perspective_frames, player_id=player_id)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        tensor=tensor,
        time_bins=np.array(meta["time_bins"], dtype=np.int32),
        channels=np.array(meta["channels"], dtype=object),
        grid_size=np.array([meta["grid_size"]], dtype=np.int32),
        player_id=np.array([meta["player_id"]], dtype=np.int32),
    )
