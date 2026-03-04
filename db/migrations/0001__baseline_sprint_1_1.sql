-- Supabase/Postgres schema (Sprint 1.1 baseline)
-- Scope: match-level metadata, player metadata, canonical events, spatial frames.

begin;

create table if not exists public.matches (
  id bigserial primary key,
  match_id text not null,
  replay_path text,
  duration_sec double precision not null,
  map_name text,
  map_dimension double precision,
  parser_version text not null default 'sprint-1.1',
  schema_version text not null default '1.0.0',
  created_at timestamptz not null default now(),
  unique (match_id, parser_version)
);

create table if not exists public.players (
  id bigserial primary key,
  match_id text not null,
  parser_version text not null default 'sprint-1.1',
  player_id integer not null,
  player_name text not null,
  civilization text,
  color_id integer,
  created_at timestamptz not null default now(),
  unique (match_id, parser_version, player_id)
);

create table if not exists public.events_raw (
  id bigserial primary key,
  match_id text not null,
  parser_version text not null default 'sprint-1.1',
  event_id integer not null,
  t_ms integer not null,
  time_sec double precision not null,
  player_id integer,
  player_name text,
  action_type text not null,
  action_family text not null,
  x double precision,
  y double precision,
  payload_json jsonb,
  created_at timestamptz not null default now(),
  unique (match_id, parser_version, event_id)
);

create table if not exists public.spatial_frames (
  id bigserial primary key,
  match_id text not null,
  parser_version text not null default 'sprint-1.1',
  time_bin_sec integer not null,
  window_sec integer not null,
  grid_size integer not null,
  player_id integer,
  player_name text,
  action_family text not null,
  cell_x integer not null,
  cell_y integer not null,
  event_count integer not null,
  created_at timestamptz not null default now(),
  unique (match_id, parser_version, time_bin_sec, window_sec, grid_size, player_id, action_family, cell_x, cell_y)
);

create index if not exists idx_matches_match on public.matches (match_id);
create index if not exists idx_players_match on public.players (match_id, player_id);
create index if not exists idx_events_match_time on public.events_raw (match_id, t_ms);
create index if not exists idx_events_match_player_time on public.events_raw (match_id, player_id, t_ms);
create index if not exists idx_events_type on public.events_raw (action_type, action_family);
create index if not exists idx_spatial_match_time on public.spatial_frames (match_id, time_bin_sec);
create index if not exists idx_spatial_match_player on public.spatial_frames (match_id, player_id, action_family);
create index if not exists idx_spatial_grid on public.spatial_frames (grid_size, cell_x, cell_y);

commit;

