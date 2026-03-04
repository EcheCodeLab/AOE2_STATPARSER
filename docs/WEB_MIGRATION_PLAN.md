# Migracion Web - Plan Incremental

Fecha: 2026-03-04

## Objetivo
Migrar la capa visual de la app desde Qt desktop a una interfaz web moderna, manteniendo el parser y las metricas en Python.

## Principios
- Backend Python conserva logica de parseo y analytics.
- Frontend web concentra visualizacion e interaccion.
- Migracion sin "big bang": convivir Qt + Web durante el proceso.

## Fases

1. Fase 1 - Base Web (este entregable)
- API local para cargar replay y pedir frames espaciales por tiempo.
- Viewer web MVP de mapa NxN con:
  - timeline y play/pause
  - capas (actividad/propio/enemigo/edificios/presion)
  - toggles de recursos y objetos clave
  - tooltip hover
  - log temporal de eventos

2. Fase 2 - Analytics UX
- Mejorar colorimetria y leyendas.
- Tooltips enriquecidos con mas contexto.
- Navegacion de log -> salto temporal.
- Comparativas A/B de jugadores.

3. Fase 3 - API estable
- Formalizar contrato OpenAPI de endpoints.
- Cache por replay + invalidacion.
- Serializacion compacta de frames (npz/parquet precomputado).

4. Fase 4 - Productizacion
- Persistencia server-side de sesiones.
- Auth opcional para compartir analisis.
- Deploy remoto (no solo local).

## Arquitectura propuesta
- `aoe2_web/app.py`: FastAPI + endpoints JSON + static files.
- `aoe2_web/static/index.html`: frontend web (sin build step al inicio).
- `aoe2stat/*`: fuente de verdad para parser, pipeline y metricas.

## Criterio de salida de Qt
Se podra retirar Qt cuando:
- Mapa web cubra 100% de casos de uso de analisis espacial.
- Overview/Trends web cubran KPIs y series principales.
- Exportes CSV/PNG/Parquet sigan disponibles via API.

