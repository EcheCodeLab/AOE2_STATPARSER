from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aoe2stat.core import load_match
from aoe2stat.pipeline import extract_raw_events


@dataclass
class ReplaySession:
    replay_path: Path
    match: Any
    events_df: pd.DataFrame
    resources_df: pd.DataFrame | None
    key_objects_df: pd.DataFrame | None
    build_events_df: pd.DataFrame | None
    delete_events_df: pd.DataFrame | None
    event_log_df: pd.DataFrame | None
    duration_sec: float
    map_dimension: float
    players: list[dict[str, Any]]


class SessionCreateRequest(BaseModel):
    replay_path: str


def _fmt_time(sec: float) -> str:
    s = max(0, int(round(float(sec))))
    return f"{s // 60}:{s % 60:02d}"


def _player_team_map(match) -> dict[int, int]:
    out: dict[int, int] = {}
    for p in match.players:
        pid = int(getattr(p, "number", 0) or 0)
        team_raw = getattr(p, "team_id", None)
        team_id = pid
        if isinstance(team_raw, (list, tuple)) and len(team_raw) > 0:
            team_id = int(team_raw[0])
        elif team_raw is not None:
            try:
                team_id = int(team_raw)
            except Exception:
                team_id = pid
        out[pid] = team_id
    return out


def _heat_from_cells(gx: np.ndarray, gy: np.ndarray, grid_size: int, weights: np.ndarray | None = None) -> np.ndarray:
    heat = np.zeros((grid_size, grid_size), dtype=float)
    if len(gx) == 0:
        return heat
    if weights is None:
        for cx, cy in zip(gx, gy):
            heat[grid_size - 1 - int(cy), int(cx)] += 1.0
        return heat
    for cx, cy, w in zip(gx, gy, weights):
        heat[grid_size - 1 - int(cy), int(cx)] += float(w)
    return heat


def _extract_initial_tcs(match) -> pd.DataFrame | None:
    rows = []
    team_map = _player_team_map(match)
    for p in match.players:
        pid = int(getattr(p, "number", 0) or 0)
        pname = str(getattr(p, "name", "") or "")
        team_id = int(team_map.get(pid, pid))
        objs = list(getattr(p, "objects", []) or [])
        for o in objs:
            name = str(getattr(o, "name", "") or "").strip().lower()
            if name != "town center":
                continue
            pos = getattr(o, "position", None)
            if pos is None:
                continue
            x = float(getattr(pos, "x", np.nan))
            y = float(getattr(pos, "y", np.nan))
            if not np.isfinite(x) or not np.isfinite(y):
                continue
            rows.append((0.0, pid, pname, team_id, x, y, "tc_initial"))
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["time_sec", "player_id", "player_name", "team_id", "x", "y", "object_kind"])
    df["x_round"] = df["x"].round(1)
    df["y_round"] = df["y"].round(1)
    df = df.drop_duplicates(subset=["player_id", "object_kind", "x_round", "y_round"], keep="first")
    return df[["time_sec", "player_id", "player_name", "team_id", "x", "y", "object_kind"]]


def _extract_key_objects(events_df: pd.DataFrame, match) -> pd.DataFrame | None:
    frames = []
    if events_df is not None and not events_df.empty and "payload_json" in events_df.columns:
        base = events_df[
            (events_df["action_type"] == "BUILD")
            & events_df["x"].notna()
            & events_df["y"].notna()
            & events_df["player_id"].notna()
        ].copy()
        if not base.empty:
            payload_lower = base["payload_json"].astype(str).str.lower()
            is_tc = payload_lower.str.contains("town center", regex=False) | payload_lower.str.contains("centro urbano", regex=False)
            is_castle = payload_lower.str.contains("castle", regex=False) | payload_lower.str.contains("castillo", regex=False)
            key = base[is_tc | is_castle].copy()
            if not key.empty:
                key["object_kind"] = np.where((is_tc[is_tc | is_castle]).to_numpy(), "tc", "castle")
                key["x_round"] = key["x"].astype(float).round(1)
                key["y_round"] = key["y"].astype(float).round(1)
                key["t_round"] = key["time_sec"].astype(float).round(1)
                key = key.drop_duplicates(subset=["player_id", "object_kind", "x_round", "y_round", "t_round"], keep="first")
                team_map = _player_team_map(match)
                key["team_id"] = key["player_id"].map(lambda pid: team_map.get(int(pid), int(pid)))
                frames.append(key[["time_sec", "player_id", "player_name", "team_id", "x", "y", "object_kind"]].copy())
    init_tc = _extract_initial_tcs(match)
    if init_tc is not None and not init_tc.empty:
        frames.append(init_tc.copy())
    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values("time_sec")


def _extract_building_events(events_df: pd.DataFrame, match) -> pd.DataFrame | None:
    if events_df is None or events_df.empty:
        return None
    build_semantic = {"building_build", "build_command"}
    base = events_df[
        (
            (events_df["action_type"].astype(str).str.upper() == "BUILD")
            | (events_df["action_family"].astype(str) == "build")
            | (events_df["event_type_semantic"].astype(str).isin(build_semantic))
        )
        & events_df["x"].notna()
        & events_df["y"].notna()
    ].copy()
    if base.empty:
        return None

    def _building_name(payload_json: str, fallback_label: str) -> str:
        try:
            payload = json.loads(str(payload_json))
            for key in ("building", "building_name", "object", "object_name", "unit", "unit_name", "structure"):
                val = str(payload.get(key, "") or "").strip()
                if val:
                    return val.lower()
        except Exception:
            pass
        return str(fallback_label or "").strip().lower()

    base["building_name"] = [
        _building_name(payload_json, fallback_label)
        for payload_json, fallback_label in zip(
            base["payload_json"].astype(str).tolist(),
            base["event_label"].astype(str).tolist(),
        )
    ]
    base = base[base["building_name"] != ""]
    if base.empty:
        return None
    team_map = _player_team_map(match)
    base["team_id"] = base["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid)))
    return base[["time_sec", "player_id", "player_name", "team_id", "x", "y", "building_name"]].sort_values("time_sec")


def _extract_delete_events(events_df: pd.DataFrame, match) -> pd.DataFrame | None:
    if events_df is None or events_df.empty:
        return None
    out = events_df[(events_df["action_type"] == "DELETE") & events_df["x"].notna() & events_df["y"].notna()].copy()
    if out.empty:
        return None
    team_map = _player_team_map(match)
    out["team_id"] = out["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid)))
    return out[["time_sec", "player_id", "player_name", "team_id", "x", "y"]].sort_values("time_sec")


def _extract_gaia_resources(match) -> pd.DataFrame | None:
    gaia = getattr(match, "gaia", None)
    if not gaia:
        return None
    gold_ids = {66}
    stone_ids = {102, 69}
    wood_class_ids = {10, 20}
    food_class_ids = {70}
    rows = []
    for obj in gaia:
        pos = getattr(obj, "position", None)
        if pos is None:
            continue
        x = float(getattr(pos, "x", np.nan))
        y = float(getattr(pos, "y", np.nan))
        if not np.isfinite(x) or not np.isfinite(y):
            continue
        oid = int(getattr(obj, "object_id", 0) or 0)
        cid = int(getattr(obj, "class_id", 0) or 0)
        rtype = None
        if oid in gold_ids:
            rtype = "gold"
        elif oid in stone_ids:
            rtype = "stone"
        elif cid in wood_class_ids:
            rtype = "wood"
        elif cid in food_class_ids:
            rtype = "food"
        if rtype is None:
            continue
        rows.append((x, y, oid, cid, rtype))
    if not rows:
        return None
    return pd.DataFrame(rows, columns=["x", "y", "object_id", "class_id", "resource_type"])


def _build_event_log(events_df: pd.DataFrame, match) -> pd.DataFrame | None:
    if events_df is None or events_df.empty:
        return None
    rows: list[dict[str, object]] = []
    df = events_df.sort_values("time_sec")
    for _, r in df.iterrows():
        t = float(r.get("time_sec", 0.0))
        a = str(r.get("action_type", "") or "")
        pname = str(r.get("player_name", "") or "")
        if a not in {"BUILD", "DELETE", "RESEARCH", "DE_ATTACK_MOVE", "PATROL", "TRAIN", "QUEUE"}:
            continue
        detail = ""
        try:
            p = json.loads(str(r.get("payload_json", "{}")))
            if a == "BUILD":
                detail = str(p.get("building", "") or "")
            elif a == "RESEARCH":
                detail = str(p.get("technology", "") or p.get("tech", "") or "")
            elif a in {"TRAIN", "QUEUE"}:
                detail = str(p.get("unit", "") or p.get("object", "") or "")
        except Exception:
            detail = ""
        rows.append({"time_sec": t, "time_txt": _fmt_time(t), "player": pname or "N/A", "event": a, "detail": detail or ""})
    if not rows:
        return None
    out = pd.DataFrame(rows).sort_values("time_sec")
    out = out.drop_duplicates(subset=["time_sec", "player", "event", "detail"], keep="first")
    return out


def _building_heat_from_frames(bdf, ddf, t: float, grid_size: int, map_dim: float) -> np.ndarray:
    heat = np.zeros((grid_size, grid_size), dtype=float)
    if bdf is None or bdf.empty:
        return heat
    b_gx = np.floor((bdf["x"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
    b_gy = np.floor((bdf["y"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
    build_h = _heat_from_cells(b_gx, b_gy, grid_size)
    if ddf is None or ddf.empty:
        return build_h
    del_df = ddf[ddf["time_sec"] <= t]
    if del_df.empty:
        return build_h
    d_gx = np.floor((del_df["x"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
    d_gy = np.floor((del_df["y"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
    del_h = _heat_from_cells(d_gx, d_gy, grid_size)
    return np.maximum(0.0, build_h - del_h)


def _building_heat_persistent(session: ReplaySession, t: float, grid_size: int, selected_player: str, layer: str) -> np.ndarray:
    heat = np.zeros((grid_size, grid_size), dtype=float)
    bdf = session.build_events_df
    if bdf is None or bdf.empty:
        return heat
    bdf = bdf[bdf["time_sec"] <= t].copy()
    if bdf.empty:
        return heat
    ddf = session.delete_events_df
    team_map = _player_team_map(session.match)
    team_ref = None
    if selected_player != "Todos":
        for p in session.match.players:
            if str(p.name) == selected_player:
                team_ref = int(team_map.get(int(p.number), int(p.number)))
                break
    if selected_player != "Todos" and layer in ("Actividad", "Edificios"):
        bdf = bdf[bdf["player_name"] == selected_player]
        if ddf is not None and not ddf.empty:
            ddf = ddf[(ddf["time_sec"] <= t) & (ddf["player_name"] == selected_player)]
    elif layer in ("Propio", "Enemigo", "Presión"):
        if team_ref is None:
            return heat
        if layer == "Propio":
            bdf = bdf[bdf["team_id"].astype(int) == int(team_ref)]
        elif layer == "Enemigo":
            bdf = bdf[bdf["team_id"].astype(int) != int(team_ref)]
        else:
            own = bdf[bdf["team_id"].astype(int) == int(team_ref)]
            enemy = bdf[bdf["team_id"].astype(int) != int(team_ref)]
            own_h = _building_heat_from_frames(own, ddf, t, grid_size, session.map_dimension)
            enemy_h = _building_heat_from_frames(enemy, ddf, t, grid_size, session.map_dimension)
            return enemy_h - own_h
        if ddf is not None and not ddf.empty:
            if layer == "Propio":
                ddf = ddf[(ddf["time_sec"] <= t) & (ddf["team_id"].astype(int) == int(team_ref))]
            elif layer == "Enemigo":
                ddf = ddf[(ddf["time_sec"] <= t) & (ddf["team_id"].astype(int) != int(team_ref))]
            else:
                ddf = ddf[ddf["time_sec"] <= t]
    else:
        if ddf is not None and not ddf.empty:
            ddf = ddf[ddf["time_sec"] <= t]
    return _building_heat_from_frames(bdf, ddf, t, grid_size, session.map_dimension)


app = FastAPI(title="AOE2 Web Analytics")
_sessions: dict[str, ReplaySession] = {}

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/session")
def create_session(req: SessionCreateRequest) -> dict[str, Any]:
    replay_path = Path(req.replay_path).expanduser().resolve()
    if not replay_path.exists():
        raise HTTPException(status_code=404, detail=f"Replay not found: {replay_path}")
    match = load_match(str(replay_path))
    events_df = extract_raw_events(match, match_id=replay_path.stem)
    resources_df = _extract_gaia_resources(match)
    key_objects_df = _extract_key_objects(events_df, match)
    build_events_df = _extract_building_events(events_df, match)
    delete_events_df = _extract_delete_events(events_df, match)
    event_log_df = _build_event_log(events_df, match)
    session_id = str(uuid.uuid4())
    players = []
    team_map = _player_team_map(match)
    for p in match.players:
        pid = int(getattr(p, "number", 0) or 0)
        players.append(
            {
                "player_id": pid,
                "player_name": str(getattr(p, "name", "") or ""),
                "team_id": int(team_map.get(pid, pid)),
                "color_id": int(getattr(p, "color_id", 0) or 0),
            }
        )
    duration_sec = float(match.duration.total_seconds())
    map_dimension = float(getattr(match.map, "dimension", 120) or 120)
    _sessions[session_id] = ReplaySession(
        replay_path=replay_path,
        match=match,
        events_df=events_df,
        resources_df=resources_df,
        key_objects_df=key_objects_df,
        build_events_df=build_events_df,
        delete_events_df=delete_events_df,
        event_log_df=event_log_df,
        duration_sec=duration_sec,
        map_dimension=map_dimension if map_dimension > 0 else 120.0,
        players=players,
    )
    return {
        "session_id": session_id,
        "replay_path": str(replay_path),
        "duration_sec": duration_sec,
        "map_dimension": map_dimension,
        "players": players,
    }


@app.get("/api/session/{session_id}/frame")
def get_frame(
    session_id: str,
    t: float = 0.0,
    window_sec: int = 20,
    grid_size: int = 128,
    layer: str = "Actividad",
    player_name: str = "Todos",
    action_family: str = "Todos",
    show_resources: bool = True,
    show_key_objects: bool = True,
    show_pulses: bool = True,
    show_buildings: bool = True,
    show_building_markers: bool = True,
    show_units: bool = True,
    log_window_sec: int = 120,
) -> dict[str, Any]:
    s = _sessions.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    t = float(max(0.0, min(float(t), s.duration_sec)))
    window_sec = max(1, int(window_sec))
    grid_size = max(16, min(256, int(grid_size)))
    t0 = max(0.0, t - float(window_sec))

    df_window = s.events_df
    df_window = df_window[(df_window["time_sec"] >= t0) & (df_window["time_sec"] <= t)]
    df_window = df_window[df_window["x"].notna() & df_window["y"].notna()]
    if action_family != "Todos":
        df_window = df_window[df_window["action_family"] == action_family]
    if df_window.empty:
        gx_all = np.array([], dtype=int)
        gy_all = np.array([], dtype=int)
        team_series = np.array([], dtype=int)
        movement_mask = np.array([], dtype=bool)
    else:
        gx_all = np.floor((df_window["x"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        gy_all = np.floor((df_window["y"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        team_map = _player_team_map(s.match)
        team_series = df_window["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid))).to_numpy()
        movement_mask = df_window["action_family"].astype(str).isin(["movement", "military"]).to_numpy()
    team_map = _player_team_map(s.match)

    pulse_heat = np.zeros((grid_size, grid_size), dtype=float)
    static_heat = np.zeros((grid_size, grid_size), dtype=float)
    if layer == "Actividad":
        if player_name != "Todos":
            p_mask = (df_window["player_name"].astype(str).to_numpy() == player_name)
            pulse_heat = _heat_from_cells(gx_all[p_mask & movement_mask], gy_all[p_mask & movement_mask], grid_size)
        else:
            pulse_heat = _heat_from_cells(gx_all[movement_mask], gy_all[movement_mask], grid_size)
        static_heat = _building_heat_persistent(s, t, grid_size, player_name, "Actividad")
    elif layer in ("Propio", "Enemigo", "Presión"):
        sel_team = None
        if player_name != "Todos":
            for p in s.match.players:
                if str(p.name) == player_name:
                    sel_team = int(team_map.get(int(p.number), int(p.number)))
                    break
        if sel_team is None:
            raise HTTPException(status_code=400, detail="player_name is required for Propio/Enemigo/Presión")
        own_mask = (team_series == int(sel_team)) & movement_mask
        enemy_mask = (team_series != int(sel_team)) & movement_mask
        own_pulse = _heat_from_cells(gx_all[own_mask], gy_all[own_mask], grid_size)
        enemy_pulse = _heat_from_cells(gx_all[enemy_mask], gy_all[enemy_mask], grid_size)
        own_static = _building_heat_persistent(s, t, grid_size, player_name, "Propio")
        enemy_static = _building_heat_persistent(s, t, grid_size, player_name, "Enemigo")
        if layer == "Propio":
            pulse_heat = own_pulse
            static_heat = own_static
        elif layer == "Enemigo":
            pulse_heat = enemy_pulse
            static_heat = enemy_static
        else:
            pulse_heat = enemy_pulse - own_pulse
            static_heat = enemy_static - own_static
    else:
        static_heat = _building_heat_persistent(s, t, grid_size, player_name, "Edificios")

    pulse_term = pulse_heat if show_pulses else np.zeros_like(pulse_heat)
    static_term = static_heat if show_buildings else np.zeros_like(static_heat)
    if layer == "Presión":
        heat = (pulse_term * 1.0) + (static_term * 0.45)
    elif layer == "Edificios":
        heat = static_term
    else:
        heat = (pulse_term * 1.0) + (static_term * 0.7)

    resources: list[dict[str, Any]] = []
    if show_resources and s.resources_df is not None and not s.resources_df.empty:
        rdf = s.resources_df.copy()
        rgx = np.floor((rdf["x"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
        rgy = np.floor((rdf["y"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
        rdf["gx"] = rgx.to_numpy()
        rdf["gy"] = rgy.to_numpy()
        for _, r in rdf.iterrows():
            resources.append({"x": int(r["gx"]), "y": int(r["gy"]), "resource_type": str(r["resource_type"])})

    key_objects: list[dict[str, Any]] = []
    if show_key_objects and s.key_objects_df is not None and not s.key_objects_df.empty:
        kdf = s.key_objects_df[s.key_objects_df["time_sec"] <= t].copy()
        if player_name != "Todos":
            kdf = kdf[kdf["player_name"] == player_name]
        if not kdf.empty:
            kgx = np.floor((kdf["x"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
            kgy = np.floor((kdf["y"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
            kdf["gx"] = kgx.to_numpy()
            kdf["gy"] = kgy.to_numpy()
            kdf = kdf.sort_values("time_sec").drop_duplicates(subset=["player_id", "object_kind", "gx", "gy"], keep="last")
            for _, r in kdf.iterrows():
                key_objects.append(
                    {
                        "x": int(r["gx"]),
                        "y": int(r["gy"]),
                        "player_name": str(r["player_name"]),
                        "team_id": int(r["team_id"]),
                        "object_kind": str(r["object_kind"]),
                        "time_sec": float(r["time_sec"]),
                    }
                )

    building_points: list[dict[str, Any]] = []
    if show_building_markers and s.build_events_df is not None and not s.build_events_df.empty:
        bdf = s.build_events_df[s.build_events_df["time_sec"] <= t].copy()
        if player_name != "Todos":
            if layer in ("Propio", "Enemigo"):
                team_ref = None
                for p in s.match.players:
                    if str(p.name) == player_name:
                        team_ref = int(team_map.get(int(p.number), int(p.number)))
                        break
                if team_ref is not None:
                    if layer == "Propio":
                        bdf = bdf[bdf["team_id"].astype(int) == int(team_ref)]
                    else:
                        bdf = bdf[bdf["team_id"].astype(int) != int(team_ref)]
            else:
                bdf = bdf[bdf["player_name"] == player_name]
        if not bdf.empty:
            bgx = np.floor((bdf["x"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
            bgy = np.floor((bdf["y"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
            bdf["gx"] = bgx.to_numpy()
            bdf["gy"] = bgy.to_numpy()
            bdf = bdf.sort_values("time_sec").drop_duplicates(
                subset=["player_id", "building_name", "gx", "gy"], keep="last"
            )
            if len(bdf) > 5000:
                bdf = bdf.iloc[-5000:]
            for _, r in bdf.iterrows():
                building_points.append(
                    {
                        "x": int(r["gx"]),
                        "y": int(r["gy"]),
                        "player_name": str(r["player_name"]),
                        "team_id": int(r["team_id"]),
                        "building_name": str(r["building_name"]),
                        "time_sec": float(r["time_sec"]),
                    }
                )

    unit_points: list[dict[str, Any]] = []
    if show_units and not df_window.empty:
        udf = df_window.copy()
        if player_name != "Todos":
            if layer in ("Propio", "Enemigo"):
                team_ref = None
                for p in s.match.players:
                    if str(p.name) == player_name:
                        team_ref = int(team_map.get(int(p.number), int(p.number)))
                        break
                if team_ref is not None:
                    if layer == "Propio":
                        udf = udf[udf["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid))) == int(team_ref)]
                    else:
                        udf = udf[udf["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid))) != int(team_ref)]
            else:
                udf = udf[udf["player_name"] == player_name]
        if not udf.empty:
            ugx = np.floor((udf["x"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
            ugy = np.floor((udf["y"].astype(float) / s.map_dimension) * grid_size).astype(int).clip(0, grid_size - 1)
            udf["gx"] = ugx.to_numpy()
            udf["gy"] = ugy.to_numpy()
            if len(udf) > 4000:
                step = int(np.ceil(len(udf) / 4000.0))
                udf = udf.iloc[::step]
            for _, r in udf.iterrows():
                unit_points.append(
                    {
                        "x": int(r["gx"]),
                        "y": int(r["gy"]),
                        "player_name": str(r.get("player_name", "") or ""),
                        "team_id": int(team_map.get(int(r.get("player_id", 0) or 0), int(r.get("player_id", 0) or 0))),
                        "action_family": str(r.get("action_family", "") or ""),
                        "event": str(r.get("action_type", "") or ""),
                    }
                )

    event_log: list[dict[str, Any]] = []
    if s.event_log_df is not None and not s.event_log_df.empty:
        lw = max(1, int(log_window_sec))
        log_df = s.event_log_df[(s.event_log_df["time_sec"] <= t) & (s.event_log_df["time_sec"] >= max(0.0, t - float(lw)))]
        if len(log_df) > 250:
            log_df = log_df.iloc[-250:]
        for _, r in log_df.iterrows():
            event_log.append(
                {
                    "time_sec": float(r["time_sec"]),
                    "time_txt": str(r["time_txt"]),
                    "player": str(r["player"]),
                    "event": str(r["event"]),
                    "detail": str(r["detail"]),
                }
            )

    return {
        "t": t,
        "duration_sec": s.duration_sec,
        "grid_size": grid_size,
        "layer": layer,
        "player_name": player_name,
        "heat": heat.tolist(),
        "resources": resources,
        "key_objects": key_objects,
        "building_points": building_points,
        "unit_points": unit_points,
        "event_log": event_log,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("aoe2_web.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
