# Revisión crítica de checklist y reformulación de objetivos (2026-03-04)

## 1) Qué está bien de la aproximación actual

- Hay enfoque por capas (parser, esquema, KPIs, espacial, UX) que evita mezclar todo en un único bloque técnico.
- Se priorizó visibilidad temprana (GUI + NxN + scrubber) y eso es correcto para validar producto.
- Existe base de contratos de datos (`db/SCHEMA_CONTRACT.md`, migraciones, versionado) suficiente para escalar.
- Parte 2 tiene bases reales implementadas: `RawEvent`, reloj unificado, vistas por tipo de evento, advertencias de parseo y snapshots por ventana.

## 2) Dónde hoy está desalineado

- La checklist mezcla `MVP`, `baseline`, `parcial` y `completado` dentro del mismo `[x]/[~]/[ ]` sin Definition of Done explícita.
- Hay desalineación entre documentos:
  - En roadmap, `P6-011` figura pendiente/parcial; en checklist está marcado como completado.
- Parte 2 muestra varios ítems como pendientes que ya tienen baseline parcial en código:
  - `P2-019` y `P2-020`: existe extracción/versionado básico en `extract_id_mappings`.
- Hay ítems en progreso sin evidencia mínima automatizada:
  - `P2-025` está en curso pero no existe `tests/test_part2_regression.py` en `tests/`.
- Se está optimizando UI/visualización a buen ritmo, pero con riesgo de deuda si no se fija una puerta de calidad mínima para extracción raw.

## 3) Evaluación de acierto (resumen)

- Dirección general: acertada.
- Ejecución actual: buena velocidad, pero con riesgo medio de "falso verde" por inconsistencia de estados.
- Recomendación: mantener estrategia por fases, pero reescribir objetivos con DoD verificable por artefacto/archivo/test.

## 4) Reformulación propuesta (Parte 2 como núcleo)

Objetivo macro Parte 2 (redefinido):
- "Cerrar un parser raw confiable y trazable, con cobertura mínima de regresión y taxonomía estable, de forma que la capa espacial (Parte 5) consuma datos sin heurísticas frágiles."

### 4.1 Subfases de Parte 2

#### P2-A Contrato raw estable (bloqueante)
- Alcance:
  - `RawEvent` con columnas canónicas fijas.
  - `parser_version`, `source_lib_version`, `parse_warnings` en toda salida CLI/API.
  - Política de eventos desconocidos sin romper pipeline.
- DoD:
  - Un ejemplo real exportado a JSON/Parquet con esos campos.
  - 1 test que valide esquema/columnas obligatorias.

#### P2-B Taxonomía y mapeos (bloqueante para KPIs y espacial)
- Alcance:
  - Cerrar taxonomía `event_type_semantic` + `action_family`.
  - Versionar diccionario `id -> human_name` por `patch_version`.
- DoD:
  - Reporte de cobertura de clasificación (% clasificado vs `other`).
  - Export de mapeos versionados con conteos observados.

#### P2-C Timelines consumibles
- Alcance:
  - `age_ups`, `units`, `buildings`, `techs` con campos mínimos homogéneos.
  - `player_commands`, `combat_events`, `economy_events`, `spatial_events` como vistas oficiales.
- DoD:
  - 1 snapshot de ejemplo por tipo de timeline.
  - Test de no-regresión en conteos por replay fixture.

#### P2-D Robustez operacional
- Alcance:
  - Manejo explícito de replays truncados/corruptos.
  - `--strict` y severidades consistentes.
- DoD:
  - Códigos de warning documentados y estables.
  - Test de replay inválido con degradación controlada.

### 4.2 KPIs de control para Parte 2

- `%_events_classified = 1 - (other / total)`
- `%_events_with_player_id`
- `%_events_with_t_ms_valid`
- `%_events_with_xy` (para habilitar calidad espacial)
- `warnings_per_match` por severidad

Objetivo mínimo de salida para habilitar Parte 5 confiable:
- `%_events_classified >= 0.90`
- `%_events_with_player_id >= 0.98`
- `%_events_with_t_ms_valid = 1.00`

## 5) Reformulación propuesta (Parte 5 alineada a datos reales)

Objetivo macro Parte 5 (redefinido):
- "Mostrar dinámica territorial interpretable y comparable entre jugadores usando capas espaciales derivadas de eventos raw con calidad medida."

### 5.1 Orden recomendado

1. Normalización de coordenadas + validación de límites (`P5-001`, `P5-002`).
2. Heatmaps base por canal (`own/enemy/buildings`) y por tiempo (`P5-004..P5-006`).
3. Riesgo/combate proxy (`P5-007`, `P5-009`) sobre canales ya validados.
4. `spatial_frame` serializable y compacto (`P5-013`) para no recalcular GUI.
5. Comparativas avanzadas (`P5-017..P5-019`) cuando los 4 pasos previos estén estables.

### 5.2 DoD mínimo Parte 5

- Cada capa muestra leyenda, rango de valores y resolución NxN efectiva.
- Cada frame espacial es serializable y rehidratable sin pérdida semántica.
- Test de consistencia espacial + 1 test de regresión visual numérica (sumas por celda).

## 6) Cambios concretos sugeridos sobre checklist actual

- Agregar campo `DoD:` obligatorio a todo ítem en `[~]`.
- Separar estado en dos dimensiones:
  - `Implementación`: `[ ] [~] [x]`
  - `Validación`: `[ ] [~] [x]`
- Reetiquetar ítems Parte 2 con evidencia existente:
  - `P2-019`: pasar a `[~]` (baseline implementado en `extract_id_mappings`).
  - `P2-020`: pasar a `[~]` (versionado inicial por `patch_version` ya presente).
- Corregir inconsistencias roadmap/checklist (ej. `P6-011`) y fijar una única fuente de verdad semanal.
- Convertir `P2-025` en entregable inmediato con fixture mínimo real (si no hay fixture, el estado no puede ser `[~]`).

## 7) Siguiente sprint recomendado (72h)

1. Cerrar `P2-025` con tests reales de regresión y snapshot esperado.
2. Publicar reporte de cobertura de taxonomía (`other`, `player_id`, `xy`).
3. Formalizar `spatial_frame` serializable (`P5-013`) consumido por GUI.
4. Reconciliar estados checklist/roadmap y congelar DoD por ítem.
