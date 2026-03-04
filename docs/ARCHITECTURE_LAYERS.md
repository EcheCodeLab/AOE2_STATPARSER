# Arquitectura por Capas (P1-001)

Objetivo: separar claramente parser crudo, transformaciones y presentación.

## Capas

1. `ParserLayer` (`aoe2stat/layers.py`)
- Responsabilidad: acceso a replay + parseo base (`download_replay`, `parse_summary`).
- Dependencias permitidas: librerías de parseo/IO (`mgz`, `requests`, filesystem).
- No debe depender de GUI ni de exportes de presentación.

2. `TransformLayer` (`aoe2stat/layers.py`)
- Responsabilidad: convertir replay en datasets canónicos (`events_raw`, `spatial_frames`) y features/validación.
- Implementación: delega en `ReplayAnalysisService`.
- No debe formatear payload final de salida CLI.

3. `PresentationLayer` (`aoe2stat/layers.py`)
- Responsabilidad: dar forma al output y exportar artefactos (CSV/JSONL/Parquet).
- Puede usar funciones de export de `pipeline` y serialización JSON.
- No realiza parseo crudo ni reglas de negocio de features.

## Entrada principal

- `aoe2_parser.py` ahora actúa como orquestador:
  - resuelve input (`--download` o ruta)
  - llama `ParserLayer` para summary
  - llama `TransformLayer` cuando hay export estructurado
  - llama `PresentationLayer` para materializar archivos/salida JSON

## Regla práctica

- Si un cambio toca parseo binario de replay: `ParserLayer`.
- Si un cambio toca cálculo de datasets/features/validaciones: `TransformLayer` (+ `services`).
- Si un cambio toca formato de salida/export: `PresentationLayer`.
