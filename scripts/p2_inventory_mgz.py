#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mgz.fast
import mgz.summary


def _truncate(text: str, n: int = 140) -> str:
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _record_leaf(path: str, value: Any, bucket: dict[str, dict[str, Any]]) -> None:
    key = path or "$"
    info = bucket.setdefault(key, {"types": set(), "sample": None})
    info["types"].add(type(value).__name__)
    if info["sample"] is None:
        info["sample"] = _truncate(repr(value))


def _walk(obj: Any, bucket: dict[str, dict[str, Any]], prefix: str = "", depth: int = 0, max_depth: int = 6) -> None:
    if depth > max_depth:
        _record_leaf(prefix + ".<max_depth>", obj, bucket)
        return

    if isinstance(obj, dict):
        if not obj:
            _record_leaf(prefix + "{}", obj, bucket)
            return
        for k, v in obj.items():
            kstr = str(k)
            p = f"{prefix}.{kstr}" if prefix else kstr
            _walk(v, bucket, p, depth + 1, max_depth)
        return

    if isinstance(obj, (list, tuple)):
        if not obj:
            _record_leaf(prefix + "[]", obj, bucket)
            return
        p = f"{prefix}[]" if prefix else "[]"
        # sample first items to keep inventory bounded
        for item in obj[:10]:
            _walk(item, bucket, p, depth + 1, max_depth)
        return

    _record_leaf(prefix, obj, bucket)


def _normalize_inventory(bucket: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path, meta in sorted(bucket.items(), key=lambda kv: kv[0]):
        out[path] = {
            "types": sorted(meta["types"]),
            "sample": meta["sample"],
        }
    return out


def _summary_inventory(replay_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "methods_ok": {},
        "methods_error": {},
        "paths": {},
    }

    with replay_path.open("rb") as fh:
        summary = mgz.summary.Summary(fh)

    candidates = []
    for name in dir(summary):
        if not name.startswith("get_"):
            continue
        fn = getattr(summary, name, None)
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
            required = [
                p
                for p in sig.parameters.values()
                if p.default is inspect._empty
                and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            ]
            if len(required) == 0:
                candidates.append(name)
        except Exception:
            # If signature cannot be inspected, skip to avoid accidental side effects.
            continue

    for name in sorted(candidates):
        try:
            value = getattr(summary, name)()
            result["methods_ok"][name] = True
            bucket: dict[str, dict[str, Any]] = {}
            _walk(value, bucket)
            result["paths"][name] = _normalize_inventory(bucket)
        except Exception as exc:
            result["methods_error"][name] = f"{type(exc).__name__}: {exc}"

    return result


def _fast_postgame_inventory(replay_path: Path) -> dict[str, Any]:
    with replay_path.open("rb") as fh:
        post = mgz.fast.postgame(fh)
    bucket: dict[str, dict[str, Any]] = {}
    _walk(post, bucket)
    return {
        "paths": _normalize_inventory(bucket),
    }


def _fast_sync_inventory(replay_path: Path, max_sync_packets: int) -> dict[str, Any]:
    bucket: dict[str, dict[str, Any]] = {}
    total_ops = 0
    sync_count = 0

    with replay_path.open("rb") as fh:
        try:
            mgz.fast.start(fh)
        except Exception:
            pass
        while sync_count < max_sync_packets:
            try:
                op_type, payload = mgz.fast.operation(fh)
                total_ops += 1
            except EOFError:
                break
            except Exception:
                continue

            if op_type != mgz.fast.Operation.SYNC:
                continue
            sync_count += 1
            _walk(payload, bucket, prefix="sync")

    return {
        "max_sync_packets": max_sync_packets,
        "sync_packets_seen": sync_count,
        "operations_scanned": total_ops,
        "paths": _normalize_inventory(bucket),
    }


def build_report(replay_path: Path, max_sync_packets: int) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "replay_path": str(replay_path.resolve()),
        "part2": {
            "P2-001_mgz_summary_inventory": _summary_inventory(replay_path),
            "P2-002_mgz_fast_inventory": {
                "postgame": _fast_postgame_inventory(replay_path),
                "sync": _fast_sync_inventory(replay_path, max_sync_packets=max_sync_packets),
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory of fields currently extractable via mgz.summary and mgz.fast")
    parser.add_argument("replay", help="Path to .aoe2record")
    parser.add_argument("--max-sync-packets", type=int, default=300, help="How many SYNC packets to inspect")
    parser.add_argument("--out", default="reports/p2_inventory_mgz.json", help="Output JSON path")
    args = parser.parse_args()

    replay_path = Path(args.replay)
    if not replay_path.exists():
        raise SystemExit(f"Replay not found: {replay_path}")

    report = build_report(replay_path, max_sync_packets=max(1, int(args.max_sync_packets)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=True)

    print(json.dumps({
        "out": str(out),
        "summary_methods_ok": len(report["part2"]["P2-001_mgz_summary_inventory"]["methods_ok"]),
        "summary_methods_error": len(report["part2"]["P2-001_mgz_summary_inventory"]["methods_error"]),
        "fast_postgame_paths": len(report["part2"]["P2-002_mgz_fast_inventory"]["postgame"]["paths"]),
        "fast_sync_paths": len(report["part2"]["P2-002_mgz_fast_inventory"]["sync"]["paths"]),
        "fast_sync_packets_seen": report["part2"]["P2-002_mgz_fast_inventory"]["sync"]["sync_packets_seen"],
    }, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
