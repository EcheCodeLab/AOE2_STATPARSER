# Dataset Layout, Partitioning and Compression

Status: baseline strategy for Part 3 (`P3-012`, `P3-013`, `P3-014`).

## Partitioning Strategy

Primary partition dimensions:
- `event_date` (ingest/export date, `YYYY-MM-DD`)
- `map_name` (sanitized map string)
- `elo_bucket` (when available; otherwise `unknown`)

Secondary dimensions:
- `schema_version`
- `parser_version`
- `match_id`

Rationale:
- `event_date` supports incremental daily ingestion and backfills.
- `map_name` is a high-value analytical filter.
- `elo_bucket` supports cohort analysis for ML/analytics.

## Path Convention

Canonical relative path:

`<table>/schema_version=<schema>/parser_version=<parser>/event_date=<YYYY-MM-DD>/map_name=<map>/elo_bucket=<bucket>/match_id=<match_id>/`

Examples:
- `events_raw/schema_version=1.0.0/parser_version=sprint-1.1/event_date=2026-03-03/map_name=Arabia/elo_bucket=1400_1599/match_id=AgeIIDE_Replay_396581946/`
- `spatial_frames/schema_version=1.0.0/parser_version=sprint-1.1/event_date=2026-03-03/map_name=Arena/elo_bucket=unknown/match_id=AgeIIDE_Replay_111222333/`

Filename suggestion inside partition:
- `part-000.parquet` for single-file exports.
- `part-<shard>.parquet` for multi-worker exports.

## Parquet Compression Strategy

Default codec: `snappy`.

Why:
- balanced read/write performance.
- broad compatibility with `pyarrow` and `fastparquet`.
- good default for interactive analytics and iterative ETL.

Current implementation baseline:
- `aoe2stat/io.py::write_parquet` uses `compression="snappy"`.
- `aoe2stat/pipeline.py::_to_parquet` uses `compression="snappy"`.
- `aoe2_batch.py` Parquet outputs use `compression="snappy"`.

## Sanitization Rules

Partition values should be sanitized before building paths:
- keep `[A-Za-z0-9._-]`
- replace other characters with `_`
- empty values -> `unknown`

Reference helper:
- `aoe2stat/io.py::sanitize_partition_value`
- `aoe2stat/io.py::dataset_relpath`
