from __future__ import annotations

import json
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
        df.to_parquet(out, index=False)
    except Exception as exc:
        raise RuntimeError(
            "Parquet export failed. Install 'pyarrow' or 'fastparquet'."
        ) from exc

