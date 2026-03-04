# Parser Source Inventory (`mgz.summary` / `mgz.fast`)

Date: `2026-03-04`  
Scope: current codebase usage inventory for Parte 2 tasks:
- `P2-001` Inventariar todo lo que hoy ya extrae `mgz.summary`
- `P2-002` Inventariar todo lo que hoy ya extrae `mgz.fast`

## `mgz.summary` Inventory (P2-001)

### Primary usage paths
- `aoe2_parser.py::parse_replay`
  - `mgz.summary.Summary(data)`
  - `summary.get_players()`
  - `summary.get_version()`
  - `summary.get_map()`
- `aoe2stat/metrics.py::resource_totals_postgame`
  - Fallback path:
    - `mgz.summary.Summary(fh)`
    - if empty players -> `mgz.summary.FullSummary(fh)`
  - Reads per-player achievements economy fields.

### Fields currently extracted from summary players/map/version
- Players:
  - `name`
  - `civilization` (numeric id in `aoe2_parser.py` summary DTO path)
  - `winner`
  - `eapm` (optional)
  - `number` (used in metrics fallback path)
  - `achievements.economy.food_collected`
  - `achievements.economy.wood_collected`
  - `achievements.economy.gold_collected`
  - `achievements.economy.stone_collected`
- Match metadata:
  - `version` (`summary.get_version()`)
  - `map.id` (`summary.get_map().get("id")`)
  - `map.name` (`summary.get_map().get("name")`)

### Notes / gaps
- Summary is used mostly for quick match/player metadata and as fallback for economy totals.
- There is no exhaustive event timeline extraction from `mgz.summary` in current pipeline.

## `mgz.fast` Inventory (P2-002)

### Primary usage paths
- `aoe2_parser.py::parse_replay`
  - `mgz.fast.postgame(data)` -> `world_time` for duration.
- `aoe2stat/metrics.py::resource_totals_postgame`
  - `mgz.fast.postgame(fh)` first-choice source for per-player collected resources.
  - Includes robust shape handling (`players`, `player`, `achievements`, `postgame`, `summary`, deep walk).
- `aoe2stat/metrics.py::sync_total_resources_timeseries`
  - `mgz.fast.start(fh)`
  - loop with `mgz.fast.operation(fh)`
  - filters `mgz.fast.Operation.SYNC`
  - reads sync payload:
    - `current_time`
    - per-player `total_res`

### Fields currently extracted from fast payloads
- Postgame:
  - `world_time` (ms)
  - per-player economy totals (food/wood/gold/stone) in multiple possible key layouts.
- Sync stream:
  - `current_time` -> time axis
  - dynamic player keys (`"1"`, `"2"`, ...)
  - `total_res` per player at sync snapshot

### Notes / gaps
- `sync_total_resources_timeseries` only consumes aggregate `total_res`; no per-resource stock split yet.
- Fast operation loop currently ignores non-`SYNC` operations for metrics path.

## Cross-check with current architecture

- Main parser pipeline (`aoe2stat/core.py` + `aoe2stat/pipeline.py`) is based on `mgz.model.parse_match`.
- `mgz.summary` and `mgz.fast` are used as complementary sources for:
  - quick replay summary output
  - postgame economy totals
  - sync-derived total resource timeline

## Suggested next technical steps (Parte 2)

1. Promote this inventory to machine-checkable tests (schema of expected fields per source path).
2. Expand `mgz.fast` parsing coverage beyond `SYNC` for richer economy/combat telemetry.
3. Reconcile duplicated metadata paths (`summary` vs `parse_match`) into one canonical extractor contract.
