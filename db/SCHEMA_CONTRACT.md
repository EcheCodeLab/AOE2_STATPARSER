# Schema Contract (v1.0.0)

Purpose: define data contracts for storage/export with explicit types, nullability, units, and logical keys.

Scope: `matches`, `players`, `events_raw`, `metrics_timeseries`, `labels_ml`, `spatial_frames` from `db/supabase_schema.sql`.

Current versions:
- `schema_version`: `1.0.0`
- `parser_version` default in DB: `sprint-1.1`

## Logical Keys

- `matches`: unique `(match_id, parser_version)`
- `players`: unique `(match_id, parser_version, player_id)`
- `events_raw`: unique `(match_id, parser_version, event_id)`
- `metrics_timeseries`: unique `(match_id, parser_version, metric_name, metric_scope, player_id, time_bin_sec, window_sec)`
- `labels_ml`: unique `(match_id, parser_version, label_name, player_id, time_bin_sec, horizon_sec)`
- `spatial_frames`: unique `(match_id, parser_version, time_bin_sec, window_sec, grid_size, player_id, action_family, cell_x, cell_y)`

Logical FK relationships (not enforced physically yet):
- `players.(match_id, parser_version)` -> `matches.(match_id, parser_version)`
- `events_raw.(match_id, parser_version)` -> `matches.(match_id, parser_version)`
- `metrics_timeseries.(match_id, parser_version)` -> `matches.(match_id, parser_version)`
- `labels_ml.(match_id, parser_version)` -> `matches.(match_id, parser_version)`
- `spatial_frames.(match_id, parser_version)` -> `matches.(match_id, parser_version)`

## Table: `matches`

| Column | Type | Null | Unit/Domain | Notes |
|---|---|---|---|---|
| `id` | `bigserial` | no | surrogate key | physical PK |
| `match_id` | `text` | no | replay stem / match identifier | stable match key within parser scope |
| `replay_path` | `text` | yes | filesystem path | source path at ingest time |
| `duration_sec` | `double precision` | no | seconds | total match duration |
| `map_name` | `text` | yes | AoE2 map name | may be missing in malformed payloads |
| `map_dimension` | `double precision` | yes | map tiles | used for spatial normalization |
| `parser_version` | `text` | no | parser tag | default `sprint-1.1` |
| `schema_version` | `text` | no | schema tag | default `1.0.0` |
| `created_at` | `timestamptz` | no | UTC timestamp | insertion timestamp |

## Table: `players`

| Column | Type | Null | Unit/Domain | Notes |
|---|---|---|---|---|
| `id` | `bigserial` | no | surrogate key | physical PK |
| `match_id` | `text` | no | match identifier | logical FK to `matches` |
| `parser_version` | `text` | no | parser tag | default `sprint-1.1` |
| `player_id` | `integer` | no | in-match player number | usually 1..8 |
| `player_name` | `text` | no | display name | from replay metadata |
| `civilization` | `text` | yes | civ name | empty/unknown allowed |
| `color_id` | `integer` | yes | AoE2 color id | usually 1..8 |
| `created_at` | `timestamptz` | no | UTC timestamp | insertion timestamp |

## Table: `events_raw`

| Column | Type | Null | Unit/Domain | Notes |
|---|---|---|---|---|
| `id` | `bigserial` | no | surrogate key | physical PK |
| `match_id` | `text` | no | match identifier | logical FK to `matches` |
| `parser_version` | `text` | no | parser tag | default `sprint-1.1` |
| `event_id` | `integer` | no | sequence index | unique per `(match_id, parser_version)` |
| `t_ms` | `integer` | no | milliseconds | game timeline |
| `time_sec` | `double precision` | no | seconds | `t_ms / 1000` representation |
| `player_id` | `integer` | yes | in-match player number | nullable for global/system events |
| `player_name` | `text` | yes | display name | nullable with unknown player |
| `action_type` | `text` | no | action label | raw/normalized type |
| `action_family` | `text` | no | enum-like category | `movement`, `build`, `production`, `research`, `economy`, `military`, `other` |
| `x` | `double precision` | yes | map tiles | nullable if event has no position |
| `y` | `double precision` | yes | map tiles | nullable if event has no position |
| `payload_json` | `jsonb` | yes | JSON object | raw action payload snapshot |
| `created_at` | `timestamptz` | no | UTC timestamp | insertion timestamp |

## Table: `spatial_frames`

| Column | Type | Null | Unit/Domain | Notes |
|---|---|---|---|---|
| `id` | `bigserial` | no | surrogate key | physical PK |
| `match_id` | `text` | no | match identifier | logical FK to `matches` |
| `parser_version` | `text` | no | parser tag | default `sprint-1.1` |
| `time_bin_sec` | `integer` | no | seconds | left edge of temporal bin |
| `window_sec` | `integer` | no | seconds | aggregation window size |
| `grid_size` | `integer` | no | cells per axis | NxN grid resolution |
| `player_id` | `integer` | yes | in-match player number | nullable for future aggregate modes |
| `player_name` | `text` | yes | display name | nullable when player unknown |
| `action_family` | `text` | no | category | same family set as `events_raw` |
| `cell_x` | `integer` | no | cell index | range `[0, grid_size-1]` |
| `cell_y` | `integer` | no | cell index | range `[0, grid_size-1]` |
| `event_count` | `integer` | no | count | events per cell/bin |
| `created_at` | `timestamptz` | no | UTC timestamp | insertion timestamp |

## Table: `metrics_timeseries`

| Column | Type | Null | Unit/Domain | Notes |
|---|---|---|---|---|
| `id` | `bigserial` | no | surrogate key | physical PK |
| `match_id` | `text` | no | match identifier | logical FK to `matches` |
| `parser_version` | `text` | no | parser tag | default `sprint-1.1` |
| `metric_name` | `text` | no | metric identifier | e.g. `apm`, `idle_tc_cum`, `villager_count` |
| `metric_scope` | `text` | no | `player` or `match` | scope discriminator |
| `player_id` | `integer` | no | player id or `0` | `0` for match-level metrics |
| `time_bin_sec` | `integer` | no | seconds | left edge of metric bin |
| `window_sec` | `integer` | no | seconds | aggregation window (`0` for point-in-time) |
| `metric_value` | `double precision` | no | metric-dependent | numeric metric value |
| `metric_unit` | `text` | yes | unit label | e.g. `count`, `sec`, `apm`, `ratio` |
| `confidence` | `text` | yes | quality flag | e.g. `high`, `medium`, `low` |
| `created_at` | `timestamptz` | no | UTC timestamp | insertion timestamp |

## Table: `labels_ml`

| Column | Type | Null | Unit/Domain | Notes |
|---|---|---|---|---|
| `id` | `bigserial` | no | surrogate key | physical PK |
| `match_id` | `text` | no | match identifier | logical FK to `matches` |
| `parser_version` | `text` | no | parser tag | default `sprint-1.1` |
| `label_name` | `text` | no | target identifier | e.g. `next_macro_action` |
| `label_value` | `text` | no | target value | class/value at `(time_bin_sec, horizon_sec)` |
| `label_class` | `text` | yes | coarse class | optional grouped label taxonomy |
| `player_id` | `integer` | no | player id or `0` | `0` for match-level labels |
| `time_bin_sec` | `integer` | no | seconds | observation time anchor |
| `horizon_sec` | `integer` | no | seconds | future prediction horizon |
| `source` | `text` | yes | label source | rule/model/manual identifier |
| `created_at` | `timestamptz` | no | UTC timestamp | insertion timestamp |

## Integrity Rules (Contract-Level)

- `t_ms >= 0`, `time_sec >= 0`.
- `event_id` must be deterministic per parser run and monotonic in extraction order.
- `event_count >= 0`.
- `window_sec >= 0` for metric tables (`0` allowed for point-like snapshots).
- `grid_size >= 4`, `window_sec >= 1`.
- if both `x` and `y` are present, they are interpreted in map-tile coordinates.

## Compatibility Notes

- Consumers should join by `(match_id, parser_version)`.
- `schema_version` identifies structural contract level.
- New nullable columns are backward-compatible for `1.x`.
