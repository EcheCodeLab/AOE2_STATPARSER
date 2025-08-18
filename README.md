# AOE2 Stat Parser

Herramienta simple para descargar y analizar partidas grabadas de **Age of Empires II: Definitive Edition**.

## Uso rápido

```bash
# Instalar dependencias
pip install mgz requests

# Analizar un archivo existente
python aoe2_parser.py AgeIIDE_Replay_396581946.aoe2record

# Descargar y analizar una partida por ID
python aoe2_parser.py --download 396581946
```

El script imprime un pequeño resumen en formato JSON con información de los jugadores, duración del juego y mapa utilizado.

## Nota

Este es un primer paso hacia un parser más completo (APM por jugador, tiempo inactivo del TC, etc.).
