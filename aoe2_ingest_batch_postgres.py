from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from aoe2_ingest_postgres import ingest_replay


def _discover_replays(input_dir: Path, recursive: bool = True) -> list[Path]:
    pattern = "**/*.aoe2record" if recursive else "*.aoe2record"
    return sorted([p for p in input_dir.glob(pattern) if p.is_file()])


def _load_list_file(path: Path) -> list[Path]:
    out: list[Path] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(Path(line))
    return out


def _collect_inputs(args) -> list[Path]:
    paths: list[Path] = []
    if args.input_dir:
        paths.extend(_discover_replays(Path(args.input_dir), recursive=not args.no_recursive))
    if args.list_file:
        paths.extend(_load_list_file(Path(args.list_file)))
    if args.replays:
        paths.extend(Path(p) for p in args.replays)
    unique: list[Path] = []
    seen = set()
    for p in paths:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=True, default=str) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingest AoE2 replays into Postgres/Supabase.")
    parser.add_argument("replays", nargs="*", help="Replay paths")
    parser.add_argument("--input-dir", help="Directory containing .aoe2record files")
    parser.add_argument("--list-file", help="Text file with one replay path per line")
    parser.add_argument("--no-recursive", action="store_true", help="Do not recurse input directory")
    parser.add_argument("--dsn", required=True, help="Postgres DSN")
    parser.add_argument("--parser-version", default="sprint-1.1", help="Version tag for upsert keys")
    parser.add_argument("--grid-size", type=int, default=32, help="Grid size for spatial frames")
    parser.add_argument("--window-sec", type=int, default=10, help="Window size in seconds for spatial frames")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Insert batch chunk size")
    parser.add_argument("--apply-schema", action="store_true", help="Apply schema before first ingest")
    parser.add_argument("--retries", type=int, default=1, help="Retries per replay on failure")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue processing after failures")
    parser.add_argument("--out-dir", default="ingest_out", help="Output directory for reports")
    args = parser.parse_args()

    inputs = _collect_inputs(args)
    if not inputs:
        raise SystemExit("No replay inputs provided.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    ok = 0
    failed = 0
    started = time.time()

    for idx, replay in enumerate(inputs, start=1):
        if not replay.exists():
            row = {
                "replay": str(replay),
                "status": "error",
                "error": "file_not_found",
                "index": idx,
            }
            results.append(row)
            failed += 1
            if not args.continue_on_error:
                break
            continue

        attempt = 0
        last_err: str | None = None
        while attempt <= args.retries:
            attempt += 1
            try:
                res = ingest_replay(
                    replay_path=replay,
                    dsn=args.dsn,
                    parser_version=str(args.parser_version),
                    grid_size=int(args.grid_size),
                    window_sec=int(args.window_sec),
                    chunk_size=max(1, int(args.chunk_size)),
                    apply_schema=bool(args.apply_schema and idx == 1 and attempt == 1),
                )
                res["replay"] = str(replay)
                res["attempt"] = attempt
                res["index"] = idx
                results.append(res)
                ok += 1
                last_err = None
                break
            except Exception as exc:
                last_err = str(exc)
                if attempt > args.retries:
                    break
                time.sleep(min(3.0, 0.5 * attempt))

        if last_err is not None:
            results.append(
                {
                    "replay": str(replay),
                    "status": "error",
                    "error": last_err,
                    "attempt": attempt,
                    "index": idx,
                }
            )
            failed += 1
            if not args.continue_on_error:
                break

    ended = time.time()
    report = {
        "inputs_total": len(inputs),
        "ok": ok,
        "failed": failed,
        "duration_sec": round(ended - started, 3),
        "parser_version": str(args.parser_version),
        "grid_size": int(args.grid_size),
        "window_sec": int(args.window_sec),
        "results_jsonl": str(out_dir / "ingest_results.jsonl"),
    }

    _write_jsonl(out_dir / "ingest_results.jsonl", results)
    (out_dir / "ingest_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

