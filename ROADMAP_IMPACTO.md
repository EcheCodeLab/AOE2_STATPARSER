# Roadmap por Impacto y Desarrollo Gradual - AOE2_STATPARSER

Este roadmap ordena el desarrollo para mostrar progreso visible rapido, sin perder base tecnica para escalar.

Prioridad de producto (corto plazo):
1. Parsear bien una partida individual
2. Ver bien los datos en GUI (timeline + KPIs)
3. Fetch y almacenamiento estructurado
4. Visualizacion geografica `NxN` de dinamicas
5. Escalar a muchas partidas

Referencias: cada bloque apunta a IDs de [CHECKLIST_DESARROLLO.md](/home/echealbaposse/GIT_Codex/AOE2_STATPARSER/CHECKLIST_DESARROLLO.md).

## Fase 1 - MVP Parser Confiable (Impacto muy alto)

Objetivo: que cualquier replay individual produzca salida consistente y util.

Estado actual (2026-03-03): en progreso avanzado.
- Completado: `RawEvent` + reloj temporal (`P2-003`, `P2-005`), esquema base `matches/players/events_raw` (`P3-001..P3-003`), export estructurado CSV/JSONL/Parquet (`P6-003`).
- Pendiente clave: metadata/timelines completos (`P2-009..P2-014`), robustez de parseo (`P2-007`, `P2-021`, `P2-022`), tests de regresión (`P2-025`, `P12-003`, `P12-004`).

Tareas foco:
- [ ] Definir `RawEvent` y reloj temporal unico (P2-003, P2-005)
- [ ] Extraer metadata completa de partida/jugadores (P2-009, P2-010)
- [ ] Extraer timelines base: age ups, unidades, edificios, techs (P2-011..P2-014)
- [ ] Manejar archivos corruptos/unknown events sin romper (P2-007, P2-021, P2-022)
- [ ] Esquema minimo de tablas `matches`, `players`, `events_raw` (P3-001..P3-004)
- [ ] Tests de regresion con replays reales (P2-025, P12-003, P12-004)

Resultado visible:
- CLI parsea replay y exporta JSON/CSV estable.

## Fase 2 - GUI Fuerte para Partida Individual (Impacto muy alto)

Objetivo: inspeccionar una replay de punta a punta y entender dinamicas.

Estado actual (2026-03-03): en progreso.
- Completado: CLI unificada base (`P6-001`, `P6-002`), scrubber/bookmarks (`P6-013`, `P6-015`), export de vista/datos (`P6-014`).
- Parcial: filtros GUI (`P6-010`).
- Pendiente: panel KPI dedicado (`P6-011`) y smoke tests GUI (`P6-020`, `P12-011`).

Tareas foco:
- [ ] CLI unificada con `parse`/`inspect` (P6-001, P6-002)
- [ ] GUI: filtros por jugador/edad/evento (P6-010)
- [ ] GUI: panel KPI + series temporales (P6-011, P6-012)
- [ ] GUI: scrubber temporal + bookmarks (P6-013, P6-015)
- [ ] Export de vista y datos filtrados (P6-014)
- [ ] Smoke tests de GUI (P6-020, P12-011)

Resultado visible:
- Abris replay y ves evolucion temporal clara de Idle TC, villager count, APM, etc.

## Fase 3 - Fetch + Persistencia Estructurada (Impacto alto)

Objetivo: dejar de depender de analisis efimero y construir base historica.

Estado actual (2026-03-03): en progreso avanzado.
- Completado: export canónico en Parquet (`P3-013`, `P6-003`) y trazabilidad de versiones (`P3-009` + parser/schema version en salidas).
- Parcial: runners batch (hay implementación operativa, falta cerrar todos los ítems `P7-001..P7-003` en checklist formal).
- Pendiente: cobertura completa de validación de calidad (`P8-001..P8-006`).

Tareas foco:
- [ ] Runner para parsear carpeta/lista/IDs (P7-001..P7-003)
- [ ] Cache y dedupe por hash (P7-007, P7-008)
- [ ] Export canonico en Parquet (P3-013, P6-003)
- [ ] Integridad y calidad minima (P8-001..P8-006)
- [ ] Trazabilidad `job_id`, `parser_version`, `schema_version` (P7-013, P2-023, P3-009)

Resultado visible:
- Se puede acumular dataset local incremental sin reprocesar todo.

## Fase 4 - Base de Datos (Supabase/Postgres) para Consulta Continua (Impacto alto)

Objetivo: almacenar datos segmentados para consulta y visualizacion incremental.

Estado actual (2026-03-03): en progreso avanzado.
- Completado: DDL inicial + índices (`P4-SUPA-001`) y upserts/injest incremental+batch (`P4-SUPA-002`, `P4-SUPA-003`).
- Pendiente: vistas/materializadas para GUI y validación de consistencia Parquet vs DB.

Enfoque recomendado:
- Empezar con `Parquet` local como fuente de verdad.
- Sincronizar a Postgres/Supabase por lotes (no directo evento a evento al inicio).
- Mantener esquema versionado para evitar roturas.

Tareas foco nuevas (ejecucion sugerida):
- [ ] Definir DDL inicial para `matches`, `players`, `events_raw`, `metrics_timeseries`, `spatial_frames`
- [ ] Implementar `upsert` por `match_id` + `parser_version`
- [ ] Crear indices por `match_id`, `player_id`, `t_ms`, `event_type`
- [ ] Crear jobs de ingest incremental (N replays por lote)
- [ ] Crear vistas/materializadas para GUI (KPIs por minuto, eventos clave)
- [ ] Crear validacion de consistencia Parquet vs DB

Resultado visible:
- Cada replay parseada queda persistida y consultable por SQL/API.

## Fase 5 - Espacial NxN (Objetivo clave corto-mediano) (Impacto muy alto)

Objetivo: representar dinamicas de movimiento/creacion sin sprites.

Estado actual (2026-03-03): MVP logrado.
- Completado: grillas base (`P5-003`), visualizador NxN (`P5-014`), scrubber temporal (`P5-015`).
- Pendiente: capas espaciales avanzadas (`P5-004..P5-010`) y serialización espacial formal `NPZ`/estructura extendida (`P5-013`).

Tareas foco:
- [ ] Coordenadas normalizadas `[0,1]x[0,1]` (P5-002)
- [ ] Grillas base 16/32/64 y criterio de resolucion (P5-003)
- [ ] Heatmaps temporales: unidades propias/enemigas y edificios (P5-004..P5-006)
- [ ] Heatmap de combate/presion (P5-007, P5-009)
- [ ] `spatial_frame` serializable a Parquet/NPZ (P5-013)
- [ ] GUI con tablero `NxN` + scrubber de tiempo (P5-014, P5-015)
- [ ] Comparativa jugador A vs B superpuesta (P5-016)

Resultado visible:
- Ves el flujo geografico del match por tiempo en tablero abstracto.

## Fase 6 - Batch Masivo y Robustez Operacional (Impacto medio-alto)

Objetivo: pasar de decenas a miles de partidas sin perder calidad.

Tareas foco:
- [ ] Paralelismo configurable + control RAM (P7-004, P7-005)
- [ ] Checkpoint/reanudacion + reintentos (P7-006, P7-009)
- [ ] Reportes de cobertura/calidad por lote (P7-012, P8-010)
- [ ] Benchmarks 100/1000 replays (P7-016, P7-017)

Resultado visible:
- Pipeline estable para coleccion de dataset a escala.

## Fase 7 - Dataset ML y Primeros Baselines (Impacto medio)

Objetivo: conectar parser+espacial con prediccion util.

Tareas foco:
- [ ] Definir labels de accion futura (+30s, +60s) (P9-001..P9-004)
- [ ] Generador de labels + splits sin leakage (P9-006, P9-008, P9-009)
- [ ] Baselines logistic/rf/xgb y temporal simple (P10-002..P10-004)
- [ ] Metricas por civ/matchup/etapa (P10-006..P10-008)

Resultado visible:
- Primer modelo que predice acciones futuras por ventana temporal.

## Orden sugerido para varias IAs en paralelo (sin pisarse)

1. IA-A: Fase 1 (parser core) + tests parser
2. IA-B: Fase 2 (GUI individual)
3. IA-C: Fase 3 (batch + export Parquet)
4. IA-D: Fase 5 (espacial NxN)
5. IA-E: Fase 4 (DB Supabase/Postgres ingest)
6. IA-F: Fase 8 calidad transversal (P8 + P12)

Regla practica:
- No arrancar Fase 7 (ML) hasta cerrar Fase 1 + Fase 5 en estado usable.

## Definicion de "Listo para Demo Corta"

Checklist minimo (estado 2026-03-03):
- [x] Parser estable para replay individual (MVP)
- [~] GUI con KPIs y timeline util
- [x] Export estructurado a Parquet
- [x] Tablero NxN con reproduccion temporal
- [x] Persistencia incremental en DB (al menos `matches`, `players`, `events_raw`)
