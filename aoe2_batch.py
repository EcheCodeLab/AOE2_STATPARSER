from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from aoe2_parser import download_replay, parse_replay
from aoe2stat.core import load_match
from aoe2stat.pipeline import (
    build_match_meta,
    export_events,
    export_id_mappings,
    export_spatial_frames,
    extract_id_mappings,
    extract_raw_events,
    spatial_frames_from_events,
)


def _merge_idmaps_global(df):
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
    import pandas as pd
    canonical = pd.DataFrame(canonical_rows).sort_values(["patch_version", "mapping_kind", "internal_id"])
    return observed, canonical, conflicts


@dataclass
class ReplayJob:
    source: str
    replay_path: Path
    source_kind: str  # local | download


@dataclass
class ReplayResult:
    replay_path: str
    sha256: str
    status: str  # ok | error | skipped_duplicate | skipped_checkpoint
    attempts: int
    elapsed_sec: float
    error: str | None
    summary_path: str | None
    events_csv_path: str | None = None
    events_jsonl_path: str | None = None
    events_parquet_path: str | None = None
    idmap_csv_path: str | None = None
    idmap_jsonl_path: str | None = None
    idmap_parquet_path: str | None = None
    spatial_csv_path: str | None = None
    spatial_parquet_path: str | None = None
    events_count: int = 0
    idmap_count: int = 0
    spatial_frames_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class StructuredExportConfig:
    export_events: bool
    export_spatial: bool
    export_events_parquet: bool
    export_spatial_parquet: bool
    export_idmap: bool
    export_idmap_parquet: bool
    merge_idmap: bool
    parquet_strict: bool
    grid_size: int
    window_sec: int


class BatchRunner:
    def __init__(
        self,
        out_dir: Path,
        checkpoint_path: Path,
        retries: int,
        continue_on_error: bool,
        strict: bool,
        dedupe: bool,
        dry_run: bool,
        report_every: int,
        structured: StructuredExportConfig,
    ) -> None:
        self.out_dir = out_dir
        self.checkpoint_path = checkpoint_path
        self.retries = max(0, int(retries))
        self.continue_on_error = continue_on_error
        self.strict = strict
        self.dedupe = dedupe
        self.dry_run = dry_run
        self.report_every = max(1, int(report_every))
        self.structured = structured

        self.job_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc)
        self.summaries_dir = self.out_dir / "summaries"
        self.report_path = self.out_dir / "batch_report.json"
        self.results_jsonl = self.out_dir / "results.jsonl"

        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

        self.checkpoint = self._load_checkpoint()
        self._seen_hashes: set[str] = set()
        self._parquet_check_done = False
        self._parquet_available = False

    def _export_signature(self) -> dict[str, Any]:
        return asdict(self.structured)

    def _ensure_parquet_engine(self) -> None:
        if self._parquet_check_done:
            return
        self._parquet_check_done = True
        try:
            import pyarrow  # type: ignore  # noqa: F401
            self._parquet_available = True
            return
        except Exception:
            pass
        try:
            import fastparquet  # type: ignore  # noqa: F401
            self._parquet_available = True
            return
        except Exception:
            self._parquet_available = False

        wants_parquet = (
            self.structured.export_events_parquet
            or self.structured.export_spatial_parquet
            or self.structured.export_idmap_parquet
        )
        if not wants_parquet:
            return
        msg = "Parquet engine not found. Install 'pyarrow' or 'fastparquet'."
        if self.structured.parquet_strict:
            raise RuntimeError(msg)
        print(f"[warn] {msg} Parquet exports will be skipped.")

    def _load_checkpoint(self) -> dict[str, Any]:
        if not self.checkpoint_path.exists():
            return {
                "job_id": self.job_id,
                "updated_at": self._now_iso(),
                "entries": {},
            }
        try:
            with self.checkpoint_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("invalid checkpoint format")
            data.setdefault("entries", {})
            return data
        except Exception:
            # Corrupt checkpoint should not block the run.
            return {
                "job_id": self.job_id,
                "updated_at": self._now_iso(),
                "entries": {},
            }

    def _save_checkpoint(self) -> None:
        self.checkpoint["updated_at"] = self._now_iso()
        tmp = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(self.checkpoint, fh, indent=2, ensure_ascii=True)
        tmp.replace(self.checkpoint_path)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _summary_to_dict(obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return {k: BatchRunner._summary_to_dict(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list):
            return [BatchRunner._summary_to_dict(v) for v in obj]
        return obj

    def _result_to_checkpoint_entry(self, result: ReplayResult) -> dict[str, Any]:
        return asdict(result)

    def _append_result_jsonl(self, result: ReplayResult) -> None:
        with self.results_jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(result), ensure_ascii=True) + "\n")

    def run(self, jobs: list[ReplayJob]) -> dict[str, Any]:
        self._ensure_parquet_engine()
        stats = {
            "total_jobs": len(jobs),
            "ok": 0,
            "error": 0,
            "skipped_duplicate": 0,
            "skipped_checkpoint": 0,
            "processed": 0,
        }
        results: list[ReplayResult] = []
        t0 = time.perf_counter()

        for idx, job in enumerate(jobs, start=1):
            key = str(job.replay_path.resolve())
            cp_entry = self.checkpoint["entries"].get(key)
            if cp_entry and cp_entry.get("status") == "ok" and cp_entry.get("export_signature") == self._export_signature():
                result = ReplayResult(
                    replay_path=key,
                    sha256=str(cp_entry.get("sha256", "")),
                    status="skipped_checkpoint",
                    attempts=0,
                    elapsed_sec=0.0,
                    error=None,
                    summary_path=cp_entry.get("summary_path"),
                    events_csv_path=cp_entry.get("events_csv_path"),
                    events_jsonl_path=cp_entry.get("events_jsonl_path"),
                    events_parquet_path=cp_entry.get("events_parquet_path"),
                    idmap_csv_path=cp_entry.get("idmap_csv_path"),
                    idmap_jsonl_path=cp_entry.get("idmap_jsonl_path"),
                    idmap_parquet_path=cp_entry.get("idmap_parquet_path"),
                    spatial_csv_path=cp_entry.get("spatial_csv_path"),
                    spatial_parquet_path=cp_entry.get("spatial_parquet_path"),
                    events_count=int(cp_entry.get("events_count", 0) or 0),
                    idmap_count=int(cp_entry.get("idmap_count", 0) or 0),
                    spatial_frames_count=int(cp_entry.get("spatial_frames_count", 0) or 0),
                    warnings=list(cp_entry.get("warnings", []) or []),
                )
                stats["skipped_checkpoint"] += 1
                results.append(result)
                if idx % self.report_every == 0:
                    print(f"[{idx}/{len(jobs)}] skip checkpoint: {job.replay_path}")
                continue

            if not job.replay_path.exists():
                result = ReplayResult(
                    replay_path=key,
                    sha256="",
                    status="error",
                    attempts=1,
                    elapsed_sec=0.0,
                    error="file_not_found",
                    summary_path=None,
                )
                self._record_result(key, result)
                stats["error"] += 1
                results.append(result)
                if not self.continue_on_error:
                    break
                continue

            sha = self._sha256(job.replay_path)
            if self.dedupe and sha in self._seen_hashes:
                result = ReplayResult(
                    replay_path=key,
                    sha256=sha,
                    status="skipped_duplicate",
                    attempts=0,
                    elapsed_sec=0.0,
                    error=None,
                    summary_path=None,
                )
                self._record_result(key, result)
                stats["skipped_duplicate"] += 1
                results.append(result)
                if idx % self.report_every == 0:
                    print(f"[{idx}/{len(jobs)}] skip duplicate hash: {job.replay_path}")
                continue
            self._seen_hashes.add(sha)

            result = self._process_with_retries(job, key, sha)
            self._record_result(key, result)
            results.append(result)
            stats[result.status] = stats.get(result.status, 0) + 1

            if result.status == "error" and not self.continue_on_error:
                break

            if idx % self.report_every == 0 or result.status == "error":
                print(f"[{idx}/{len(jobs)}] {result.status}: {job.replay_path}")

        elapsed = time.perf_counter() - t0
        stats["processed"] = stats["ok"] + stats["error"]
        throughput = (stats["processed"] / elapsed * 60.0) if elapsed > 0 else 0.0

        report = {
            "job_id": self.job_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self._now_iso(),
            "elapsed_sec": round(elapsed, 3),
            "throughput_replays_per_min": round(throughput, 2),
            "strict": self.strict,
            "continue_on_error": self.continue_on_error,
            "dedupe": self.dedupe,
            "dry_run": self.dry_run,
            "stats": stats,
            "checkpoint_path": str(self.checkpoint_path),
            "results_jsonl": str(self.results_jsonl),
            "export_signature": self._export_signature(),
            "results": [asdict(r) for r in results],
        }
        merge_report = self._merge_idmaps_if_requested(results)
        if merge_report is not None:
            report["idmap_merge"] = merge_report
        with self.report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=True)
        return report

    def _merge_idmaps_if_requested(self, results: list[ReplayResult]) -> dict[str, Any] | None:
        if not self.structured.merge_idmap:
            return None
        inputs: list[Path] = []
        for r in results:
            if r.idmap_csv_path:
                inputs.append(Path(r.idmap_csv_path))
            elif r.idmap_parquet_path:
                inputs.append(Path(r.idmap_parquet_path))
        inputs = [p for p in inputs if p.exists()]
        if not inputs:
            return {"enabled": True, "merged": False, "reason": "no_idmap_inputs"}

        frames: list[Any] = []
        for p in inputs:
            if p.suffix.lower() == ".csv":
                import pandas as pd
                frames.append(pd.read_csv(p))
            elif p.suffix.lower() == ".jsonl":
                import pandas as pd
                frames.append(pd.read_json(p, lines=True))
            elif p.suffix.lower() == ".parquet":
                import pandas as pd
                frames.append(pd.read_parquet(p))

        if not frames:
            return {"enabled": True, "merged": False, "reason": "no_readable_idmap_inputs"}

        import pandas as pd
        raw = pd.concat(frames, ignore_index=True)
        observed, canonical, conflicts = _merge_idmaps_global(raw)
        out_observed = self.out_dir / "idmap_observed_merged.csv"
        out_canonical = self.out_dir / "idmap_canonical.csv"
        out_conflicts = self.out_dir / "idmap_conflicts.json"
        observed.to_csv(out_observed, index=False)
        canonical.to_csv(out_canonical, index=False)
        out_conflicts.write_text(json.dumps(conflicts, indent=2, ensure_ascii=True), encoding="utf-8")
        return {
            "enabled": True,
            "merged": True,
            "inputs_count": int(len(inputs)),
            "rows_observed": int(len(observed)),
            "rows_canonical": int(len(canonical)),
            "conflict_keys": int(len(conflicts)),
            "out_observed_csv": str(out_observed),
            "out_canonical_csv": str(out_canonical),
            "out_conflicts_json": str(out_conflicts),
        }

    def _process_with_retries(self, job: ReplayJob, key: str, sha: str) -> ReplayResult:
        attempts = 0
        t0 = time.perf_counter()
        last_error: str | None = None

        while attempts <= self.retries:
            attempts += 1
            try:
                if self.dry_run:
                    elapsed = time.perf_counter() - t0
                    return ReplayResult(
                        replay_path=key,
                        sha256=sha,
                        status="ok",
                        attempts=attempts,
                        elapsed_sec=round(elapsed, 3),
                        error=None,
                        summary_path=None,
                    )

                summary = parse_replay(job.replay_path)
                payload = {
                    "job_id": self.job_id,
                    "source_kind": job.source_kind,
                    "source": job.source,
                    "replay_path": key,
                    "sha256": sha,
                    "parsed_at": self._now_iso(),
                    "summary": self._summary_to_dict(summary),
                }
                summary_name = f"{sha[:12]}_{job.replay_path.stem}.json"
                summary_path = self.summaries_dir / summary_name
                with summary_path.open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2, ensure_ascii=True, default=str)

                events_csv_path: str | None = None
                events_jsonl_path: str | None = None
                events_parquet_path: str | None = None
                idmap_csv_path: str | None = None
                idmap_jsonl_path: str | None = None
                idmap_parquet_path: str | None = None
                spatial_csv_path: str | None = None
                spatial_parquet_path: str | None = None
                events_count = 0
                idmap_count = 0
                spatial_count = 0
                warnings: list[str] = []
                if (
                    self.structured.export_events
                    or self.structured.export_spatial
                    or self.structured.export_events_parquet
                    or self.structured.export_spatial_parquet
                    or self.structured.export_idmap
                    or self.structured.export_idmap_parquet
                ):
                    match = load_match(job.replay_path)
                    meta = build_match_meta(match, job.replay_path)
                    events_df = extract_raw_events(match, match_id=meta.match_id)
                    events_count = int(len(events_df))
                    if self.structured.export_events:
                        events_csv = self.out_dir / "events_csv" / f"{sha[:12]}_{job.replay_path.stem}.csv"
                        events_jsonl = self.out_dir / "events_jsonl" / f"{sha[:12]}_{job.replay_path.stem}.jsonl"
                        export_events(events_df, csv_path=events_csv, jsonl_path=events_jsonl)
                        events_csv_path = str(events_csv)
                        events_jsonl_path = str(events_jsonl)
                    if self.structured.export_events_parquet:
                        events_parquet = self.out_dir / "events_parquet" / f"{sha[:12]}_{job.replay_path.stem}.parquet"
                        events_parquet.parent.mkdir(parents=True, exist_ok=True)
                        if not self._parquet_available:
                            warnings.append("parquet_export_events_skipped: missing engine")
                        else:
                            try:
                                events_df.to_parquet(events_parquet, index=False, compression="snappy")
                            except Exception as exc:  # pragma: no cover
                                msg = f"parquet_export_events_failed: {exc}"
                                if self.structured.parquet_strict:
                                    raise RuntimeError(msg) from exc
                                warnings.append(msg)
                            else:
                                events_parquet_path = str(events_parquet)
                    if self.structured.export_idmap or self.structured.export_idmap_parquet:
                        idmap_df = extract_id_mappings(match, match_id=meta.match_id)
                        idmap_count = int(len(idmap_df))
                        if self.structured.export_idmap:
                            idmap_csv = self.out_dir / "idmap_csv" / f"{sha[:12]}_{job.replay_path.stem}.csv"
                            idmap_jsonl = self.out_dir / "idmap_jsonl" / f"{sha[:12]}_{job.replay_path.stem}.jsonl"
                            export_id_mappings(idmap_df, csv_path=idmap_csv, jsonl_path=idmap_jsonl)
                            idmap_csv_path = str(idmap_csv)
                            idmap_jsonl_path = str(idmap_jsonl)
                        if self.structured.export_idmap_parquet:
                            idmap_parquet = self.out_dir / "idmap_parquet" / f"{sha[:12]}_{job.replay_path.stem}.parquet"
                            idmap_parquet.parent.mkdir(parents=True, exist_ok=True)
                            if not self._parquet_available:
                                warnings.append("parquet_export_idmap_skipped: missing engine")
                            else:
                                try:
                                    idmap_df.to_parquet(idmap_parquet, index=False, compression="snappy")
                                except Exception as exc:  # pragma: no cover
                                    msg = f"parquet_export_idmap_failed: {exc}"
                                    if self.structured.parquet_strict:
                                        raise RuntimeError(msg) from exc
                                    warnings.append(msg)
                                else:
                                    idmap_parquet_path = str(idmap_parquet)
                    if self.structured.export_spatial or self.structured.export_spatial_parquet:
                        spatial_df = spatial_frames_from_events(
                            events_df,
                            map_dimension=meta.map_dimension,
                            grid_size=self.structured.grid_size,
                            window_sec=self.structured.window_sec,
                        )
                        spatial_count = int(len(spatial_df))
                        if self.structured.export_spatial:
                            spatial_csv = self.out_dir / "spatial_csv" / f"{sha[:12]}_{job.replay_path.stem}.csv"
                            export_spatial_frames(spatial_df, csv_path=spatial_csv)
                            spatial_csv_path = str(spatial_csv)
                        if self.structured.export_spatial_parquet:
                            spatial_parquet = self.out_dir / "spatial_parquet" / f"{sha[:12]}_{job.replay_path.stem}.parquet"
                            spatial_parquet.parent.mkdir(parents=True, exist_ok=True)
                            if not self._parquet_available:
                                warnings.append("parquet_export_spatial_skipped: missing engine")
                            else:
                                try:
                                    spatial_df.to_parquet(spatial_parquet, index=False, compression="snappy")
                                except Exception as exc:  # pragma: no cover
                                    msg = f"parquet_export_spatial_failed: {exc}"
                                    if self.structured.parquet_strict:
                                        raise RuntimeError(msg) from exc
                                    warnings.append(msg)
                                else:
                                    spatial_parquet_path = str(spatial_parquet)

                elapsed = time.perf_counter() - t0
                return ReplayResult(
                    replay_path=key,
                    sha256=sha,
                    status="ok",
                    attempts=attempts,
                    elapsed_sec=round(elapsed, 3),
                    error=None,
                    summary_path=str(summary_path),
                    events_csv_path=events_csv_path,
                    events_jsonl_path=events_jsonl_path,
                    events_parquet_path=events_parquet_path,
                    idmap_csv_path=idmap_csv_path,
                    idmap_jsonl_path=idmap_jsonl_path,
                    idmap_parquet_path=idmap_parquet_path,
                    spatial_csv_path=spatial_csv_path,
                    spatial_parquet_path=spatial_parquet_path,
                    events_count=events_count,
                    idmap_count=idmap_count,
                    spatial_frames_count=spatial_count,
                    warnings=warnings,
                )
            except Exception as exc:  # pragma: no cover
                last_error = f"{type(exc).__name__}: {exc}"
                if attempts > self.retries:
                    break

        elapsed = time.perf_counter() - t0
        return ReplayResult(
            replay_path=key,
            sha256=sha,
            status="error",
            attempts=attempts,
            elapsed_sec=round(elapsed, 3),
            error=last_error,
            summary_path=None,
        )

    def _record_result(self, key: str, result: ReplayResult) -> None:
        entry = self._result_to_checkpoint_entry(result)
        entry["export_signature"] = self._export_signature()
        self.checkpoint["entries"][key] = entry
        self._append_result_jsonl(result)
        self._save_checkpoint()


def _read_list_file(list_file: Path) -> list[Path]:
    paths: list[Path] = []
    with list_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            paths.append(Path(line).expanduser())
    return paths


def _collect_local_replays(input_dir: Path | None, list_file: Path | None, replay_args: list[str]) -> list[Path]:
    found: list[Path] = []

    if input_dir:
        found.extend(sorted(input_dir.rglob("*.aoe2record")))

    if list_file:
        found.extend(_read_list_file(list_file))

    for value in replay_args:
        p = Path(value).expanduser()
        if p.is_dir():
            found.extend(sorted(p.rglob("*.aoe2record")))
        else:
            found.append(p)

    # Keep order but deduplicate same path.
    seen: set[str] = set()
    deduped: list[Path] = []
    for p in found:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped


def _download_jobs(game_ids: Iterable[int], download_dir: Path) -> list[ReplayJob]:
    jobs: list[ReplayJob] = []
    download_dir.mkdir(parents=True, exist_ok=True)
    for game_id in game_ids:
        dest = download_dir / f"AgeIIDE_Replay_{game_id}.aoe2record"
        path = download_replay(int(game_id), dest=dest)
        jobs.append(ReplayJob(source=str(game_id), replay_path=path, source_kind="download"))
    return jobs


def _extract_game_ids_from_history(payload: Any) -> list[int]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("matchHistoryStats") or payload.get("match_history_stats") or []
    if not isinstance(rows, list):
        return []
    ids: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("id") or row.get("match_id") or row.get("matchhistory_id")
        try:
            gid = int(raw)
        except Exception:
            continue
        if gid > 0:
            ids.append(gid)
    return ids


def _fetch_recent_game_ids_for_players(
    profile_ids: list[int],
    aliases: list[str],
    per_player_count: int,
    matchtype_id: int | None,
    title: str = "age2",
) -> list[int]:
    endpoint = "https://aoe-api.reliclink.com/community/leaderboard/getRecentMatchHistory"
    all_ids: list[int] = []

    # Resolve by profile IDs.
    for pid in profile_ids:
        params: dict[str, str] = {
            "title": title,
            "profile_ids": json.dumps([int(pid)]),
        }
        if matchtype_id is not None:
            params["matchtype_id"] = str(int(matchtype_id))
        resp = requests.get(endpoint, params=params, timeout=45)
        resp.raise_for_status()
        ids = _extract_game_ids_from_history(resp.json())[:per_player_count]
        all_ids.extend(ids)

    # Resolve by aliases (player names).
    for alias in aliases:
        a = alias.strip()
        if not a:
            continue
        params = {
            "title": title,
            "aliases": json.dumps([a]),
        }
        if matchtype_id is not None:
            params["matchtype_id"] = str(int(matchtype_id))
        resp = requests.get(endpoint, params=params, timeout=45)
        resp.raise_for_status()
        ids = _extract_game_ids_from_history(resp.json())[:per_player_count]
        all_ids.extend(ids)

    # Keep order, dedupe.
    seen: set[int] = set()
    deduped: list[int] = []
    for gid in all_ids:
        if gid in seen:
            continue
        seen.add(gid)
        deduped.append(gid)
    return deduped


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch runner for AoE2 replay parsing")
    parser.add_argument("replays", nargs="*", help="Replay files or directories")
    parser.add_argument("--input-dir", help="Directory to scan recursively for .aoe2record files")
    parser.add_argument("--list-file", help="Text file with replay paths (one per line)")
    parser.add_argument("--game-ids", nargs="*", type=int, default=[], help="Optional game IDs to download and parse")
    parser.add_argument(
        "--player-profile-ids",
        nargs="*",
        type=int,
        default=[],
        help="Fetch recent matches for these profile IDs and download by game ID",
    )
    parser.add_argument(
        "--player-aliases",
        nargs="*",
        default=[],
        help="Fetch recent matches for these player aliases and download by game ID",
    )
    parser.add_argument(
        "--per-player-count",
        type=int,
        default=5,
        help="How many recent matches to fetch per player (default: 5)",
    )
    parser.add_argument(
        "--player-matchtype-id",
        type=int,
        default=None,
        help="Optional matchtype_id filter for recent player matches",
    )
    parser.add_argument("--download-dir", default="downloads", help="Directory for downloaded replays")

    parser.add_argument("--out-dir", default="batch_out", help="Output directory for summaries and reports")
    parser.add_argument("--checkpoint", default="", help="Checkpoint file path (default: <out-dir>/checkpoint.json)")
    parser.add_argument("--retries", type=int, default=2, help="Retries per replay on parse errors")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue even when a replay fails")
    parser.add_argument("--strict", action="store_true", help="Stop on first parse error")
    parser.add_argument("--no-dedupe", action="store_true", help="Disable SHA-256 dedupe")
    parser.add_argument("--dry-run", action="store_true", help="Discover and schedule jobs without parsing")
    parser.add_argument("--report-every", type=int, default=10, help="Print progress every N jobs")
    parser.add_argument("--export-events", action="store_true", help="Export canonical events per replay (CSV+JSONL)")
    parser.add_argument("--export-spatial", action="store_true", help="Export spatial frames CSV per replay")
    parser.add_argument("--export-idmap", action="store_true", help="Export replay-derived id mapping per replay (CSV+JSONL)")
    parser.add_argument("--export-events-parquet", action="store_true", help="Export canonical events Parquet per replay")
    parser.add_argument("--export-spatial-parquet", action="store_true", help="Export spatial frames Parquet per replay")
    parser.add_argument("--export-idmap-parquet", action="store_true", help="Export replay-derived id mapping Parquet per replay")
    parser.add_argument("--merge-idmap", action="store_true", help="After batch, merge idmap files into canonical mapping by patch")
    parser.add_argument("--parquet-strict", action="store_true", help="Fail replay if Parquet export fails")
    parser.add_argument("--grid-size", type=int, default=32, help="Grid resolution for spatial export")
    parser.add_argument("--window-sec", type=int, default=10, help="Window size in seconds for spatial export")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    out_dir = Path(args.out_dir).expanduser()
    checkpoint_path = Path(args.checkpoint).expanduser() if args.checkpoint else (out_dir / "checkpoint.json")

    local = _collect_local_replays(
        input_dir=Path(args.input_dir).expanduser() if args.input_dir else None,
        list_file=Path(args.list_file).expanduser() if args.list_file else None,
        replay_args=args.replays,
    )
    jobs = [ReplayJob(source=str(p), replay_path=p, source_kind="local") for p in local]

    if args.game_ids:
        jobs.extend(_download_jobs(args.game_ids, Path(args.download_dir).expanduser()))
    player_profile_ids = [int(x) for x in (args.player_profile_ids or [])]
    player_aliases = [str(x) for x in (args.player_aliases or [])]
    if player_profile_ids or player_aliases:
        recent_ids = _fetch_recent_game_ids_for_players(
            profile_ids=player_profile_ids,
            aliases=player_aliases,
            per_player_count=max(1, int(args.per_player_count)),
            matchtype_id=(int(args.player_matchtype_id) if args.player_matchtype_id is not None else None),
            title="age2",
        )
        if recent_ids:
            jobs.extend(_download_jobs(recent_ids, Path(args.download_dir).expanduser()))
        else:
            print("[warn] No se encontraron partidas recientes para los jugadores especificados.")

    if not jobs:
        raise SystemExit(
            "No input replays found. Use --input-dir, --list-file, replays, --game-ids, "
            "or --player-profile-ids/--player-aliases."
        )

    continue_on_error = bool(args.continue_on_error or (not args.strict))

    runner = BatchRunner(
        out_dir=out_dir,
        checkpoint_path=checkpoint_path,
        retries=args.retries,
        continue_on_error=continue_on_error,
        strict=bool(args.strict),
        dedupe=(not args.no_dedupe),
        dry_run=bool(args.dry_run),
        report_every=args.report_every,
        structured=StructuredExportConfig(
            export_events=bool(args.export_events),
            export_spatial=bool(args.export_spatial),
            export_events_parquet=bool(args.export_events_parquet),
            export_spatial_parquet=bool(args.export_spatial_parquet),
            export_idmap=bool(args.export_idmap),
            export_idmap_parquet=bool(args.export_idmap_parquet),
            merge_idmap=bool(args.merge_idmap),
            parquet_strict=bool(args.parquet_strict),
            grid_size=int(args.grid_size),
            window_sec=int(args.window_sec),
        ),
    )
    report = runner.run(jobs)

    print(json.dumps({
        "job_id": report["job_id"],
        "stats": report["stats"],
        "elapsed_sec": report["elapsed_sec"],
        "throughput_replays_per_min": report["throughput_replays_per_min"],
        "report_path": runner.report_path.as_posix(),
        "idmap_merge": report.get("idmap_merge"),
    }, indent=2, ensure_ascii=True))

    if args.strict and report["stats"].get("error", 0) > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
