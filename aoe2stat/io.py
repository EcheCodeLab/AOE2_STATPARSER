from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .core import load_match


def read_match(replay_path: str | Path):
    return load_match(replay_path)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8")


def write_csv(df: pd.DataFrame, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)


def write_jsonl(df: pd.DataFrame, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in df.to_dict(orient="records"):
            fh.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")


def write_parquet(df: pd.DataFrame, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(out, index=False, compression="snappy")
    except Exception as exc:
        raise RuntimeError(
            "Parquet export failed. Install 'pyarrow' or 'fastparquet'."
        ) from exc


def sanitize_partition_value(value: Any, default: str = "unknown") -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
    cleaned = cleaned.strip("._-")
    return cleaned or default


def dataset_relpath(
    table: str,
    match_id: str,
    parser_version: str,
    schema_version: str,
    event_date: str,
    map_name: str | None = None,
    elo_bucket: str | None = None,
) -> Path:
    table_v = sanitize_partition_value(table, default="table")
    match_v = sanitize_partition_value(match_id, default="match")
    parser_v = sanitize_partition_value(parser_version, default="parser")
    schema_v = sanitize_partition_value(schema_version, default="schema")
    date_v = sanitize_partition_value(event_date, default="date")
    map_v = sanitize_partition_value(map_name, default="unknown")
    elo_v = sanitize_partition_value(elo_bucket, default="unknown")
    return Path(
        f"{table_v}/schema_version={schema_v}/parser_version={parser_v}/"
        f"event_date={date_v}/map_name={map_v}/elo_bucket={elo_v}/match_id={match_v}"
    )
