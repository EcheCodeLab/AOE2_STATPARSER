"""CLI entrypoint for AoE2 replay parsing and structured exports."""
from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from aoe2stat.layers import ParserLayer, TransformLayer, PresentationLayer, dumps_payload


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
        "--export-idmap-csv",
        help="Export replay-derived id mapping table to CSV path.",
    )
    parser.add_argument(
        "--export-idmap-jsonl",
        help="Export replay-derived id mapping table to JSONL path.",
    )
    parser.add_argument(
        "--export-idmap-parquet",
        help="Export replay-derived id mapping table to Parquet path.",
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
        replay_path = ParserLayer.download_replay(args.download)
    elif args.replay is not None:
        replay_path = Path(args.replay)
        if not replay_path.exists():
            raise SystemExit(f"File not found: {replay_path}")
    else:
        raise SystemExit("No replay file provided.")

    summary = ParserLayer.parse_summary(replay_path)
    output: dict[str, object] = {"summary": PresentationLayer.summary_to_payload(summary)}

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
    if wants_structured:
        transformer = TransformLayer()
        try:
            bundle = transformer.analyze(
                replay_path=replay_path,
                grid_size=int(args.grid_size),
                window_sec=int(args.window_sec),
            )
            output["structured"] = PresentationLayer.export_structured(
                bundle=bundle,
                events_csv=args.export_events_csv,
                events_jsonl=args.export_events_jsonl,
                events_parquet=args.export_events_parquet,
                spatial_csv=args.export_spatial_csv,
                spatial_parquet=args.export_spatial_parquet,
                idmap_csv=args.export_idmap_csv,
                idmap_jsonl=args.export_idmap_jsonl,
                idmap_parquet=args.export_idmap_parquet,
                grid_size=int(args.grid_size),
                window_sec=int(args.window_sec),
                replay_path=replay_path,
            )
        except Exception as exc:
            # Controlled degradation for corrupt/truncated files (P2-007):
            # keep summary output and emit actionable structured warnings.
            output["structured"] = {
                "match_meta": {
                    "match_id": replay_path.stem,
                    "replay_path": str(replay_path),
                    "duration_sec": float(getattr(summary, "duration_seconds", 0.0) or 0.0),
                    "map_name": str(getattr(summary, "map_name", "") or ""),
                    "map_dimension": 0.0,
                    "players": [],
                },
                "events_count": 0,
                "parse_warnings": [
                    {
                        "code": "W_STRUCTURED_ANALYZE_FAILED",
                        "severity": "severe",
                        "message": f"{type(exc).__name__}: {exc}",
                    }
                ],
                "error_trace": traceback.format_exc(limit=2),
            }

    print(dumps_payload(output))


if __name__ == "__main__":
    main()
