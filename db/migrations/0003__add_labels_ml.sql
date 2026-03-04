-- Add labels_ml table for supervised-learning targets.
-- Backward-compatible migration.

begin;

create table if not exists public.labels_ml (
  id bigserial primary key,
  match_id text not null,
  parser_version text not null default 'sprint-1.1',
  label_name text not null,
  label_value text not null,
  label_class text,
  player_id integer not null default 0,
  time_bin_sec integer not null,
  horizon_sec integer not null default 0,
  source text,
  created_at timestamptz not null default now(),
  unique (match_id, parser_version, label_name, player_id, time_bin_sec, horizon_sec)
);

create index if not exists idx_labels_match_time on public.labels_ml (match_id, time_bin_sec);
create index if not exists idx_labels_name_player on public.labels_ml (label_name, player_id, horizon_sec);

commit;
