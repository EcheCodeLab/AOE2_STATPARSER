-- Add metrics_timeseries table for KPI/windowed metric storage.
-- Backward-compatible migration.

begin;

create table if not exists public.metrics_timeseries (
  id bigserial primary key,
  match_id text not null,
  parser_version text not null default 'sprint-1.1',
  metric_name text not null,
  metric_scope text not null default 'player',
  player_id integer not null default 0,
  time_bin_sec integer not null,
  window_sec integer not null default 0,
  metric_value double precision not null,
  metric_unit text,
  confidence text,
  created_at timestamptz not null default now(),
  unique (match_id, parser_version, metric_name, metric_scope, player_id, time_bin_sec, window_sec)
);

create index if not exists idx_metrics_match_time on public.metrics_timeseries (match_id, time_bin_sec);
create index if not exists idx_metrics_name_scope on public.metrics_timeseries (metric_name, metric_scope, player_id);

commit;
