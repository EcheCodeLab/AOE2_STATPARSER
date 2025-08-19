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
```

El script imprime un resumen en JSON con jugadores, duración y mapa.

## Modularización

Además del notebook, el repo incluye una pequeña librería y una GUI de escritorio:

- `aoe2stat/`: utilidades núcleo
  - `patterns.py`: patrones de unidades (incluye Knight line y más)
  - `core.py`: extracción robusta desde payloads
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
```

Abre un `.aoe2record` desde el menú Archivo. Cada pestaña tiene controles (unidad, ventana, filtros) y actualiza en vivo.
