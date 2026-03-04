# AOE2 Stat Parser

Herramienta para descargar y analizar partidas grabadas de **Age of Empires II: Definitive Edition** con utilidades de métrica, notebook y GUI.

## Uso rápido (CLI)

```bash
# Instalar dependencias mínimas
pip install mgz requests numpy pandas matplotlib

# Analizar un archivo existente
python aoe2_parser.py AgeIIDE_Replay_396581946.aoe2record

# Descargar y analizar una partida por ID
python aoe2_parser.py --download 396581946

# Exportar eventos canónicos + representación espacial NxN
python aoe2_parser.py AgeIIDE_Replay_396581946.aoe2record \
  --export-events-csv out/events.csv \
  --export-events-jsonl out/events.jsonl \
  --export-events-parquet out/events.parquet \
  --export-spatial-csv out/spatial.csv \
  --export-spatial-parquet out/spatial.parquet \
  --grid-size 32 \
  --window-sec 10
```

El script imprime un resumen en JSON con jugadores, duración y mapa.
Si pasas flags de export, también devuelve un bloque `structured` con conteos y rutas de salida.
Para Parquet necesitás instalar `pyarrow` o `fastparquet`.

## Ejecución vía npm scripts

Si prefieres arrancar con `npm`:

```bash
# Solo crea package-lock.json local; este repo no requiere paquetes npm externos
npm install

# Abrir GUI (equivalente a: python -m gui.run_gui)
npm run dev

# Parsear un archivo (equivalente a: python aoe2_parser.py <archivo>)
npm run parse -- AgeIIDE_Replay_396581946.aoe2record

# Descargar por ID y parsear (equivalente a: python aoe2_parser.py --download <id>)
npm run parse:download -- 396581946

# Export estructurado con argumentos extra
npm run parse -- AgeIIDE_Replay_396581946.aoe2record --export-events-csv out/events.csv --export-spatial-csv out/spatial.csv

# Batch parse (equivalente a: python aoe2_batch.py ...)
npm run batch -- --input-dir ./replays --out-dir ./batch_out
```

## Batch runner (P7 baseline)

`aoe2_batch.py` agrega un pipeline batch local orientado a robustez:

- Entrada por carpeta (`--input-dir`), lista (`--list-file`) o paths posicionales
- Descarga opcional por IDs (`--game-ids`)
- Descarga automática de partidas recientes por jugador (`--player-profile-ids` / `--player-aliases`)
- Dedupe por `sha256` (se puede desactivar con `--no-dedupe`)
- Checkpoint reanudable (`--checkpoint`)
- Reintentos por replay (`--retries`)
- `--strict` (corta ante error) o `--continue-on-error`
- Salidas: `results.jsonl`, `checkpoint.json`, `batch_report.json`, y resúmenes por replay
- Export estructurado opcional por replay:
  - `--export-events`: genera `events_csv/*.csv` y `events_jsonl/*.jsonl`
  - `--export-spatial`: genera `spatial_csv/*.csv`
  - `--export-events-parquet`: genera `events_parquet/*.parquet`
  - `--export-spatial-parquet`: genera `spatial_parquet/*.parquet`
  - `--grid-size` y `--window-sec` para el espacial
  - `--parquet-strict`: falla el replay si no se puede exportar Parquet

Ejemplos:

```bash
# Recursivo por carpeta
python aoe2_batch.py --input-dir ./replays --out-dir ./batch_out

# Desde lista de archivos (1 path por línea)
python aoe2_batch.py --list-file ./replays.txt --out-dir ./batch_out

# Descargar y parsear por IDs
python aoe2_batch.py --game-ids 396581946 396581947 --download-dir ./downloads --out-dir ./batch_out

# Descargar y parsear partidas recientes de jugadores por alias
python aoe2_batch.py --player-aliases "Hera" "Liereyy" --per-player-count 3 --out-dir ./batch_out

# Variante más robusta por profile IDs
python aoe2_batch.py --player-profile-ids 6174996 1234567 --per-player-count 5 --out-dir ./batch_out

# Batch + export estructurado (events y espacial)
python aoe2_batch.py --input-dir ./replays --out-dir ./batch_out --export-events --export-spatial --grid-size 32 --window-sec 10

# Batch + parquet (requiere pyarrow o fastparquet)
python aoe2_batch.py --input-dir ./replays --out-dir ./batch_out --export-events-parquet --export-spatial-parquet
```

## Modularización

Además del notebook, el repo incluye una pequeña librería y una GUI de escritorio:

- `aoe2stat/`: utilidades núcleo
  - `config.py`: configuración centralizada desde entorno (`AOE2_*`)
  - `patterns.py`: patrones de unidades (incluye Knight line y más)
  - `core.py`: extracción robusta desde payloads
  - `pipeline.py`: extracción canónica de eventos y generación de frames espaciales
  - `schema.py`: modelos tipados para bundles de análisis
  - `io.py`: lectura/escritura de formatos (json/csv/jsonl/parquet)
  - `features.py`: plugins de features/KPI (`FeaturePlugin`, `FeatureRegistry`)
  - `spatial.py`: capa espacial de alto nivel para `NxN`
  - `validation.py`: controles de calidad de datasets derivados
  - `services.py`: orquestación reusable por CLI/GUI (`ReplayAnalysisService`)
  - `batch.py`: ejecución batch con la capa de servicios
  - `metrics.py`: APM, series de creación, conteo de aldeanos, idle TC (incl. acumulado), recursos (fallback)
  - `viz.py`: funciones de plotting con Matplotlib
- `gui/`: GUI con PySide6/PyQt5
  - `run_gui.py`: punto de entrada
  - `window.py`: ventana principal con pestañas (APM, Unidades, Idle TC, Recursos)

## GUI de escritorio

Instala dependencias:

```bash
pip install PySide6 matplotlib numpy pandas mgz
```

Lanza la app:

```bash
python -m gui.run_gui
# alternativa
npm run dev
```

Abre un `.aoe2record` desde el menú Archivo. Cada pestaña tiene controles (unidad, ventana, filtros) y actualiza en vivo.

También podés abrir una carpeta completa de replays desde `Archivo -> Abrir carpeta de replays` y navegar rápido con:
- `Archivo -> Replay anterior`
- `Archivo -> Replay siguiente`
- `Archivo -> Descargar recientes por jugador` para bajar partidas nuevas desde internet por alias

Exportes desde GUI:
- `Archivo -> Exportar gráfico (PNG)` para la pestaña activa
- `Archivo -> Exportar datos filtrados (CSV)` para la pestaña activa

Bookmarks de tiempo (pestaña `Mapa`):
- `Agregar bookmark` en el tiempo actual del slider
- doble click en bookmark para saltar al timestamp
- `Eliminar bookmark` y `Limpiar bookmarks` para gestión rápida

Reproducción de timeline (pestaña `Mapa`):
- botón `Play/Pausa` para animar el tiempo
- selector de velocidad (`0.5x`, `1x`, `2x`, `4x`)

Overlay de eventos sobre series:
- toggle global en `Ver -> Overlay de eventos`
- aplica a series de APM, Unidades, Stock Total y Score

### Mapa NxN (MVP)

La pestaña `Mapa` ahora usa una grilla `NxN` para visualizar densidad espacial de acciones con:

- filtro por jugador
- filtro por familia de acción (`movement`, `build`, `production`, etc.)
- resolución de grilla (`16` a `64`)
- ventana temporal deslizante (segundos)
- slider de tiempo para reproducir la partida

## Supabase/Postgres (schema inicial)

Se incluye un DDL base para persistencia incremental en:

- `db/supabase_schema.sql`
- `db/SCHEMA_CONTRACT.md` (tipos, nullabilidad, unidades y claves lógicas)
- `db/MIGRATIONS.md` (política de versionado y estrategia de migraciones)
- `db/migrations/0001__baseline_sprint_1_1.sql` (baseline incremental)

Tablas incluidas:

- `matches`
- `players`
- `events_raw`
- `spatial_frames`

Aplicar schema (ejemplo local con `psql`):

```bash
psql "$DATABASE_URL" -f db/supabase_schema.sql
```

Ingest incremental de una replay (upsert por `match_id + parser_version`):

```bash
pip install psycopg2-binary
python aoe2_ingest_postgres.py AgeIIDE_Replay_396581946.aoe2record \
  --dsn "$DATABASE_URL" \
  --parser-version sprint-1.1 \
  --grid-size 32 \
  --window-sec 10 \
  --apply-schema
```

Ingest batch a Postgres/Supabase:

```bash
python aoe2_ingest_batch_postgres.py \
  --input-dir ./replays \
  --dsn "$DATABASE_URL" \
  --parser-version sprint-1.1 \
  --grid-size 32 \
  --window-sec 10 \
  --retries 2 \
  --continue-on-error \
  --out-dir ./ingest_out
```

Salidas del batch:
- `ingest_out/ingest_results.jsonl`
- `ingest_out/ingest_report.json`
