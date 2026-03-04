# Schema Versioning and Migrations

This document defines how to evolve `db/supabase_schema.sql` safely.

Current schema version: `1.0.0`

## Versioning Policy (`schema_version`)

Use semantic versioning:
- `MAJOR`: breaking contract changes (drop/rename column, incompatible type change).
- `MINOR`: backward-compatible additions (new nullable column, new index, new table not required by old readers).
- `PATCH`: non-contract changes (index tuning, comments, docs, non-breaking defaults).

`schema_version` must be stamped into `matches.schema_version` at ingest time.

## Migration Rules

1. Never edit historical migration SQL files.
2. Add a new migration file for each change.
3. Keep migrations idempotent when possible (`if exists` / `if not exists`).
4. Apply migrations in lexical order.
5. Update `db/supabase_schema.sql` to reflect latest state for fresh installs.
6. Update `db/SCHEMA_CONTRACT.md` whenever contract changes.

## File Layout

- `db/supabase_schema.sql`: latest bootstrap schema for empty DB.
- `db/migrations/NNNN__description.sql`: incremental migration scripts.

Suggested naming:
- `0001__baseline_sprint_1_1.sql`
- `0002__add_metrics_timeseries.sql`
- `0003__add_labels_ml.sql`
- `0004__add_events_source_lib_version.sql`

## Backward Compatibility Checklist

Before releasing a new schema version:
- Confirm readers can still load old rows.
- Confirm joins on `(match_id, parser_version)` remain valid.
- Confirm uniqueness constraints are unchanged or explicitly migrated.
- Confirm ingestion scripts are updated for new required columns.
- Confirm README and schema contract docs are updated.
