# Checklist Maestro de Desarrollo - AOE2_STATPARSER

Objetivo: dejar el proyecto listo para parseo robusto, analitica temporal/espacial, escalado masivo y base para IA predictiva.

Roadmap recomendado por impacto y etapas: [ROADMAP_IMPACTO.md](/home/echealbaposse/GIT_Codex/AOE2_STATPARSER/ROADMAP_IMPACTO.md)

Convencion sugerida:
- `[ ]` pendiente
- `[~]` en progreso
- `[x]` completado
- `Owner:` IA/persona asignada
- `Bloquea:` IDs de tareas que dependen de esta

## Trabajo en curso (coordinar antes de tocar)

Fecha de inicio: 2026-03-03

- [x] P2-003 Diseñar `RawEvent` canónico: `match_id, t_ms, player, event_type, payload` (Owner: Codex, MVP en `aoe2stat/pipeline.py`)
- [x] P2-001 Inventariar todo lo que hoy ya extrae `mgz.summary` (Owner: Codex, `docs/PARSER_SOURCE_INVENTORY.md`)
- [x] P2-002 Inventariar todo lo que hoy ya extrae `mgz.fast` (Owner: Codex, `docs/PARSER_SOURCE_INVENTORY.md`)
- [x] P2-005 Unificar reloj temporal (ms, segundos de juego, tiempo real) (Owner: Codex, MVP `t_ms` + `time_sec`)
- [x] P2-009 Extraer metadata completa de partida (mapa, modo, patch, seeds si existen) (Owner: Codex, enriquecido en `aoe2stat/pipeline.py::build_match_meta`)
- [x] P2-010 Extraer metadata completa de jugadores (civ, team, color, rating si disponible) (Owner: Codex, enriquecido en `aoe2stat/pipeline.py::build_match_meta`)
- [x] P3-003 Definir esquema de tabla `events_raw` (Owner: Codex, MVP columnas exportables CSV/JSONL)
- [x] P6-003 Agregar salida CSV/Parquet por flags (Owner: Codex, CSV/JSONL/Parquet por flags; Parquet requiere `pyarrow` o `fastparquet`)
- [x] P6-009 GUI: selector de replay individual y carpeta de replays (Owner: Codex, menú + navegación anterior/siguiente)
- [x] P6-001 Definir comando CLI principal con subcomandos (`parse`, `metrics`, `batch`, `inspect`) (Owner: Codex, implementado en `aoe2_cli.py`)
- [x] P6-002 Agregar salida JSON compacta y JSON detallada (Owner: Codex, implementado en `aoe2_cli.py` con `--json {compact,detailed}`)
- [x] P6-004 Agregar `--schema-version` y `--parser-version` en salida (Owner: Codex, implementado en `aoe2_cli.py` + bloque `meta`)
- [x] P6-005 Agregar `--strict` para fallar ante warnings severos (Owner: Codex, implementado en `aoe2_cli.py` con severidad `severe`)
- [x] P4-014 Crear calculadora de KPIs por ventana configurable (Owner: Codex, `aoe2stat/kpis.py::kpis_by_window` + integración en `aoe2_cli.py metrics`)
- [x] P4-015 Crear calculadora de KPIs acumulados al minuto N (Owner: Codex, `aoe2stat/kpis.py::kpis_at_minute` + integración en `aoe2_cli.py metrics`)
- [x] P4-001 Formalizar definicion de Idle TC (instantaneo y acumulado) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v1`)
- [x] P4-003 Formalizar definicion de APM bruto vs eAPM (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v1`)
- [x] P4-006 Formalizar definicion de floating resources por ventana (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v2`)
- [x] P4-008 Formalizar definicion de eco balance (food/wood/gold/stone) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v2`)
- [x] P4-002 Formalizar definicion de villager count efectivo (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v3`)
- [x] P4-004 Formalizar definicion de tiempo en cada edad (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v3`)
- [x] P4-005 Formalizar definicion de uptime de produccion militar (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v4`)
- [x] P4-007 Formalizar definicion de idle military (si aplica) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v4`)
- [x] P4-009 Formalizar definicion de eficiencia de granjas (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v5`)
- [x] P4-010 Formalizar definicion de trade efficiency (TG) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v5`)
- [x] P4-011 Formalizar definicion de scouting coverage (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v7`)
- [x] P4-012 Formalizar definicion de presion/agresion temprana (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v7`)
- [x] P4-016 Agregar intervalos de confianza para metricas aproximadas (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v8`)
- [x] P4-017 Agregar bandera de calidad por KPI (`high/medium/low confidence`) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v8`)
- [~] P6-010 GUI: panel de filtros por jugador/edad/tipo evento (Owner: Codex, implementado en tab Mapa NxN; en curso limpieza de redundancia entre pestañas)
- [x] P6-013 GUI: bookmarks de timestamps relevantes (Owner: Codex, alta/salto/eliminación/limpieza en tab Mapa)
- [x] P6-014 GUI: exportar gráfico y exportar datos filtrados (Owner: Codex, export PNG/CSV por pestaña activa)
- [x] P6-015 GUI: reproducir timeline a velocidad variable (Owner: Codex, play/pausa + velocidades 0.5x/1x/2x/4x)
- [~] P2-004 Diseñar `RawSnapshot` canónico para estados por tick/ventana (Owner: Codex, en implementación en `aoe2stat/pipeline.py`)
- [~] P2-011 Extraer timeline de age ups (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-012 Extraer timeline de creacion de unidades (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-013 Extraer timeline de construccion de edificios (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-014 Extraer timeline de investigaciones tecnologicas (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-015 Extraer eventos de combate (daño, muertes, trades cuando aplique) (Owner: Codex, baseline por clasificación de comandos en `aoe2stat/pipeline.py`)
- [~] P2-016 Extraer eventos de economia (gather/deposit cuando sea posible) (Owner: Codex, baseline por `action_family=economy` en `aoe2stat/pipeline.py`)
- [~] P2-017 Extraer eventos de comandos del jugador (inputs/APM base) (Owner: Codex, baseline `player_commands` en `aoe2stat/pipeline.py`)
- [~] P2-018 Extraer posiciones x/y de entidades y/o eventos (Owner: Codex, en integración `spatial_events` en payload estructurado)
- [~] P2-025 Escribir tests de regresion con replays reales pequeños (Owner: Codex, en implementación `tests/test_part2_regression.py`)
- [x] P6-012 GUI: overlay de eventos sobre series de tiempo (Owner: Codex, toggle global en menú Ver)
- [x] P7-003 Implementar runner batch por IDs (descarga + parse) (Owner: Codex, extendido con fetch reciente por jugador alias/profile_id)
- [x] P5-010 Generar trayectorias agregadas por tipo de unidad (Owner: Codex, baseline visual cinemático en `gui/window.py` con trails + glow + loop)
- [x] P5-003 Definir grillas base (16x16, 32x32, 64x64) y criterio de eleccion (Owner: Codex, MVP con selector en GUI)
- [x] P5-014 Crear visualizador de grilla en GUI (Owner: Codex, MVP heatmap NxN)
- [x] P5-015 Crear reproductor temporal con scrubber de tiempo (Owner: Codex, MVP slider por segundos)
- [x] P5-016 Permitir superponer 2 jugadores en capas separadas (Owner: Codex, `overlay_player_layers` en `aoe2stat/spatial.py`)
- [x] P5-020 Escribir tests de consistencia espacial (bordes, simetria, escalado) (Owner: Codex, `tests/test_spatial_consistency.py`)
- [x] P3-001 Definir esquema de tabla `matches` (Owner: Codex, `db/supabase_schema.sql`)
- [x] P3-002 Definir esquema de tabla `players` (Owner: Codex, `db/supabase_schema.sql`)
- [x] P3-004 Definir esquema de tabla `metrics_timeseries` (Owner: Codex, `db/supabase_schema.sql` + `db/migrations/0002__add_metrics_timeseries.sql`)
- [x] P3-005 Definir esquema de tabla `spatial_frames` (Owner: Codex, `db/supabase_schema.sql`)
- [x] P3-006 Definir esquema de tabla `labels_ml` (Owner: Codex, `db/supabase_schema.sql` + `db/migrations/0003__add_labels_ml.sql`)
- [x] P3-007 Documentar tipos, nullabilidad y unidades de cada columna (Owner: Codex, `db/SCHEMA_CONTRACT.md`)
- [x] P3-008 Definir claves primarias y foráneas lógicas (Owner: Codex, `db/SCHEMA_CONTRACT.md`)
- [x] P3-009 Definir versionado de esquema (`schema_version`) (Owner: Codex, `db/MIGRATIONS.md`)
- [x] P3-010 Definir migraciones de esquema (Owner: Codex, `db/migrations/0001__baseline_sprint_1_1.sql` + `db/MIGRATIONS.md`)
- [x] P3-015 Generar diccionario de datos legible para humanos (Owner: Codex, `db/SCHEMA_CONTRACT.md`)
- [x] P3-011 Definir validaciones de integridad por tabla (Owner: Codex, `aoe2stat/validation.py` + `aoe2stat/services.py`)
- [x] P3-012 Definir estrategia de particionado de archivos (por fecha/mapa/elo) (Owner: Codex, `db/DATASET_LAYOUT.md`)
- [x] P3-013 Definir estrategia de compresión (Parquet codec) (Owner: Codex, `snappy` en `aoe2stat/io.py`, `aoe2stat/pipeline.py`, `aoe2_batch.py`)
- [x] P3-014 Definir convencion de rutas de dataset en disco (Owner: Codex, `db/DATASET_LAYOUT.md` + helper `aoe2stat/io.py::dataset_relpath`)
- [x] P4-SUPA-001 Crear DDL inicial para Supabase/Postgres + índices (Owner: Codex, `db/supabase_schema.sql`)
- [x] P4-SUPA-002 Implementar ingest incremental a Postgres/Supabase con upsert por `match_id + parser_version` (Owner: Codex, `aoe2_ingest_postgres.py`)
- [x] P4-SUPA-003 Implementar ingest batch a Postgres/Supabase (carpeta/lista + reintentos + continue-on-error) (Owner: Codex, `aoe2_ingest_batch_postgres.py`)
- [x] P1-002 Crear modulo `io` para lectura/escritura de formatos (Owner: Codex, `aoe2stat/io.py`)
- [x] P1-003 Crear modulo `schema` con dataclasses o modelos tipados (Owner: Codex, `aoe2stat/schema.py`)
- [x] P1-004 Crear modulo `features` para KPIs derivados (Owner: Codex, `aoe2stat/features.py`)
- [x] P1-005 Crear modulo `spatial` para representaciones de mapa/grilla (Owner: Codex, `aoe2stat/spatial.py`)
- [x] P1-006 Crear modulo `batch` para ejecucion masiva (Owner: Codex, `aoe2stat/batch.py`)
- [x] P1-007 Crear modulo `validation` para controles de calidad (Owner: Codex, `aoe2stat/validation.py`)
- [x] P1-009 Definir capa de servicios reutilizable por GUI y CLI (Owner: Codex, `aoe2stat/services.py` + uso en `aoe2_parser.py`)
- [x] P1-014 Definir estrategia de configuracion centralizada (yaml/toml/env) (Owner: Codex, baseline env en `aoe2stat/config.py`)
- [x] P1-015 Definir interfaz estable para plugins de features (Owner: Codex, `FeaturePlugin` + `FeatureRegistry`)
- [x] P1-008 Reducir logica duplicada entre CLI, notebook y GUI (Owner: Codex, `ReplayAnalysisService` integrado en CLI e ingest + helper notebook)
- [x] P1-001 Separar claramente parser crudo, transformaciones y visualizacion (Owner: Codex, `aoe2stat/layers.py` + `docs/ARCHITECTURE_LAYERS.md`)

## Parte 0 - Alineacion funcional y alcance

- [ ] P0-001 Definir lista exacta de casos de uso de corto plazo (analisis manual de pocas repeticiones)
- [ ] P0-002 Definir lista exacta de casos de uso de mediano plazo (batch de miles de partidas)
- [ ] P0-003 Definir lista exacta de casos de uso de largo plazo (entrenamiento IA predictiva)
- [ ] P0-004 Definir metricas de exito por horizonte (precision parser, throughput, latencia, UX)
- [ ] P0-005 Definir versiones soportadas de AoE2 DE y variaciones de replay
- [ ] P0-006 Definir tamano maximo esperado de replay y presupuesto de memoria por proceso
- [ ] P0-007 Definir politicas de compatibilidad hacia atras para formato de salida
- [ ] P0-008 Definir taxonomia inicial de eventos (economia, militar, exploracion, tecnologia)
- [ ] P0-009 Definir criterio de "dato confiable" vs "dato aproximado"
- [ ] P0-010 Definir backlog priorizado por impacto vs esfuerzo

## Parte 1 - Arquitectura de codigo y modulos

- [x] P1-001 Separar claramente parser crudo, transformaciones y visualizacion
- [x] P1-002 Crear modulo `io` para lectura/escritura de formatos
- [x] P1-003 Crear modulo `schema` con dataclasses o modelos tipados
- [x] P1-004 Crear modulo `features` para KPIs derivados
- [x] P1-005 Crear modulo `spatial` para representaciones de mapa/grilla
- [x] P1-006 Crear modulo `batch` para ejecucion masiva
- [x] P1-007 Crear modulo `validation` para controles de calidad
- [x] P1-008 Reducir logica duplicada entre CLI, notebook y GUI
- [x] P1-009 Definir capa de servicios reutilizable por GUI y CLI
- [ ] P1-010 Definir puntos de extension para nuevos extractores
- [ ] P1-011 Definir convencion de nombres para columnas/tablas/archivos
- [ ] P1-012 Definir politica de manejo de errores por capa
- [ ] P1-013 Definir estrategia de logging estructurado
- [x] P1-014 Definir estrategia de configuracion centralizada (yaml/toml/env)
- [x] P1-015 Definir interfaz estable para plugins de features

## Parte 2 - Parser base de replay (raw extraction)

- [x] P2-001 Inventariar todo lo que hoy ya extrae `mgz.summary` (Owner: Codex, `docs/PARSER_SOURCE_INVENTORY.md`)
- [x] P2-002 Inventariar todo lo que hoy ya extrae `mgz.fast` (Owner: Codex, `docs/PARSER_SOURCE_INVENTORY.md`)
- [x] P2-003 Diseñar `RawEvent` canónico: `match_id, t_ms, player, event_type, payload`
- [~] P2-004 Diseñar `RawSnapshot` canónico para estados por tick/ventana (Owner: Codex, en implementación en `aoe2stat/pipeline.py`)
- [x] P2-005 Unificar reloj temporal (ms, segundos de juego, tiempo real)
- [ ] P2-006 Resolver offsets de inicio/fin para partidas incompletas
- [ ] P2-007 Manejar archivos corruptos o truncados con degradación controlada
- [ ] P2-008 Manejar compresiones/formatos alternativos si aparecen
- [x] P2-009 Extraer metadata completa de partida (mapa, modo, patch, seeds si existen) (Owner: Codex, enriquecido en `aoe2stat/pipeline.py::build_match_meta`)
- [x] P2-010 Extraer metadata completa de jugadores (civ, team, color, rating si disponible) (Owner: Codex, enriquecido en `aoe2stat/pipeline.py::build_match_meta`)
- [~] P2-011 Extraer timeline de age ups (Feudal/Castle/Imperial) (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-012 Extraer timeline de creacion de unidades (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-013 Extraer timeline de construccion de edificios (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-014 Extraer timeline de investigaciones tecnologicas (Owner: Codex, en integración `aoe2stat/pipeline.py` + payload estructurado)
- [~] P2-015 Extraer eventos de combate (daño, muertes, trades cuando aplique) (Owner: Codex, baseline por clasificación de comandos en `aoe2stat/pipeline.py`)
- [~] P2-016 Extraer eventos de economia (gather/deposit cuando sea posible) (Owner: Codex, baseline por `action_family=economy` en `aoe2stat/pipeline.py`)
- [~] P2-017 Extraer eventos de comandos del jugador (inputs/APM base) (Owner: Codex, baseline `player_commands` en `aoe2stat/pipeline.py`)
- [~] P2-018 Extraer posiciones x/y de entidades y/o eventos (Owner: Codex, en integración `spatial_events` en payload estructurado)
- [ ] P2-019 Mapear IDs internos a nombres humanos (unidades, techs, edificios)
- [ ] P2-020 Mantener tabla de mapeo versionada por patch
- [ ] P2-021 Manejar eventos desconocidos sin romper pipeline
- [ ] P2-022 Agregar flag `parse_warnings` por replay
- [ ] P2-023 Agregar flag `parser_version` por output
- [ ] P2-024 Agregar flag `source_lib_version` por output
- [~] P2-025 Escribir tests de regresion con replays reales pequeños (Owner: Codex, en implementación `tests/test_part2_regression.py`)

## Parte 3 - Esquema de datos y contratos

- [x] P3-001 Definir esquema de tabla `matches`
- [x] P3-002 Definir esquema de tabla `players`
- [x] P3-003 Definir esquema de tabla `events_raw`
- [x] P3-004 Definir esquema de tabla `metrics_timeseries`
- [x] P3-005 Definir esquema de tabla `spatial_frames`
- [x] P3-006 Definir esquema de tabla `labels_ml`
- [x] P3-007 Documentar tipos, nullabilidad y unidades de cada columna
- [x] P3-008 Definir claves primarias y foráneas lógicas
- [x] P3-009 Definir versionado de esquema (`schema_version`)
- [x] P3-010 Definir migraciones de esquema
- [x] P3-011 Definir validaciones de integridad por tabla
- [x] P3-012 Definir estrategia de particionado de archivos (por fecha/mapa/elo)
- [x] P3-013 Definir estrategia de compresión (Parquet codec)
- [x] P3-014 Definir convencion de rutas de dataset en disco
- [x] P3-015 Generar diccionario de datos legible para humanos

## Parte 4 - KPIs y métricas de juego (core analytics)

- [x] P4-001 Formalizar definicion de Idle TC (instantaneo y acumulado) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v1`)
- [x] P4-002 Formalizar definicion de villager count efectivo (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v3`)
- [x] P4-003 Formalizar definicion de APM bruto vs eAPM (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v1`)
- [x] P4-004 Formalizar definicion de tiempo en cada edad (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v3`)
- [x] P4-005 Formalizar definicion de uptime de produccion militar (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v4`)
- [x] P4-006 Formalizar definicion de floating resources por ventana (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v2`)
- [x] P4-007 Formalizar definicion de idle military (si aplica) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v4`)
- [x] P4-008 Formalizar definicion de eco balance (food/wood/gold/stone) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v2`)
- [x] P4-009 Formalizar definicion de eficiencia de granjas (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v5`)
- [x] P4-010 Formalizar definicion de trade efficiency (TG) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v5`)
- [x] P4-011 Formalizar definicion de scouting coverage (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v7`)
- [x] P4-012 Formalizar definicion de presion/agresion temprana (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v7`)
- [x] P4-013 Formalizar definicion de power spike por timing tech/unit (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v7`)
- [x] P4-014 Crear calculadora de KPIs por ventana configurable (Owner: Codex, `aoe2stat/kpis.py::kpis_by_window` + integración en `aoe2_cli.py metrics`)
- [x] P4-015 Crear calculadora de KPIs acumulados al minuto N (Owner: Codex, `aoe2stat/kpis.py::kpis_at_minute` + integración en `aoe2_cli.py metrics`)
- [x] P4-016 Agregar intervalos de confianza para metricas aproximadas (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v8`)
- [x] P4-017 Agregar bandera de calidad por KPI (`high/medium/low confidence`) (Owner: Codex, `docs/KPI_DEFINITIONS.md` -> `kpi_defs_v8`)
- [ ] P4-018 Validar KPIs contra partidas revisadas manualmente
- [ ] P4-019 Documentar limites conocidos de cada KPI
- [ ] P4-020 Crear bateria de tests numericos con tolerancias

## Parte 5 - Representación espacial y abstracción del mapa

- [ ] P5-001 Definir sistema de coordenadas unico para todos los mapas
- [ ] P5-002 Normalizar coordenadas a `[0,1] x [0,1]`
- [x] P5-003 Definir grillas base (16x16, 32x32, 64x64) y criterio de eleccion
- [ ] P5-004 Generar heatmap temporal de unidades propias por celda
- [ ] P5-005 Generar heatmap temporal de unidades enemigas por celda
- [ ] P5-006 Generar heatmap temporal de edificios por celda
- [ ] P5-007 Generar heatmap de combates/daño por celda
- [ ] P5-008 Generar heatmap de control territorial aproximado
- [ ] P5-009 Generar mapas de riesgo por proximidad enemiga
- [x] P5-010 Generar trayectorias agregadas por tipo de unidad
- [ ] P5-011 Implementar downsampling temporal para secuencias largas
- [ ] P5-012 Implementar compresion de tensores espaciales
- [ ] P5-013 Definir estructura de `spatial_frame` serializable a Parquet/NPZ
- [x] P5-014 Crear visualizador de grilla en GUI
- [x] P5-015 Crear reproductor temporal con scrubber de tiempo
- [x] P5-016 Permitir superponer 2 jugadores en capas separadas
- [ ] P5-017 Permitir comparar dos partidas lado a lado
- [ ] P5-018 Agregar deteccion de hotspots por clustering
- [ ] P5-019 Agregar deteccion de rutas frecuentes (flow fields)
- [x] P5-020 Escribir tests de consistencia espacial (bordes, simetria, escalado)

## Parte 6 - CLI, GUI y experiencia de uso

- [x] P6-001 Definir comando CLI principal con subcomandos (`parse`, `metrics`, `batch`, `inspect`) (Owner: Codex, implementado en `aoe2_cli.py`)
- [x] P6-002 Agregar salida JSON compacta y JSON detallada (Owner: Codex, implementado en `aoe2_cli.py` con `--json {compact,detailed}`)
- [x] P6-003 Agregar salida CSV/Parquet por flags
- [x] P6-004 Agregar `--schema-version` y `--parser-version` en salida (Owner: Codex, implementado en `aoe2_cli.py` + bloque `meta`)
- [x] P6-005 Agregar `--strict` para fallar ante warnings severos (Owner: Codex, implementado en `aoe2_cli.py` con severidad `severe`)
- [ ] P6-006 Agregar `--continue-on-error` para lotes
- [ ] P6-007 Agregar barra de progreso para batch
- [x] P6-008 Agregar resumen final de errores por codigo (Owner: Codex, implementado en `aoe2_cli.py` (`error_summary` en `batch`))
- [x] P6-009 GUI: selector de replay individual y carpeta de replays
- [~] P6-010 GUI: panel de filtros por jugador/edad/tipo evento (Owner: Codex, en curso limpieza de redundancia entre pestañas)
- [x] P6-011 GUI: panel de KPIs con valores + sparkline (Owner: Codex, tab `KPIs` en `gui/window.py` con serie por métrica + snapshot por minuto)
- [x] P6-012 GUI: overlay de eventos sobre series de tiempo
- [x] P6-013 GUI: bookmarks de timestamps relevantes
- [x] P6-014 GUI: exportar grafico y exportar datos filtrados
- [x] P6-015 GUI: reproducir timeline a velocidad variable
- [x] P6-021 GUI: consolidar pestañas redundantes en flujo principal (`Overview` + `Timeline` + `Mapa`) (Owner: Codex, ocultadas tabs legacy APM/Unidades/Idle/Stock/Ventaja)
- [x] P6-022 GUI: timeline unificado de recursos colectados por jugador en función del tiempo (Owner: Codex, modo `Recursos colectados`)
- [x] P6-023 GUI: timeline unificado de unidades creadas por tipo y jugador (Owner: Codex, modo `Unidades creadas`)
- [x] P6-024 GUI: timeline de edificios construidos por jugador (Owner: Codex, modo `Edificios construidos`)
- [x] P6-025 GUI: timeline de clicks acumulados / relación APM (Owner: Codex, modo `Clicks/APM`)
- [~] P6-026 GUI: timeline de enemigos matados (proxy) por jugador (Owner: Codex, proxy inicial via `KILL|DESTROY|DELETE`; pendiente mejorar atribución real de kills)
- [x] P6-027 GUI: cálculo bajo demanda por serie (botón `Calcular`) + modo auto opcional (Owner: Codex, implementado en tab `Timeline`)
- [x] P6-028 GUI: cachear resultados temporales por replay/filtros para evitar recomputo (Owner: Codex, `timeline_cache`)
- [ ] P6-029 GUI: panel comparativo sincronizado para dos jugadores (económico + militar) en la misma vista
- [~] P6-030 WEB GUI: corregir contraste tipográfico en modo oscuro (menús, labels, inputs, tablas y tooltips) (Owner: Codex, en implementación)
- [~] P6-031 WEB GUI: rehacer tooltip espacial para fijarlo por celda/objetos y evitar desplazamiento errático (Owner: Codex, en implementación)
- [~] P6-032 WEB GUI: expandir capa de edificios para incluir todos los tipos parseables (casa, barracks, mercado, murallas, torres, etc.) (Owner: Codex, en implementación)
- [~] P6-033 WEB GUI: agregar overlay opcional de posiciones/eventos de unidades (Owner: Codex, en implementación)
- [~] P6-034 WEB GUI: reestructurar sidebar con secciones colapsables y scroll usable (Owner: Codex, en implementación)
- [ ] P6-016 GUI: comparar dos jugadores sincronizados
- [ ] P6-017 GUI: comparar dos partidas sincronizadas por tiempo relativo
- [ ] P6-018 GUI: tema claro/oscuro sin romper legibilidad
- [ ] P6-019 GUI: manejo de errores amigable y accionable
- [ ] P6-020 GUI: tests basicos de smoke

## Parte 4B - KPIs economicos/militares pedidos

- [ ] P4B-001 Definir KPI `idle_eco_time` por jugador y por fase (dark/feudal/castle/imperial)
- [ ] P4B-002 Definir KPI `villager_labour_efficiency` (tiempo productivo / tiempo total observable)
- [ ] P4B-003 Definir KPI `resource_delivery_efficiency` (tiempo de desplazamiento a drop-site vs tiempo de recolección)
- [ ] P4B-004 Definir KPI `military_kill_efficiency` (kills confirmados o proxy por costo destruido / costo perdido)
- [ ] P4B-005 Definir KPI `build_uptime` por edificio de producción (TC/Barracks/Archery/Stable/Siege)
- [ ] P4B-006 Implementar cálculo incremental de KPIs (ventanas) y snapshot acumulado al minuto N
- [ ] P4B-007 Exponer KPIs nuevos en CLI (`aoe2_cli.py metrics`) y GUI (`Overview`)
- [ ] P4B-008 Documentar supuestos y nivel de confianza de cada KPI nuevo (`high/medium/low`)

## Parte 5B - Trayectorias y eficiencia laboral de aldeanos

- [ ] P5B-001 Reconstruir trayectorias aproximadas de aldeanos por timestamps de comandos/eventos con posición
- [ ] P5B-002 Estimar distancia recorrida total y distancia improductiva por aldeano
- [ ] P5B-003 Inferir segmentos productivos vs improductivos (gather, return, idle, walk)
- [ ] P5B-004 Estimar tiempo de ida/vuelta a drop-sites por tipo de recurso
- [ ] P5B-005 Calcular `work_labour_efficiency` agregado por jugador y por ventana temporal
- [ ] P5B-006 Permitir ejecución `on-demand` de cálculos costosos (trayectorias) desde GUI/CLI
- [ ] P5B-007 Guardar cache intermedio de trayectorias por replay para reutilización
- [ ] P5B-008 Validar métricas de trayectoria con muestras manuales y tests de tolerancia

## Parte 7 - Procesamiento batch y escalabilidad

- [ ] P7-001 Implementar runner batch por carpeta
- [ ] P7-002 Implementar runner batch por lista de archivos
- [x] P7-003 Implementar runner batch por IDs (descarga + parse)
- [ ] P7-004 Implementar paralelismo configurable por CPU
- [ ] P7-005 Implementar control de memoria por worker
- [ ] P7-006 Implementar reintentos para fallos transitorios
- [ ] P7-007 Implementar cache de replays descargados
- [ ] P7-008 Implementar deduplicacion por hash de archivo
- [ ] P7-009 Implementar checkpoint/reanudacion de batch
- [ ] P7-010 Implementar cola de trabajos (simple local)
- [ ] P7-011 Implementar telemetria de throughput (replays/min)
- [ ] P7-012 Implementar reporte final de cobertura de parseo
- [ ] P7-013 Implementar trazabilidad `job_id` en outputs
- [ ] P7-014 Implementar limites de tasa para descargas
- [ ] P7-015 Implementar modo dry-run de batch
- [ ] P7-016 Benchmark: 100 replays
- [ ] P7-017 Benchmark: 1000 replays
- [ ] P7-018 Benchmark: stress de archivos grandes
- [ ] P7-019 Documentar tuning recomendado por hardware
- [ ] P7-020 Crear script reproducible de benchmark

## Parte 8 - Calidad de datos y validación

- [ ] P8-001 Crear suite de validaciones por replay
- [ ] P8-002 Validar monotonicidad temporal
- [ ] P8-003 Validar coherencia de conteos (no negativos, no saltos imposibles)
- [ ] P8-004 Validar coherencia de estados de edad
- [ ] P8-005 Validar consistencia de coordenadas dentro de mapa
- [ ] P8-006 Validar integridad referencial entre tablas
- [ ] P8-007 Crear score de calidad por replay
- [ ] P8-008 Crear score de calidad por columna/KPI
- [ ] P8-009 Definir umbrales para excluir replays del dataset ML
- [ ] P8-010 Guardar reporte de validacion por lote
- [ ] P8-011 Crear muestras golden para regresion
- [ ] P8-012 Automatizar comparacion con golden files
- [ ] P8-013 Detectar drift de distribuciones entre corridas
- [ ] P8-014 Detectar outliers extremos por métrica
- [ ] P8-015 Crear tablero de calidad de datos (aunque sea local HTML)

## Parte 9 - Dataset para ML y etiquetado

- [ ] P9-001 Definir tarea objetivo #1 (ej: proxima accion macro en +30s)
- [ ] P9-002 Definir tarea objetivo #2 (ej: decision militar en +60s)
- [ ] P9-003 Definir granularidad temporal de labels
- [ ] P9-004 Definir taxonomia de labels mutuamente excluyentes
- [ ] P9-005 Definir tratamiento de clases raras
- [ ] P9-006 Implementar generador de labels desde eventos
- [ ] P9-007 Implementar ventana de features historicas
- [ ] P9-008 Implementar split train/val/test sin leakage por partida
- [ ] P9-009 Implementar split por jugador para evaluacion robusta
- [ ] P9-010 Implementar balanceo/ponderacion de clases
- [ ] P9-011 Exportar dataset tabular para baseline
- [ ] P9-012 Exportar dataset secuencial para modelos temporales
- [ ] P9-013 Exportar dataset espacial-temporal para modelos de tensor
- [ ] P9-014 Agregar metadata de reproducibilidad de dataset
- [ ] P9-015 Versionar datasets generados (`dataset_version`)

## Parte 10 - Baselines de modelado IA

- [ ] P10-001 Baseline 1: regla heuristica (sin ML)
- [ ] P10-002 Baseline 2: Logistic Regression
- [ ] P10-003 Baseline 3: Random Forest / XGBoost
- [ ] P10-004 Baseline 4: RNN/Temporal Conv para secuencias
- [ ] P10-005 Baseline 5: modelo espacial-temporal liviano
- [ ] P10-006 Definir metricas de evaluacion (F1 macro, top-k accuracy, calibration)
- [ ] P10-007 Evaluar metricas por etapa del juego
- [ ] P10-008 Evaluar metricas por civ y matchup
- [ ] P10-009 Evaluar sensibilidad a calidad de parser
- [ ] P10-010 Crear benchmark reproducible de entrenamiento
- [ ] P10-011 Guardar artefactos de experimentos
- [ ] P10-012 Trazar curva de mejora vs complejidad
- [ ] P10-013 Analizar explicabilidad (feature importance/SHAP)
- [ ] P10-014 Definir criterio minimo para "modelo util"
- [ ] P10-015 Documentar limites y sesgos del modelo

## Parte 11 - Rendimiento y optimización

- [ ] P11-001 Perf profile del parser en replay corto
- [ ] P11-002 Perf profile del parser en replay largo
- [ ] P11-003 Perf profile de calculo de KPIs
- [ ] P11-004 Perf profile de transformaciones espaciales
- [ ] P11-005 Reducir copias innecesarias de datos en memoria
- [ ] P11-006 Vectorizar operaciones pesadas (NumPy/Polars)
- [ ] P11-007 Evaluar multiproceso vs multihilo
- [ ] P11-008 Implementar lectura por streaming cuando aplique
- [ ] P11-009 Agregar cache de resultados intermedios
- [ ] P11-010 Definir budgets de tiempo por replay
- [ ] P11-011 Definir budgets de RAM por replay
- [ ] P11-012 Agregar tests de performance en CI (smoke)

## Parte 12 - Testing e integración continua

- [ ] P12-001 Configurar `pytest` base
- [ ] P12-002 Crear fixtures de replays mínimos
- [ ] P12-003 Tests unitarios de parseo de metadata
- [ ] P12-004 Tests unitarios de eventos críticos
- [ ] P12-005 Tests unitarios de KPIs
- [ ] P12-006 Tests unitarios de espacial
- [ ] P12-007 Tests de integración end-to-end (parse -> metrics -> export)
- [ ] P12-008 Tests de regresion con golden files
- [ ] P12-009 Tests de tolerancia a errores
- [ ] P12-010 Tests de CLI
- [ ] P12-011 Tests de smoke de GUI
- [ ] P12-012 Configurar cobertura de tests y umbral minimo
- [ ] P12-013 Agregar workflow CI en GitHub Actions
- [ ] P12-014 Ejecutar lint + tests en PR
- [ ] P12-015 Publicar artefactos de test fallidos para debug

## Parte 13 - Observabilidad y debugging

- [ ] P13-001 Estandarizar niveles de log (DEBUG/INFO/WARN/ERROR)
- [ ] P13-002 Agregar `match_id` y `job_id` a todos los logs relevantes
- [ ] P13-003 Agregar tiempos por etapa del pipeline
- [ ] P13-004 Agregar contador de eventos parseados por tipo
- [ ] P13-005 Agregar resumen de warnings por replay
- [ ] P13-006 Crear modo `--debug-event` por timestamp/rango
- [ ] P13-007 Crear dump selectivo de eventos para inspeccion manual
- [ ] P13-008 Crear utilitario para comparar dos parseos del mismo replay
- [ ] P13-009 Crear utilitario para diff entre versiones de parser
- [ ] P13-010 Documentar playbook de debugging rapido

## Parte 14 - Documentación y onboarding

- [ ] P14-001 Actualizar README con arquitectura final
- [ ] P14-002 Crear guia de contribucion (`CONTRIBUTING.md`)
- [ ] P14-003 Crear guia de desarrollo local rapido
- [ ] P14-004 Crear guia de uso de CLI avanzada
- [ ] P14-005 Crear guia de uso de GUI
- [ ] P14-006 Crear guia de formato de dataset exportado
- [ ] P14-007 Crear guia de entrenamiento de baselines ML
- [ ] P14-008 Crear FAQ de errores comunes
- [ ] P14-009 Crear changelog versionado
- [ ] P14-010 Agregar ejemplos reproducibles minimos

## Parte 15 - Gestión de proyecto y paralelización multi-IA

- [ ] P15-001 Crear tablero Kanban con columnas por estado
- [ ] P15-002 Etiquetar tareas por dominio (`parser`, `kpi`, `spatial`, `ml`, `infra`)
- [ ] P15-003 Etiquetar tareas por dificultad (`S`, `M`, `L`, `XL`)
- [ ] P15-004 Etiquetar tareas por riesgo (`bajo`, `medio`, `alto`)
- [ ] P15-005 Definir plantilla de PR obligatoria
- [ ] P15-006 Definir Definition of Done por tipo de tarea
- [ ] P15-007 Definir politicas de branch naming
- [ ] P15-008 Definir politicas de code review
- [ ] P15-009 Definir politicas de merge (squash/rebase/merge commit)
- [ ] P15-010 Definir politicas de release versioning
- [ ] P15-011 Crear matriz de asignacion de tareas para varias IAs
- [ ] P15-012 Definir tareas independientes para correr en paralelo
- [ ] P15-013 Definir tareas que no deben hacerse en paralelo (conflicto alto)
- [ ] P15-014 Definir rutina semanal de triage tecnico
- [ ] P15-015 Definir ritual de cierre de milestone

## Parte 16 - Seguridad, licencias y cumplimiento

- [ ] P16-001 Revisar licencias de dependencias Python
- [ ] P16-002 Revisar licencias de dependencias JS (si crece la capa npm)
- [ ] P16-003 Revisar restricciones de uso de replays/metadata descargada
- [ ] P16-004 Definir politica de anonimización de datos sensibles
- [ ] P16-005 Definir politica de retencion de datasets
- [ ] P16-006 Definir politicas de almacenamiento de credenciales (si aplica)
- [ ] P16-007 Escaneo basico de vulnerabilidades en dependencias
- [ ] P16-008 Documentar consideraciones legales de distribucion

## Parte 17 - Entregables de hitos (milestones)

- [ ] P17-001 Milestone A: parser raw estable + tests base
- [ ] P17-002 Milestone B: KPIs robustos + validaciones
- [ ] P17-003 Milestone C: GUI temporal mejorada + exportes
- [ ] P17-004 Milestone D: espacial baseline + visualizacion de grilla
- [ ] P17-005 Milestone E: batch 1000 replays reproducible
- [ ] P17-006 Milestone F: dataset ML versionado
- [ ] P17-007 Milestone G: primer baseline predictivo util
- [ ] P17-008 Milestone H: hardening + documentacion completa

## Parte 18 - Backlog de mejoras opcionales

- [ ] P18-001 Soporte para analisis de team games avanzado
- [ ] P18-002 Soporte de comparativas por rango ELO
- [ ] P18-003 Soporte de comparativas por mapa/matchup
- [ ] P18-004 Deteccion automatica de build orders
- [ ] P18-005 Deteccion automatica de transiciones estrategicas
- [ ] P18-006 Sugerencias automáticas post-partida (coach mode)
- [ ] P18-007 API REST local para consultar parseos
- [ ] P18-008 Exportador a formato consumible por dashboards BI
- [ ] P18-009 Integracion con notebooks de analisis exploratorio
- [ ] P18-010 Integracion futura con servicio online

## Propuesta de reparto rápido entre varias IAs (inicio)

- [~] R-001 IA-A: P2-001..P2-010 (inventario y metadata parser) (Owner: Codex, completado P2-001/P2-002/P2-003/P2-005/P2-009/P2-010)
- [x] R-002 IA-B: P4-001..P4-010 (definiciones KPI) (Owner: Codex, completado en `docs/KPI_DEFINITIONS.md`)
- [ ] R-003 IA-C: P5-001..P5-010 (modelo espacial base)
- [ ] R-004 IA-D: P12-001..P12-008 (testing base + golden files)
- [~] R-005 IA-E: P6-001..P6-008 (CLI unificada) (Owner: Codex, tomado P6-001)
- [ ] R-006 IA-F: P7-001..P7-010 (batch runner)
- [x] R-007 IA-G: P3-001..P3-010 (schema + migraciones) (Owner: Codex, completado en `db/supabase_schema.sql` + `db/migrations`)
- [ ] R-008 IA-H: P14-001..P14-006 (docs técnicas)
