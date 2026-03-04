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

# Batch + export estructurado (events y espacial)
python aoe2_batch.py --input-dir ./replays --out-dir ./batch_out --export-events --export-spatial --grid-size 32 --window-sec 10

# Batch + parquet (requiere pyarrow o fastparquet)
python aoe2_batch.py --input-dir ./replays --out-dir ./batch_out --export-events-parquet --export-spatial-parquet
```

## Modularización

Además del notebook, el repo incluye una pequeña librería y una GUI de escritorio:

- `aoe2stat/`: utilidades núcleo
  - `patterns.py`: patrones de unidades (incluye Knight line y más)
  - `core.py`: extracción robusta desde payloads
  - `pipeline.py`: extracción canónica de eventos y generación de frames espaciales
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

Exportes desde GUI:
- `Archivo -> Exportar gráfico (PNG)` para la pestaña activa
- `Archivo -> Exportar datos filtrados (CSV)` para la pestaña activa

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

Tablas incluidas:

- `matches`
- `players`
- `events_raw`
- `spatial_frames`

Aplicar schema (ejemplo local con `psql`):

```bash
psql "$DATABASE_URL" -f db/supabase_schema.sql
```
