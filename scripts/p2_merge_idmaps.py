#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "match_id",
    "mapping_kind",
    "internal_id",
    "human_name",
    "seen_count",
    "first_t_ms",
    "patch_version",
}


def _read_one(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file format: {path}")


def _collect_inputs(inputs: list[str], input_dir: str | None, glob_pattern: str) -> list[Path]:
    out: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            out.extend(sorted(p.rglob(glob_pattern)))
        elif p.exists():
            out.append(p)
    if input_dir:
        out.extend(sorted(Path(input_dir).rglob(glob_pattern)))

    # Deduplicate by resolved path preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        k = str(p.resolve())
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    return uniq


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    out = df.copy()
    out = out[[
        "match_id",
        "mapping_kind",
        "internal_id",
        "human_name",
        "seen_count",
        "first_t_ms",
        "patch_version",
    ]]
    out["match_id"] = out["match_id"].astype(str)
    out["mapping_kind"] = out["mapping_kind"].astype(str)
    out["internal_id"] = pd.to_numeric(out["internal_id"], errors="coerce").fillna(-1).astype(int)
    out["human_name"] = out["human_name"].astype(str).str.strip()
    out["seen_count"] = pd.to_numeric(out["seen_count"], errors="coerce").fillna(0).astype(int)
    out["first_t_ms"] = pd.to_numeric(out["first_t_ms"], errors="coerce").fillna(0).astype(int)
    out["patch_version"] = out["patch_version"].astype(str)
    out = out[(out["internal_id"] >= 0) & (out["human_name"] != "")]
    return out


def merge_idmaps(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    # Observed aggregation by exact (patch,kind,id,name)
    observed = (
        df.groupby(["patch_version", "mapping_kind", "internal_id", "human_name"], dropna=False)
        .agg(
            seen_count_total=("seen_count", "sum"),
            first_t_ms_min=("first_t_ms", "min"),
            match_count=("match_id", "nunique"),
        )
        .reset_index()
        .sort_values(["patch_version", "mapping_kind", "internal_id", "seen_count_total"], ascending=[True, True, True, False])
    )

    canonical_rows: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for (patch, kind, internal_id), grp in observed.groupby(["patch_version", "mapping_kind", "internal_id"], sort=True):
        grp = grp.sort_values(["seen_count_total", "match_count", "human_name"], ascending=[False, False, True])
        best = grp.iloc[0]
        candidate_names = grp["human_name"].tolist()
        is_conflict = len(candidate_names) > 1
        canonical_rows.append(
            {
                "patch_version": str(patch),
                "mapping_kind": str(kind),
                "internal_id": int(internal_id),
                "canonical_name": str(best["human_name"]),
                "seen_count_total": int(best["seen_count_total"]),
                "match_count": int(best["match_count"]),
                "candidate_name_count": int(len(candidate_names)),
                "has_conflict": bool(is_conflict),
            }
        )
        if is_conflict:
            conflicts.append(
                {
                    "patch_version": str(patch),
                    "mapping_kind": str(kind),
                    "internal_id": int(internal_id),
                    "canonical_name": str(best["human_name"]),
                    "candidates": [
                        {
                            "human_name": str(r["human_name"]),
                            "seen_count_total": int(r["seen_count_total"]),
                            "match_count": int(r["match_count"]),
                        }
                        for _, r in grp.iterrows()
                    ],
                }
            )

    canonical = pd.DataFrame(canonical_rows).sort_values(["patch_version", "mapping_kind", "internal_id"])
    return observed, canonical, conflicts


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge replay-derived idmap files into canonical mapping by patch")
    parser.add_argument("inputs", nargs="*", help="Input idmap files (.csv/.jsonl/.parquet) or directories")
    parser.add_argument("--input-dir", help="Optional input directory to scan recursively")
    parser.add_argument("--glob", default="*idmap*.csv", help="Glob pattern used with directories (default: *idmap*.csv)")
    parser.add_argument("--out-observed-csv", default="reports/idmap_observed_merged.csv")
    parser.add_argument("--out-canonical-csv", default="reports/idmap_canonical.csv")
    parser.add_argument("--out-conflicts-json", default="reports/idmap_conflicts.json")
    args = parser.parse_args()

    paths = _collect_inputs(args.inputs, args.input_dir, args.glob)
    if not paths:
        raise SystemExit("No idmap inputs found. Pass files/directories and/or --input-dir.")

    frames: list[pd.DataFrame] = []
    for p in paths:
        try:
            frames.append(_normalize(_read_one(p)))
        except Exception as exc:
            raise SystemExit(f"Failed reading {p}: {exc}")

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    observed, canonical, conflicts = merge_idmaps(raw)

    out_observed = Path(args.out_observed_csv)
    out_canonical = Path(args.out_canonical_csv)
    out_conflicts = Path(args.out_conflicts_json)
    out_observed.parent.mkdir(parents=True, exist_ok=True)
    out_canonical.parent.mkdir(parents=True, exist_ok=True)
    out_conflicts.parent.mkdir(parents=True, exist_ok=True)

    observed.to_csv(out_observed, index=False)
    canonical.to_csv(out_canonical, index=False)
    out_conflicts.write_text(json.dumps(conflicts, indent=2, ensure_ascii=True), encoding="utf-8")

    print(
        json.dumps(
            {
                "inputs": [str(p) for p in paths],
                "rows_input": int(len(raw)),
                "rows_observed": int(len(observed)),
                "rows_canonical": int(len(canonical)),
                "conflict_keys": int(len(conflicts)),
                "out_observed_csv": str(out_observed),
                "out_canonical_csv": str(out_canonical),
                "out_conflicts_json": str(out_conflicts),
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
