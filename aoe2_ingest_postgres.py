from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aoe2stat.services import ReplayAnalysisService


def _require_psycopg2():
    try:
        import psycopg2  # type: ignore
        from psycopg2.extras import execute_batch  # type: ignore
        return psycopg2, execute_batch
    except Exception as exc:
        raise SystemExit(
            "Missing dependency: psycopg2-binary. Install with:\n"
            "  pip install psycopg2-binary"
        ) from exc


def _run_schema_if_requested(cur, apply_schema: bool) -> None:
    if not apply_schema:
        return
    schema_path = Path("db/supabase_schema.sql")
    if not schema_path.exists():
        raise SystemExit(f"Schema file not found: {schema_path}")
    cur.execute(schema_path.read_text(encoding="utf-8"))


def _chunked_rows(rows: list[tuple[Any, ...]], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def ingest_replay(
    replay_path: Path,
    dsn: str,
    parser_version: str,
    grid_size: int,
    window_sec: int,
    chunk_size: int,
    apply_schema: bool,
) -> dict[str, Any]:
    psycopg2, execute_batch = _require_psycopg2()

    service = ReplayAnalysisService()
    bundle = service.analyze(
        replay_path=replay_path,
        grid_size=grid_size,
        window_sec=window_sec,
    )
    meta = bundle.match_meta
    events_df = bundle.events_raw
    spatial_df = bundle.spatial_frames

    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                _run_schema_if_requested(cur, apply_schema=apply_schema)

                cur.execute(
                    """
                    insert into public.matches (
                      match_id, replay_path, duration_sec, map_name, map_dimension, parser_version
                    ) values (%s, %s, %s, %s, %s, %s)
                    on conflict (match_id, parser_version)
                    do update set
                      replay_path = excluded.replay_path,
                      duration_sec = excluded.duration_sec,
                      map_name = excluded.map_name,
                      map_dimension = excluded.map_dimension
                    """,
                    (
                        str(meta["match_id"]),
                        str(meta["replay_path"]),
                        float(meta["duration_sec"]),
                        str(meta.get("map_name", "")),
                        float(meta.get("map_dimension", 120.0)),
                        parser_version,
                    ),
                )

                players_rows = [
                    (
                        str(meta["match_id"]),
                        parser_version,
                        int(p["player_id"]),
                        str(p["player_name"]),
                        str(p.get("civilization") or ""),
                        int(p.get("color_id") or 0),
                    )
                    for p in (meta.get("players") or [])
                ]
                execute_batch(
                    cur,
                    """
                    insert into public.players (
                      match_id, parser_version, player_id, player_name, civilization, color_id
                    ) values (%s, %s, %s, %s, %s, %s)
                    on conflict (match_id, parser_version, player_id)
                    do update set
                      player_name = excluded.player_name,
                      civilization = excluded.civilization,
                      color_id = excluded.color_id
                    """,
                    players_rows,
                    page_size=max(1, min(chunk_size, 5000)),
                )

                event_rows = [
                    (
                        str(r.match_id),
                        parser_version,
                        int(r.event_id),
                        int(r.t_ms),
                        float(r.time_sec),
                        int(r.player_id),
                        str(r.player_name),
                        str(r.action_type),
                        str(r.action_family),
                        None if r.x != r.x else float(r.x),
                        None if r.y != r.y else float(r.y),
                        str(r.payload_json),
                    )
                    for r in events_df.itertuples(index=False)
                ]
                for chunk in _chunked_rows(event_rows, chunk_size):
                    execute_batch(
                        cur,
                        """
                        insert into public.events_raw (
                          match_id, parser_version, event_id, t_ms, time_sec, player_id, player_name,
                          action_type, action_family, x, y, payload_json
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        on conflict (match_id, parser_version, event_id)
                        do update set
                          t_ms = excluded.t_ms,
                          time_sec = excluded.time_sec,
                          player_id = excluded.player_id,
                          player_name = excluded.player_name,
                          action_type = excluded.action_type,
                          action_family = excluded.action_family,
                          x = excluded.x,
                          y = excluded.y,
                          payload_json = excluded.payload_json
                        """,
                        chunk,
                        page_size=max(1, min(chunk_size, 5000)),
                    )

                spatial_rows = [
                    (
                        str(r.match_id),
                        parser_version,
                        int(r.time_bin_sec),
                        int(r.window_sec),
                        int(r.grid_size),
                        int(r.player_id),
                        str(r.player_name),
                        str(r.action_family),
                        int(r.cell_x),
                        int(r.cell_y),
                        int(r.event_count),
                    )
                    for r in spatial_df.itertuples(index=False)
                ]
                for chunk in _chunked_rows(spatial_rows, chunk_size):
                    execute_batch(
                        cur,
                        """
                        insert into public.spatial_frames (
                          match_id, parser_version, time_bin_sec, window_sec, grid_size, player_id,
                          player_name, action_family, cell_x, cell_y, event_count
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        on conflict (match_id, parser_version, time_bin_sec, window_sec, grid_size, player_id, action_family, cell_x, cell_y)
                        do update set
                          event_count = excluded.event_count,
                          player_name = excluded.player_name
                        """,
                        chunk,
                        page_size=max(1, min(chunk_size, 5000)),
                    )
    finally:
        conn.close()

    return {
        "match_id": str(meta["match_id"]),
        "parser_version": parser_version,
        "events_count": int(len(events_df)),
        "spatial_frames_count": int(len(spatial_df)),
        "grid_size": int(grid_size),
        "window_sec": int(window_sec),
        "features": bundle.features,
        "validation": bundle.validation,
        "status": "ok",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a parsed AoE2 replay into Postgres/Supabase.")
    parser.add_argument("replay", help="Path to .aoe2record file")
    parser.add_argument("--dsn", required=True, help="Postgres DSN")
    parser.add_argument("--parser-version", default="sprint-1.1", help="Version tag for upsert keys")
    parser.add_argument("--grid-size", type=int, default=32, help="Grid size for spatial frames")
    parser.add_argument("--window-sec", type=int, default=10, help="Window size in seconds for spatial frames")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Batch chunk size")
    parser.add_argument("--apply-schema", action="store_true", help="Apply db/supabase_schema.sql before ingest")
    args = parser.parse_args()

    replay_path = Path(args.replay)
    if not replay_path.exists():
        raise SystemExit(f"Replay file not found: {replay_path}")

    result = ingest_replay(
        replay_path=replay_path,
        dsn=args.dsn,
        parser_version=str(args.parser_version),
        grid_size=int(args.grid_size),
        window_sec=int(args.window_sec),
        chunk_size=max(1, int(args.chunk_size)),
        apply_schema=bool(args.apply_schema),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
