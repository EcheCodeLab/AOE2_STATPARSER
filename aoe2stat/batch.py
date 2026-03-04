from __future__ import annotations

from pathlib import Path
from typing import Any

from .services import ReplayAnalysisService


def run_batch_analysis(
    replay_paths: list[str | Path],
    service: ReplayAnalysisService | None = None,
    continue_on_error: bool = True,
) -> list[dict[str, Any]]:
    svc = service or ReplayAnalysisService()
    out: list[dict[str, Any]] = []
    for rp in replay_paths:
        p = Path(rp)
        try:
            bundle = svc.analyze(p)
            row = bundle.to_dict()
            row["replay_path"] = str(p)
            row["status"] = "ok"
            out.append(row)
        except Exception as exc:
            out.append({"replay_path": str(p), "status": "error", "error": str(exc)})
            if not continue_on_error:
                break
    return out

