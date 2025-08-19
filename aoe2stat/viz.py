from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_apm(ts: pd.DataFrame, match, window_sec: int):
    if ts.empty:
        print('Sin acciones suficientes para APM.')
        return
    plt.figure(figsize=(10, 6))
    for pid in ts.columns:
        name = next(p.name for p in match.players if p.number == pid)
        plt.plot(ts.index / 60, ts[pid], label=name)
    plt.xlabel('Tiempo (min)')
    plt.ylabel('APM')
    plt.title(f'APM por jugador — ventana {window_sec}s')
    plt.grid(True)
    plt.legend()
    plt.show()


def plot_apm_bar(ts: pd.DataFrame, match):
    if ts.empty:
        print('Sin datos para generar barplot de APM.')
        return
    means = ts.mean()
    stds = ts.std()
    names = [next(p.name for p in match.players if p.number == pid) for pid in means.index]
    x = np.arange(len(names))
    plt.figure(figsize=(6, 5))
    plt.bar(x, means.values, yerr=stds.values, capsize=6)
    plt.xticks(x, names, rotation=45, ha='right')
    plt.ylabel('APM medio')
    plt.title('APM medio ± desviación estándar')
    plt.tight_layout()
    plt.show()


def plot_units_created_ts(ts: pd.DataFrame, match, unit_type: str, window_sec: int):
    if ts.empty:
        print(f'Sin acciones suficientes para {unit_type}.')
        return
    plt.figure(figsize=(10, 6))
    for pid in ts.columns:
        name = next(p.name for p in match.players if p.number == pid)
        plt.plot(ts.index/60, ts[pid], label=name)
    plt.xlabel('Tiempo (min)')
    plt.ylabel(f'Unidades creadas ({unit_type})')
    plt.title(f'{unit_type} creadas por jugador — ventana {window_sec}s')
    plt.grid(True)
    plt.legend()
    plt.show()


def plot_tc_idle_cumulative(ts: pd.DataFrame, match, window_sec: int):
    if ts.empty:
        print('Sin datos suficientes para idle TC acumulado.')
        return
    plt.figure(figsize=(10, 6))
    for pid in ts.columns:
        name = next(p.name for p in match.players if p.number == pid)
        plt.plot(ts.index/60, ts[pid], label=name)
    plt.xlabel('Tiempo (min)')
    plt.ylabel('Idle TC acumulado (s)')
    plt.title(f'Idle TC acumulado — ventana {window_sec}s')
    plt.grid(True)
    plt.legend()
    plt.show()


def plot_resource_cumulative(ts: pd.DataFrame, match, resource: str, window_sec: int):
    if ts.empty:
        print('Sin datos suficientes para recursos acumulados.')
        return
    plt.figure(figsize=(10, 6))
    for pid in ts.columns:
        name = next(p.name for p in match.players if p.number == pid)
        plt.plot(ts.index/60, ts[pid], label=name)
    plt.xlabel('Tiempo (min)')
    plt.ylabel(f'{resource.title()} acumulado')
    plt.title(f'{resource.title()} acumulado — ventana {window_sec}s')
    plt.grid(True)
    plt.legend()
    plt.show()

