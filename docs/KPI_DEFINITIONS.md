# KPI Definitions (Core Analytics)

This document formalizes KPI definitions used in the current MVP parser.

Scope in this version:
- `P4-001` Idle TC (instantaneous and cumulative)
- `P4-002` Effective villager count
- `P4-003` APM bruto vs eAPM
- `P4-004` Time per age
- `P4-005` Military production uptime
- `P4-006` Floating resources by window
- `P4-007` Idle military (if applicable)
- `P4-008` Eco balance (food/wood/gold/stone)
- `P4-009` Farm efficiency
- `P4-010` Trade efficiency (team games)
- `P4-011` Scouting coverage
- `P4-012` Early pressure/aggression
- `P4-013` Power spike by tech/unit timing
- `P4-016` Confidence intervals for approximate metrics
- `P4-017` KPI quality flag (`high/medium/low confidence`)

References in code:
- `aoe2stat/metrics.py` (`tc_idle_time`, `tc_idle_cumulative_timeseries`, `apm_timeseries`)
- `aoe2stat/kpis.py` (`kpis_by_window`, `kpis_at_minute`)

## P4-001 Idle TC (instantaneous and cumulative)

### Input signals
- Player production-like actions (`TRAIN`, `CREATE`, `QUEUE`, `ORDER`)
- Villager-matching payload (`villager|aldean`)
- Action timestamp in seconds

### Parameters (current defaults)
- `base_prod_time_sec = 25.0`
- `gap_threshold_sec = 27.0`

### Instantaneous idle increment
For two consecutive villager-train timestamps `t_prev` and `t_curr`:

- `gap = t_curr - t_prev`
- If `gap > gap_threshold_sec`, then:
  - `idle_increment_sec = max(0, gap - base_prod_time_sec)`
- Else:
  - `idle_increment_sec = 0`

### Cumulative idle
- `idle_tc_cum_sec(t) = sum(idle_increment_sec_i)` for all increments up to time `t`.

### Units
- Seconds (`sec`)

### Quality note
- This is an approximation derived from villager creation timing, not direct TC state packets.

## P4-002 Effective villager count

### Definition objective
Represent the villager workforce that is effectively available for economy decisions at each analysis point.

### Current MVP estimator
- Base signal: villager creation actions detected from payload match (`villager|aldean`).
- Let `v_created_cum(t)` be cumulative villagers created by player until time `t`.
- MVP effective villager count:
  - `villager_effective(t) = v_created_cum(t)`

### Extended target definition (future)
When richer signals are available, effective count should be:
- `villager_effective(t) = v_alive(t) - v_idle_long(t) - v_garrisoned_nonworking(t)`

Where:
- `v_alive(t)` = villagers alive at `t`
- `v_idle_long(t)` = villagers idle beyond threshold
- `v_garrisoned_nonworking(t)` = villagers temporarily removed from eco tasks

### Units
- Number of villagers (`count`)

### Quality note
- MVP does not subtract deaths, idling, or garrisoning effects due to limited direct state extraction.

## P4-003 APM bruto vs eAPM

### APM bruto (implemented)
For each player and analysis window `window_sec`:

- `actions_in_window = count(player actions in [t, t + window_sec))`
- `apm_bruto = actions_in_window * 60 / window_sec`

### eAPM (not yet implemented in MVP)
Current definition contract for future implementation:

- `eAPM = effective_actions_in_window * 60 / window_sec`
- `effective_actions` should exclude low-impact/redundant commands (for example spam-reselect or repeated no-op commands), based on a deterministic action taxonomy.

### Units
- Actions per minute (`APM`)

### Current output behavior
- MVP exports only `apm_bruto`.
- Any `eAPM` field should be marked `null` or omitted until the effective-action filter is implemented.

## P4-004 Time per age

### Definition objective
Measure duration spent by player in each age segment (Dark, Feudal, Castle, Imperial).

### Age transition events
- Detect research events whose tech label is one of:
  - `Feudal Age`
  - `Castle Age`
  - `Imperial Age`
- For each player:
  - `t_feudal`: first timestamp of `Feudal Age` research
  - `t_castle`: first timestamp of `Castle Age` research
  - `t_imperial`: first timestamp of `Imperial Age` research
  - `t_end`: replay/player analysis end time

### Segment durations
- `time_dark = max(0, t_feudal - 0)`
- `time_feudal = max(0, t_castle - t_feudal)`
- `time_castle = max(0, t_imperial - t_castle)`
- `time_imperial = max(0, t_end - t_imperial)`

### Fallback rules
- Missing `t_feudal`: all elapsed time remains in `Dark`.
- Missing `t_castle`: `Feudal` runs until `t_end`.
- Missing `t_imperial`: `Castle` runs until `t_end`, `Imperial = 0`.

### Units
- Seconds (`sec`) and optional normalized share (`segment_sec / t_end`).

### Quality note
- Accuracy depends on reliable extraction and normalization of age-up research labels.

## P4-005 Military production uptime

### Definition objective
Quantify how consistently military production structures are producing units over time.

### Window-based definition
For player `p` in window `w`:

- `military_prod_active_sec(p, w)`: seconds inside `w` where at least one military-production queue is active.
- `window_duration_sec = window_sec`
- `uptime_military_prod(p, w) = military_prod_active_sec(p, w) / window_duration_sec`

Bounded range:
- `uptime_military_prod in [0, 1]`

### Cumulative/match summary form
- `uptime_military_prod_match(p) = total_active_sec(p) / total_observed_sec(p)`

### MVP fallback proxy (when queue state is unavailable)
- Use military unit creation command density:
  - `uptime_military_prod_proxy(p, w) = min(1, military_create_events(p, w) / k)`
- `k` is a calibration constant documented per dataset split.

### Units
- Ratio (`0..1`) and optional percentage (`0..100%`)

### Quality note
- Exact uptime requires queue state per building; command-density proxy is medium confidence.

## P4-006 Floating resources by window

### Definition objective
Estimate the amount of resources a player is carrying/stockpiling over time, reported per analysis window.

### Current MVP estimator
- Uses action-derived approximation from `resource_balance_timeseries(...)`.
- Per resource `r in {food, wood, gold, stone}`:
  - `floating_r(t) = start_r + cumulative_sum(window_delta_r up to t)`
  - `window_delta_r` is inferred from spend-like actions and market operations (`BUY`/`SELL`).
- Total floating proxy:
  - `floating_total(t) = floating_food(t) + floating_wood(t) + floating_gold(t) + floating_stone(t)`

### Window aggregation
- `t` corresponds to the start of each `window_sec` bucket.
- In outputs, each point represents the state after accumulating all deltas up to that bucket.

### Units
- Resource units (game resource points)

### Quality note
- This is an approximation and does not include direct gather/deposit sync at full fidelity.
- Should be tagged as medium/low confidence until sync-driven estimator is fully integrated.

## P4-007 Idle military (if applicable)

### Definition objective
Measure military potential that is inactive (not executing productive combat/movement/stance goals) for prolonged periods.

### Entity-level conceptual definition
For each military unit `u` and time `t`:
- `is_idle_military(u, t) = 1` if unit is alive and not in active command state.

Per player and window:
- `idle_military_ratio(p, w) = idle_military_unit_seconds(p, w) / alive_military_unit_seconds(p, w)`

Bounded range:
- `idle_military_ratio in [0, 1]`

### MVP applicability gate
- If per-unit state is unavailable, metric is optional and should be flagged `not_computable`.
- Temporary proxy (low confidence):
  - infer from long gaps between military commands while military unit count is estimated > 0.

### Units
- Ratio (`0..1`) and optional percentage (`0..100%`)

### Quality note
- This KPI is highly sensitive to missing unit-state telemetry and should be labeled low confidence in proxy mode.

## P4-008 Eco balance (food/wood/gold/stone)

### Per-resource eco balance
For each player, window `t`, and resource `r`:

- `eco_balance_r(t) = start_r + income_r_cum(t) - spend_r_cum(t) + market_delta_r_cum(t)`

MVP fallback when `income_r_cum` is unavailable:
- Approximate with action-derived deltas only:
  - `eco_balance_r_approx(t) = start_r + action_delta_r_cum(t)`

### Total eco balance
- `eco_balance_total(t) = sum_r eco_balance_r(t)` for `r in {food, wood, gold, stone}`.

### Recommended start vector (MVP)
- `start_food = 200`
- `start_wood = 200`
- `start_gold = 100`
- `start_stone = 200`

### Units
- Resource units (game resource points)

### Contract with existing code
- Per-resource approximation aligns with `resource_balance_timeseries(...)`.
- Total approximation aligns with `approximate_total_balance_timeseries(...)` and `floating_total` in `kpis_by_window(...)`.
- Any UI/report label should explicitly include `approx` when this estimator is used.

## P4-009 Farm efficiency

### Definition objective
Estimate how effectively farm-related investment is converted into sustained food economy output.

### Canonical ratio form
For player `p` over window `w`:

- `farm_efficiency(p, w) = food_income_from_farms(p, w) / farm_capacity_proxy(p, w)`

Where:
- `food_income_from_farms(p, w)` is food gathered from farms during `w`.
- `farm_capacity_proxy(p, w)` is expected farm output capacity in `w` (from active farm villager time and tech-adjusted gather rates).

### Match-level aggregate
- `farm_efficiency_match(p) = sum_w food_income_from_farms(p, w) / sum_w farm_capacity_proxy(p, w)`

### MVP fallback proxy (without gather telemetry)
- Use spend/stock proxies and farm-building events:
  - `farm_efficiency_proxy(p, w) = food_spend_proxy(p, w) / max(1, farms_built_or_estimated(p, w))`
- Must be explicitly labeled as `proxy_low_confidence`.

### Units
- Dimensionless ratio (`0..+inf`) plus optional capped score (`0..1`) for dashboards.

### Quality note
- Real efficiency requires reliable farm-specific gather attribution; proxy should not be used for strict comparisons across patches/civs.

## P4-010 Trade efficiency (team games)

### Definition objective
Measure how efficiently trade activity converts into gold gain versus expected route potential.

### Canonical ratio form
For player `p` over window `w` (team games only):

- `trade_efficiency(p, w) = gold_from_trade(p, w) / expected_trade_gold(p, w)`

Where:
- `gold_from_trade(p, w)` is observed gold credited from trade carts/cogs in `w`.
- `expected_trade_gold(p, w)` is route-length-adjusted expected gold from active trade units in `w`.

### Match-level aggregate
- `trade_efficiency_match(p) = sum_w gold_from_trade(p, w) / sum_w expected_trade_gold(p, w)`

### Applicability
- If match mode is not team game, set KPI to `not_applicable`.
- If trade telemetry is missing, set KPI to `not_computable`.

### MVP fallback proxy
- Approximate from market/trade-like action deltas where possible:
  - `trade_efficiency_proxy = trade_gold_proxy / expected_trade_gold_proxy`
- Label as `proxy_low_confidence`.

### Units
- Dimensionless ratio (`0..+inf`) and optional percentage (`ratio * 100`).

### Quality note
- Route geometry, unit pathing, and interruptions strongly affect true efficiency; proxy mode is low confidence.

## P4-011 Scouting coverage

### Definition objective
Estimate how much relevant map area/opponent information a player has explored over time.

### Canonical spatial form
For player `p` and window `w`:

- `covered_cells_unique(p, w)`: number of map grid cells observed for the first time during `w`.
- `covered_cells_cum(p, t)`: cumulative unique observed cells up to time `t`.
- `total_relevant_cells`: total map cells considered scout-relevant (optionally excluding unreachable terrain).

Coverage ratios:
- `scouting_coverage_window(p, w) = covered_cells_unique(p, w) / total_relevant_cells`
- `scouting_coverage_cum(p, t) = covered_cells_cum(p, t) / total_relevant_cells`

### Opponent-aware extension
- `enemy_scouting_coverage(p, t)` can be computed as fraction of enemy-controlled/active zones visited by `p`.

### Units
- Ratio (`0..1`) and optional percentage (`0..100%`)

### MVP fallback proxy
- If fog-of-war visibility is unavailable, proxy from movement/scout-unit trajectories and visited grid cells.
- Label proxy outputs as `proxy_medium_confidence`.

### Quality note
- Map generation and terrain accessibility influence comparability; normalize by map size and cell resolution.

## P4-012 Early pressure/aggression

### Definition objective
Quantify offensive activity intensity during early game windows.

### Time horizon
- Define early phase cutoff `t_early_end` (default suggested: `15:00` game time).

### Canonical score form
For player `p` and `t <= t_early_end`:

- `offensive_events(p)` includes attack-move, patrol-forward, military production surge, forward buildings, and combat interactions in enemy-side regions.
- Weighted pressure score:
  - `early_pressure_score(p) = sum_i weight_i * normalized_component_i(p)`

Example normalized components:
- `military_actions_rate_early`
- `forward_build_presence`
- `enemy_territory_combat_time_ratio`
- `early_military_value_produced`

### Classification form (optional)
- Map score to categorical bands:
  - `low`, `medium`, `high` aggression

### Units
- Composite score (dimensionless), plus optional category label.

### MVP fallback proxy
- If combat telemetry is partial, estimate from military command density + forward-position events.
- Label as `proxy_medium_confidence` or `proxy_low_confidence` depending on missing signals.

### Quality note
- Civilization matchups and map generation can bias aggression interpretation; recommend matchup-aware normalization for benchmarking.

## P4-013 Power spike by tech/unit timing

### Definition objective
Capture temporary strength advantages created by key technology completions and unit-composition breakpoints.

### Event-driven score
For player `p` at time `t`:

- `power_spike_score(p, t) = sum_i impact_i * exp(-(t - t_i) / tau_i) * I(t >= t_i)`

Where each trigger `i` corresponds to:
- high-impact military tech completion;
- critical unit mass reached for a composition;
- timing buildings that unlock new military options.

Parameters:
- `impact_i`: calibrated impact weight per trigger class.
- `tau_i`: decay horizon (suggested `120-240 sec`, depending on trigger).

### Practical outputs
- `first_spike_time`: first `t` where score crosses threshold `theta`.
- `peak_spike_score`: max score in match.
- `spike_area_early`: integral of score from `0` to `20 min`.

### Units
- Dimensionless score; optionally normalized to `0..1` for dashboards.

### MVP fallback proxy
- If direct unit-state mass is incomplete:
  - `power_spike_proxy = tech_completion_impact_decay + military_production_burst_proxy`
- Label as `proxy_medium_confidence`.

### Quality note
- Trigger weights must be validated per patch/civ matchup; generic calibration is ranking-oriented and not causal proof.

## P4-016 Confidence intervals for approximate metrics

### Definition objective
Attach uncertainty ranges to approximate KPIs so consumers can distinguish estimate precision.

### Applicability
Use confidence intervals for KPIs derived from proxies/partial telemetry, for example:
- `floating_total`
- `eco_balance_r_approx`
- `farm_efficiency_proxy`
- `trade_efficiency_proxy`
- `power_spike_proxy`

### Canonical interval form
For KPI estimate `k_hat` at player-window level:
- `CI_95 = [k_hat - z_0.975 * sigma_hat, k_hat + z_0.975 * sigma_hat]`
- with `z_0.975 = 1.96` and non-negative clipping when metric domain requires it.

### Sigma estimation contract
`sigma_hat` should come from one of:
- empirical residual model calibrated on validation set:
  - `sigma_hat = sigma_model(feature_context)`
- bootstrap over replay windows when enough samples exist.

Fallback when calibration is unavailable:
- use metric-class default relative error `r_default`:
  - `sigma_hat = abs(k_hat) * r_default`

### Output fields (recommended)
- `kpi_value`
- `ci_lower`
- `ci_upper`
- `ci_level` (default `0.95`)
- `ci_method` (`residual_model`, `bootstrap`, `default_relative_error`)

### Quality note
- CI quality is only as good as calibration set representativeness (patch, elo, map type, civ distribution).

## P4-017 KPI quality flag (`high/medium/low confidence`)

### Definition objective
Provide a simple reliability label per KPI point and per match aggregate.

### Label set
- `high`
- `medium`
- `low`

### Rule-based baseline mapping
At minimum, confidence should combine:
- source completeness (`telemetry_coverage`)
- proxy usage (`is_proxy`)
- CI relative width (`(ci_upper - ci_lower) / max(eps, abs(kpi_value))`)

Suggested baseline rules:
- `high`:
  - direct telemetry, no proxy, and relative CI width <= `0.20`
- `medium`:
  - mixed/direct+proxy, or relative CI width in `(0.20, 0.50]`
- `low`:
  - proxy-heavy/missing signals, or relative CI width > `0.50`

Special states:
- if KPI is not computable -> emit `not_computable` in status field and omit confidence flag.
- if KPI is not applicable (e.g., trade in 1v1) -> emit `not_applicable`.

### Output fields (recommended)
- `confidence_flag` (`high|medium|low`)
- `confidence_reason_codes` (list, e.g. `["proxy_mode", "wide_ci"]`)
- `data_quality_status` (`ok|not_computable|not_applicable`)

### Quality note
- Confidence flags are interpretability aids, not a substitute for raw KPI + CI in downstream modeling.

## Versioning

- Definition version: `kpi_defs_v8`
- Date: `2026-03-04`
