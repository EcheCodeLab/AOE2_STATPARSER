from __future__ import annotations

import traceback
from pathlib import Path

try:
    from PySide6 import QtWidgets
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QFileDialog, QMessageBox, QTabWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QCheckBox
    )
except Exception:  # pragma: no cover
    from PyQt5 import QtWidgets  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QMainWindow, QWidget, QFileDialog, QMessageBox, QTabWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QCheckBox
    )

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from aoe2stat.core import load_match
from aoe2stat.metrics import (
    apm_timeseries, unit_created_timeseries, tc_idle_cumulative_timeseries,
    resource_totals_postgame, resource_cumulative_timeseries,
)
from aoe2stat.patterns import base_unit_patterns, augment_unit_patterns


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure(figsize=(5, 4))
        self.ax = fig.add_subplot(111)
        super().__init__(fig)

    def plot_lines(self, x, series_dict, xlabel: str, ylabel: str, title: str):
        self.ax.clear()
        for label, y in series_dict.items():
            self.ax.plot(x, y, label=label)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(title)
        self.ax.grid(True)
        self.ax.legend()
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AoE2 Stat Analyzer")
        self.replay_path: Path | None = None
        self.match = None
        self.unit_patterns = augment_unit_patterns(base_unit_patterns())

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tabs
        self.tab_apm = QWidget(); self.tabs.addTab(self.tab_apm, "APM")
        self.tab_units = QWidget(); self.tabs.addTab(self.tab_units, "Unidades")
        self.tab_idle = QWidget(); self.tabs.addTab(self.tab_idle, "Idle TC")
        self.tab_res = QWidget(); self.tabs.addTab(self.tab_res, "Recursos")

        self._setup_menu()
        self._setup_apm_tab()
        self._setup_units_tab()
        self._setup_idle_tab()
        self._setup_res_tab()

    # ---- UI Setup ----
    def _setup_menu(self):
        open_action = QtWidgets.QAction("Abrir replay", self)
        open_action.triggered.connect(self.open_replay)
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Archivo")
        file_menu.addAction(open_action)

    def _setup_apm_tab(self):
        layout = QVBoxLayout(); self.tab_apm.setLayout(layout)
        controls = QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QLabel("Ventana (s):"))
        self.apm_window = QComboBox(); self.apm_window.addItems(["15","30","45","60","90","120"]) ; self.apm_window.setCurrentText("60")
        self.apm_window.currentTextChanged.connect(self.update_apm)
        controls.addWidget(self.apm_window)
        self.apm_canvas = PlotCanvas(); layout.addWidget(self.apm_canvas)

    def _setup_units_tab(self):
        layout = QVBoxLayout(); self.tab_units.setLayout(layout)
        controls1 = QHBoxLayout(); layout.addLayout(controls1)
        controls1.addWidget(QLabel("Unidad:"))
        self.units_combo = QComboBox(); self.units_combo.addItems(list(self.unit_patterns.keys()))
        self.units_combo.currentTextChanged.connect(self.update_units)
        controls1.addWidget(self.units_combo)
        controls1.addWidget(QLabel("Ventana (s):"))
        self.units_window = QComboBox(); self.units_window.addItems(["15","30","45","60","90","120"]) ; self.units_window.setCurrentText("60")
        self.units_window.currentTextChanged.connect(self.update_units)
        controls1.addWidget(self.units_window)
        # Player filters
        self.units_players_list = QListWidget(); self.units_players_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(QLabel("Jugadores a mostrar:"))
        layout.addWidget(self.units_players_list)
        self.units_players_list.itemSelectionChanged.connect(self.update_units)
        self.units_canvas = PlotCanvas(); layout.addWidget(self.units_canvas)

    def _setup_idle_tab(self):
        layout = QVBoxLayout(); self.tab_idle.setLayout(layout)
        controls = QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QLabel("Ventana (s):"))
        self.idle_window = QComboBox(); self.idle_window.addItems(["15","30","45","60","90","120"]) ; self.idle_window.setCurrentText("60")
        self.idle_window.currentTextChanged.connect(self.update_idle)
        self.idle_canvas = PlotCanvas(); layout.addWidget(self.idle_canvas)

    def _setup_res_tab(self):
        layout = QVBoxLayout(); self.tab_res.setLayout(layout)
        controls = QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QLabel("Recurso:"))
        self.res_combo = QComboBox(); self.res_combo.addItems(["food","wood","gold","stone"]) ; self.res_combo.currentTextChanged.connect(self.update_res)
        controls.addWidget(self.res_combo)
        controls.addWidget(QLabel("Ventana (s):"))
        self.res_window = QComboBox(); self.res_window.addItems(["15","30","45","60","90","120"]) ; self.res_window.setCurrentText("60")
        self.res_window.currentTextChanged.connect(self.update_res)
        self.res_canvas = PlotCanvas(); layout.addWidget(self.res_canvas)

    # ---- Actions ----
    def open_replay(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona .aoe2record", filter="AoE2 Replay (*.aoe2record)")
        if not path:
            return
        try:
            self.match = load_match(path)
            self.replay_path = Path(path)
            # Populate players list
            self.units_players_list.clear()
            for p in self.match.players:
                item = QListWidgetItem(p.name)
                item.setData(1, int(p.number))
                item.setSelected(True)
                self.units_players_list.addItem(item)
            # Trigger updates
            self.update_apm(); self.update_units(); self.update_idle(); self.update_res()
        except Exception as e:  # pragma: no cover
            QMessageBox.critical(self, "Error", f"No se pudo abrir el replay:\n{e}\n\n{traceback.format_exc()}")

    # ---- Update plots ----
    def update_apm(self):
        if not self.match:
            return
        w = int(self.apm_window.currentText())
        ts = apm_timeseries(self.match, window_sec=w)
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        self.apm_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'APM', f'APM ventana {w}s')

    def _selected_players(self):
        pids = []
        for i in range(self.units_players_list.count()):
            item = self.units_players_list.item(i)
            if item.isSelected():
                pids.append(int(item.data(1)))
        return pids

    def update_units(self):
        if not self.match:
            return
        unit_name = self.units_combo.currentText()
        w = int(self.units_window.currentText())
        pattern = self.unit_patterns[unit_name]
        ts = unit_created_timeseries(self.match, pattern, window_sec=w)
        sel = self._selected_players()
        if sel and not ts.empty:
            ts = ts[[pid for pid in ts.columns if pid in sel]]
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        self.units_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', f'Unidades creadas ({unit_name})', f'{unit_name} — ventana {w}s')

    def update_idle(self):
        if not self.match:
            return
        import re
        villager_re = re.compile(r'villager|aldean', re.IGNORECASE)
        w = int(self.idle_window.currentText())
        ts = tc_idle_cumulative_timeseries(self.match, villager_re, window_sec=w)
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        self.idle_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'Idle TC acumulado (s)', f'Idle TC — ventana {w}s')

    def update_res(self):
        if not self.match or not self.replay_path:
            return
        res = self.res_combo.currentText()
        w = int(self.res_window.currentText())
        per_player = resource_totals_postgame(self.replay_path)
        ts = resource_cumulative_timeseries(self.match, per_player, resource=res, window_sec=w)
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        self.res_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', f'{res.title()} acumulado', f'{res.title()} — ventana {w}s')

