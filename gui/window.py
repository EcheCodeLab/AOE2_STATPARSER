from __future__ import annotations

import traceback
import csv
from pathlib import Path
import json

try:
    from PySide6 import QtWidgets, QtCore
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QFileDialog, QMessageBox, QTabWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QCheckBox, QSlider,
        QInputDialog, QAbstractItemView, QFrame, QTableWidget, QTableWidgetItem, QHeaderView
    )
    from PySide6.QtGui import QAction
except Exception:  # pragma: no cover
    from PyQt5 import QtWidgets, QtCore  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QMainWindow, QWidget, QFileDialog, QMessageBox, QTabWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QCheckBox, QAction, QSlider,
        QInputDialog, QAbstractItemView, QFrame, QTableWidget, QTableWidgetItem, QHeaderView
    )

import os
import requests
# Ensure Matplotlib uses QtAgg with the chosen Qt binding
os.environ.setdefault("QT_API", os.environ.get("QT_API", "pyside6"))
os.environ.setdefault("MPLBACKEND", "QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from aoe2stat.core import load_match
from aoe2stat.layers import ParserLayer
from aoe2stat.metrics import (
    apm_timeseries, unit_created_timeseries, tc_idle_cumulative_timeseries,
    resource_totals_postgame, resource_cumulative_timeseries,
    resource_spend_timeseries, resource_balance_timeseries, important_events,
)
from aoe2stat.patterns import base_unit_patterns, augment_unit_patterns
from aoe2stat.pipeline import extract_raw_events
from aoe2stat.kpis import kpis_by_window
import numpy as np


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure(figsize=(5, 4), constrained_layout=True)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.dark = False
        self.legend_outside = False

    def set_theme(self, dark: bool):
        self.dark = bool(dark)
        # Apply immediately to current axes
        self._apply_theme()
        self.draw()

    def _apply_theme(self):
        if self.dark:
            fg = '#e6e6e6'; bg = '#0f1116'; axbg = '#141821'; grid = '#2a2f3a'; spine = '#5a6472'
        else:
            fg = '#111111'; bg = '#ffffff'; axbg = '#ffffff'; grid = '#dddddd'; spine = '#444444'
        self.figure.set_facecolor(bg)
        self.ax.set_facecolor(axbg)
        self.ax.grid(True, color=grid, alpha=0.6)
        for spine_obj in self.ax.spines.values():
            spine_obj.set_color(spine)
        self.ax.tick_params(colors=fg)
        self.ax.xaxis.label.set_color(fg); self.ax.yaxis.label.set_color(fg)
        self.ax.title.set_color(fg)
        # adjust legend after theme
        self._apply_legend()

    def set_legend_outside(self, outside: bool):
        self.legend_outside = bool(outside)
        self._apply_legend()
        self.draw()

    def _apply_legend(self):
        leg = self.ax.get_legend()
        if leg is None:
            return
        if self.legend_outside:
            leg.remove()
            leg = self.ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), borderaxespad=0., framealpha=0.2, fontsize=9)
        else:
            leg.remove()
            leg = self.ax.legend(loc='upper left', framealpha=0.2, fontsize=9)
        if leg is not None and self.dark:
            leg.get_frame().set_facecolor('#0f1116')
            leg.get_frame().set_edgecolor('#5a6472')

    def plot_lines(self, x, series_dict, xlabel: str, ylabel: str, title: str, colors: dict | None = None):
        self.ax.clear()
        ymax = 0.0
        for label, y in series_dict.items():
            kw = {}
            if colors and label in colors:
                kw['color'] = colors[label]
            self.ax.plot(x, y, label=label, linewidth=1.8, **kw)
            try:
                ymax = max(ymax, float(max(y)))
            except Exception:
                pass
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(title)
        self._apply_theme()
        leg = self.ax.legend(loc='upper left', framealpha=0.2, fontsize=9)
        if leg is not None and self.dark:
            leg.get_frame().set_facecolor('#0f1116')
            leg.get_frame().set_edgecolor('#5a6472')
        # re-apply legend placement (inside/outside)
        self._apply_legend()
        # Add headroom for markers
        if ymax > 0:
            lo, hi = self.ax.get_ylim()
            self.ax.set_ylim(lo, max(hi, ymax * 1.15))
        self.draw()

    def draw_message(self, text: str):
        self.ax.clear()
        self.ax.text(0.5, 0.5, text, ha='center', va='center', transform=self.ax.transAxes)
        self.ax.set_axis_off()
        self.draw()

    def add_event_markers(self, xs, kinds, colors=None, texts=None):
        # draw vertical lines and marker shapes near top
        ylim = self.ax.get_ylim()
        y_pos = ylim[0] + 0.95 * (ylim[1] - ylim[0])
        marker_map = {
            'age': ('*', 'F'),      # star
            'castle': ('s', 'C'),   # square
            'elite': ('D', 'E'),    # diamond
            'tech': ('^', 'T'),     # triangle up
            'tc': ('v', 'TC'),      # triangle down
        }
        for i, (x, kind) in enumerate(zip(xs, kinds)):
            c = colors[i] if colors and i < len(colors) else 'k'
            m, txt = marker_map.get(kind, ('o', '?'))
            if texts and i < len(texts) and texts[i]:
                txt = texts[i]
            # vertical line
            self.ax.axvline(x, color=c, linewidth=0.6, alpha=0.4)
            # marker (filled for visibility)
            edge = '#ffffff' if self.dark else '#000000'
            self.ax.scatter([x], [y_pos], marker=m, s=90, facecolors=c, edgecolors=edge, linewidths=0.8, alpha=0.7, clip_on=False)
            # tiny label above in contrasting color
            txt_color = '#e6e6e6' if self.dark else '#111111'
            self.ax.text(x, y_pos, txt, va='bottom', ha='center', fontsize=8, color=txt_color)
        self.ax.set_ylim(ylim)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AoE2 Stat Analyzer")
        self.resize(1460, 920)
        self.setMinimumSize(1120, 760)
        self.ui_layout_mode = "analyst"
        self.replay_path: Path | None = None
        self.replay_files: list[Path] = []
        self.replay_index: int = -1
        self.match = None
        self.events_df = None
        self.unit_patterns = augment_unit_patterns(base_unit_patterns())
        self.export_cache: dict[str, dict] = {}
        self.bookmarks_by_replay: dict[str, list[dict[str, str | float]]] = {}
        self.map_playback_timer = QtCore.QTimer(self)
        self.map_playback_timer.setInterval(250)
        self.map_playback_timer.timeout.connect(self._playback_tick)
        self.map_playback_is_running = False
        self.map_playback_pos = 0.0
        self.map_cine_heat: np.ndarray | None = None
        self.map_cine_center: tuple[float, float] | None = None
        self.map_cine_radius: float | None = None
        self.map_last_time: float | None = None
        self.map_cine_signature: tuple | None = None
        self.map_key_objects_df = None
        self.map_resource_df = None
        self.map_build_events_df = None
        self.map_delete_events_df = None
        self.map_fixed_grid_size = 128
        self.map_initial_tcs_df = None
        self.map_hover_items: list[dict[str, float | str]] = []
        self.map_hover_annotation = None
        self.map_event_log_df = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._map_cache = None

        # Tabs
        self.tab_apm = QWidget(); self.tabs.addTab(self.tab_apm, "APM")
        self.tab_units = QWidget(); self.tabs.addTab(self.tab_units, "Unidades")
        self.tab_idle = QWidget(); self.tabs.addTab(self.tab_idle, "Idle TC")
        self.tab_res = QWidget(); self.tabs.addTab(self.tab_res, "Recursos")
        self.tab_stock = QWidget(); self.tabs.addTab(self.tab_stock, "Stock Total")
        self.tab_score = QWidget(); self.tabs.addTab(self.tab_score, "Ventaja")
        self.tab_kpis = QWidget(); self.tabs.addTab(self.tab_kpis, "KPIs")
        self.tab_map = QWidget(); self.tabs.addTab(self.tab_map, "Mapa")

        self._setup_menu()
        self._setup_apm_tab()
        self._setup_units_tab()
        self._setup_idle_tab()
        self._setup_res_tab()
        self._setup_stock_tab()
        self._setup_score_tab()
        self._setup_kpis_tab()
        self._setup_map_tab()
        self._apply_base_layouts()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # initialize theme/legend on canvases
        self._apply_theme_all()

    # ---- UI Setup ----
    def _setup_menu(self):
        open_action = QAction("Abrir replay", self)
        open_action.triggered.connect(self.open_replay)
        download_recent_action = QAction("Descargar recientes por jugador", self)
        download_recent_action.triggered.connect(self.download_recent_replays_by_alias)
        open_folder_action = QAction("Abrir carpeta de replays", self)
        open_folder_action.triggered.connect(self.open_replay_folder)
        prev_replay_action = QAction("Replay anterior", self)
        prev_replay_action.triggered.connect(self.open_prev_replay)
        next_replay_action = QAction("Replay siguiente", self)
        next_replay_action.triggered.connect(self.open_next_replay)
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Archivo")
        file_menu.addAction(open_action)
        file_menu.addAction(download_recent_action)
        file_menu.addAction(open_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(prev_replay_action)
        file_menu.addAction(next_replay_action)
        file_menu.addSeparator()
        export_plot_action = QAction("Exportar gráfico (PNG)", self)
        export_plot_action.triggered.connect(self.export_current_plot_png)
        file_menu.addAction(export_plot_action)
        export_data_action = QAction("Exportar datos filtrados (CSV)", self)
        export_data_action.triggered.connect(self.export_current_data_csv)
        file_menu.addAction(export_data_action)
        view_menu = menubar.addMenu("Ver")
        self.dark_action = QAction("Tema oscuro", self, checkable=True)
        self.dark_action.setChecked(True)
        self.dark_action.toggled.connect(self._toggle_theme)
        view_menu.addAction(self.dark_action)
        self.legend_out_action = QAction("Leyenda fuera", self, checkable=True)
        self.legend_out_action.setChecked(True)
        self.legend_out_action.toggled.connect(self._toggle_legend_outside)
        view_menu.addAction(self.legend_out_action)
        view_menu.addSeparator()
        self.layout_analyst_action = QAction("Layout Analyst", self, checkable=True)
        self.layout_analyst_action.setChecked(True)
        self.layout_analyst_action.triggered.connect(self._set_layout_analyst)
        view_menu.addAction(self.layout_analyst_action)
        self.layout_compact_action = QAction("Layout Compacto Pro", self, checkable=True)
        self.layout_compact_action.setChecked(False)
        self.layout_compact_action.triggered.connect(self._set_layout_compact)
        view_menu.addAction(self.layout_compact_action)
        self.overlay_events_action = QAction("Overlay de eventos", self, checkable=True)
        self.overlay_events_action.setChecked(True)
        self.overlay_events_action.toggled.connect(self._toggle_event_overlay)
        view_menu.addAction(self.overlay_events_action)
        help_menu = menubar.addMenu("Ayuda")
        self.gloss_action = QAction("Ver glosario de hitos", self)
        self.gloss_action.triggered.connect(self._show_glossary)
        help_menu.addAction(self.gloss_action)

    def _setup_apm_tab(self):
        layout = QVBoxLayout(); self.tab_apm.setLayout(layout)
        controls = QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QLabel("Ventana (s):"))
        self.apm_window = QComboBox(); self.apm_window.addItems(["15","30","45","60","90","120"]) ; self.apm_window.setCurrentText("60")
        self.apm_window.currentTextChanged.connect(self.update_apm)
        controls.addWidget(self.apm_window)
        controls.addStretch(1)
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
        controls1.addStretch(1)
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
        self.idle_events = QCheckBox("Eventos"); self.idle_events.setChecked(True)
        self.idle_events.stateChanged.connect(self.update_idle)
        controls.addWidget(self.idle_events)
        controls.addStretch(1)
        self.idle_canvas = PlotCanvas(); layout.addWidget(self.idle_canvas)

    def _setup_res_tab(self):
        layout = QVBoxLayout(); self.tab_res.setLayout(layout)
        controls = QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QLabel("Recurso:"))
        self.res_combo = QComboBox(); self.res_combo.addItems(["food","wood","gold","stone"]) ; self.res_combo.currentTextChanged.connect(self.update_res)
        controls.addWidget(self.res_combo)
        controls.addWidget(QLabel("Modo:"))
        # Keep stock analysis in "Stock Total" tab to avoid duplicated views.
        self.res_mode = QComboBox(); self.res_mode.addItems(["Gasto", "Balance aprox.", "Postgame (si existe)"]) ; self.res_mode.setCurrentText("Gasto")
        self.res_mode.currentTextChanged.connect(self.update_res)
        # Initial stock for Balance aprox.
        controls.addWidget(QLabel("Stock inicial:"))
        self.res_stock = QSpinBox(); self.res_stock.setRange(0, 100000); self.res_stock.setValue(0)
        self.res_stock.valueChanged.connect(self.update_res)
        controls.addWidget(self.res_stock)
        # Toggle significant events
        self.res_events = QCheckBox("Eventos importantes"); self.res_events.setChecked(True)
        self.res_events.stateChanged.connect(self.update_res)
        controls.addWidget(self.res_events)
        controls.addWidget(QLabel("Ventana (s):"))
        self.res_window = QComboBox(); self.res_window.addItems(["15","30","45","60","90","120"]) ; self.res_window.setCurrentText("60")
        self.res_window.currentTextChanged.connect(self.update_res)
        controls.addWidget(self.res_window)
        controls.addStretch(1)
        self.res_canvas = PlotCanvas(); layout.addWidget(self.res_canvas)

    def _setup_stock_tab(self):
        layout = QVBoxLayout(); self.tab_stock.setLayout(layout)
        self.stock_canvas = PlotCanvas(); layout.addWidget(self.stock_canvas)

    def _setup_map_tab(self):
        root = QHBoxLayout(); self.tab_map.setLayout(root)

        # Left analytics sidebar (filters + toggles + bookmarks).
        self.map_sidebar = QFrame()
        self.map_sidebar.setObjectName("ControlPanel")
        self.map_sidebar.setMinimumWidth(300)
        self.map_sidebar.setMaximumWidth(420)
        sidebar_layout = QVBoxLayout(); self.map_sidebar.setLayout(sidebar_layout)

        sidebar_layout.addWidget(QLabel("Filtros de visualizacion"))
        sidebar_layout.addWidget(QLabel("Capa:"))
        self.map_layer_combo = QComboBox()
        self.map_layer_combo.addItems(["Actividad", "Propio", "Enemigo", "Edificios", "Presión"])
        self.map_layer_combo.setCurrentText("Actividad")
        self.map_layer_combo.currentTextChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_layer_combo)

        sidebar_layout.addWidget(QLabel("Jugador:"))
        self.map_player_combo = QComboBox(); self.map_player_combo.addItem("Todos")
        self.map_player_combo.currentTextChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_player_combo)

        sidebar_layout.addWidget(QLabel("Tipo de accion:"))
        self.map_family_combo = QComboBox()
        self.map_family_combo.addItems(["Todos", "movement", "build", "production", "military", "research", "economy", "other"])
        self.map_family_combo.currentTextChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_family_combo)

        sidebar_layout.addWidget(QLabel("Ventana pulso (s):"))
        self.map_window_combo = QComboBox(); self.map_window_combo.addItems(["5", "10", "20", "30", "60"]); self.map_window_combo.setCurrentText("20")
        self.map_window_combo.currentTextChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_window_combo)

        sidebar_layout.addWidget(QLabel("Resolucion NxN:"))
        self.map_grid_combo = QComboBox()
        self.map_grid_combo.addItems([f"{self.map_fixed_grid_size} (fijo)"])
        self.map_grid_combo.setEnabled(False)
        sidebar_layout.addWidget(self.map_grid_combo)

        self.map_key_objects_check = QCheckBox("Mostrar TC/Castillos")
        self.map_key_objects_check.setChecked(True)
        self.map_key_objects_check.stateChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_key_objects_check)

        self.map_resources_check = QCheckBox("Mostrar recursos (madera/oro/piedra/alimento)")
        self.map_resources_check.setChecked(True)
        self.map_resources_check.stateChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_resources_check)

        self.map_pulses_check = QCheckBox("Mostrar pulsos de movimiento")
        self.map_pulses_check.setChecked(True)
        self.map_pulses_check.stateChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_pulses_check)

        self.map_buildings_check = QCheckBox("Mostrar edificios persistentes")
        self.map_buildings_check.setChecked(True)
        self.map_buildings_check.stateChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_buildings_check)

        self.map_cinematic_check = QCheckBox("Modo cinematica de movimiento")
        self.map_cinematic_check.setChecked(True)
        self.map_cinematic_check.stateChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_cinematic_check)

        sidebar_layout.addWidget(QLabel("Suavizado movimiento:"))
        self.map_cine_smooth_combo = QComboBox()
        self.map_cine_smooth_combo.addItems(["Suave", "Medio", "Fuerte"])
        self.map_cine_smooth_combo.setCurrentText("Medio")
        self.map_cine_smooth_combo.currentTextChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_cine_smooth_combo)

        sidebar_layout.addWidget(QLabel("Zoom dinamico:"))
        self.map_cine_zoom_combo = QComboBox()
        self.map_cine_zoom_combo.addItems(["Amplio", "Normal", "Cercano"])
        self.map_cine_zoom_combo.setCurrentText("Normal")
        self.map_cine_zoom_combo.currentTextChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_cine_zoom_combo)

        sidebar_layout.addWidget(QLabel("Bookmarks (doble click para ir):"))
        self.map_bookmarks = QListWidget()
        self.map_bookmarks.setObjectName("BookmarkList")
        self.map_bookmarks.setSelectionMode(QAbstractItemView.SingleSelection)
        self.map_bookmarks.itemDoubleClicked.connect(self.go_to_selected_bookmark)
        sidebar_layout.addWidget(self.map_bookmarks, 1)

        bookmarks_controls = QHBoxLayout()
        self.map_add_bookmark_btn = QPushButton("Agregar")
        self.map_add_bookmark_btn.clicked.connect(self.add_map_bookmark)
        bookmarks_controls.addWidget(self.map_add_bookmark_btn)
        self.map_remove_bookmark_btn = QPushButton("Eliminar")
        self.map_remove_bookmark_btn.clicked.connect(self.remove_map_bookmark)
        bookmarks_controls.addWidget(self.map_remove_bookmark_btn)
        self.map_clear_bookmarks_btn = QPushButton("Limpiar")
        self.map_clear_bookmarks_btn.clicked.connect(self.clear_map_bookmarks)
        bookmarks_controls.addWidget(self.map_clear_bookmarks_btn)
        sidebar_layout.addLayout(bookmarks_controls)

        sidebar_layout.addWidget(QLabel("Log analitico"))
        self.map_log_window_combo = QComboBox()
        self.map_log_window_combo.addItems(["30s", "60s", "120s", "300s", "Todo"])
        self.map_log_window_combo.setCurrentText("120s")
        self.map_log_window_combo.currentTextChanged.connect(self.update_map)
        sidebar_layout.addWidget(self.map_log_window_combo)
        self.map_event_log_list = QListWidget()
        self.map_event_log_list.setObjectName("BookmarkList")
        sidebar_layout.addWidget(self.map_event_log_list, 1)

        # Right: big map canvas + playback strip.
        right_wrap = QVBoxLayout()
        timeline = QFrame()
        timeline.setObjectName("ControlPanel")
        timeline_layout = QHBoxLayout(); timeline.setLayout(timeline_layout)
        timeline_layout.addWidget(QLabel("Tiempo:"))
        self.map_slider = QSlider(QtCore.Qt.Horizontal)
        self.map_slider.setMinimum(0); self.map_slider.setMaximum(1); self.map_slider.setValue(0)
        self.map_slider.setSingleStep(1); self.map_slider.valueChanged.connect(self.update_map)
        timeline_layout.addWidget(self.map_slider, 1)
        self.map_time_label = QLabel("0:00")
        self.map_time_label.setMinimumWidth(54)
        timeline_layout.addWidget(self.map_time_label)
        self.map_play_btn = QPushButton("Play")
        self.map_play_btn.setObjectName("PrimaryButton")
        self.map_play_btn.clicked.connect(self.toggle_map_playback)
        timeline_layout.addWidget(self.map_play_btn)
        timeline_layout.addWidget(QLabel("Velocidad:"))
        self.map_speed_combo = QComboBox()
        self.map_speed_combo.addItems(["0.5x", "1x", "2x", "4x"])
        self.map_speed_combo.setCurrentText("1x")
        timeline_layout.addWidget(self.map_speed_combo)
        self.map_sidebar_toggle_btn = QPushButton("Ocultar filtros")
        self.map_sidebar_toggle_btn.clicked.connect(self._toggle_map_sidebar)
        timeline_layout.addWidget(self.map_sidebar_toggle_btn)
        timeline_layout.addStretch(1)

        self.map_canvas = PlotCanvas()
        self.map_canvas.mpl_connect("motion_notify_event", self._on_map_hover)
        right_wrap.addWidget(timeline)
        right_wrap.addWidget(self.map_canvas, 1)

        root.addWidget(self.map_sidebar)
        root.addLayout(right_wrap, 1)

    def _apply_base_layouts(self):
        # Consistent whitespace and visual rhythm across all tabs.
        compact = (self.ui_layout_mode == "compact")
        margin = 10 if compact else 14
        spacing = 7 if compact else 10
        tab_spacing = 8 if compact else 12
        tabs = [self.tab_apm, self.tab_units, self.tab_idle, self.tab_res, self.tab_stock, self.tab_score, self.tab_kpis, self.tab_map]
        for tab in tabs:
            lay = tab.layout()
            if lay is None:
                continue
            lay.setContentsMargins(margin, margin - 2, margin, margin - 2)
            lay.setSpacing(spacing)
        for lay in [self.tab_apm.layout(), self.tab_units.layout(), self.tab_idle.layout(), self.tab_res.layout(), self.tab_kpis.layout(), self.tab_map.layout()]:
            if lay is not None:
                lay.setSpacing(tab_spacing)
        if hasattr(self, "units_players_list"):
            self.units_players_list.setMaximumHeight(96 if compact else 120)
        if hasattr(self, "map_bookmarks"):
            self.map_bookmarks.setMinimumHeight(150 if compact else 220)
        if hasattr(self, "map_time_label"):
            self.map_time_label.setMinimumWidth(46 if compact else 54)

    def _apply_qt_style(self, dark: bool):
        compact = (self.ui_layout_mode == "compact")
        tab_pad_v = 6 if compact else 8
        tab_pad_h = 10 if compact else 14
        input_pad_v = 4 if compact else 5
        input_pad_h = 7 if compact else 8
        input_min_h = 26 if compact else 28
        btn_pad_v = 5 if compact else 6
        btn_pad_h = 10 if compact else 12
        btn_min_h = 28 if compact else 30
        if dark:
            bg = "#0f141c"; panel = "#161d28"; panel_alt = "#1a2330"; border = "#2b3646"; text = "#e8eef7"
            muted = "#9fb0c5"; accent = "#43a7ff"; accent_hover = "#5ab2ff"; accent_press = "#2d8fe8"
            input_bg = "#1a2230"; list_sel = "#27496d"; tab_bg = "#131a24"; tab_sel = "#1f2b3b"
            status_bg = "#101722"; plot_bg = "#151d28"
        else:
            bg = "#eef2f7"; panel = "#ffffff"; panel_alt = "#f5f8fc"; border = "#cfd8e3"; text = "#16202b"
            muted = "#516173"; accent = "#1168cc"; accent_hover = "#1d79e3"; accent_press = "#0a58b2"
            input_bg = "#ffffff"; list_sel = "#cfe3ff"; tab_bg = "#e5ebf3"; tab_sel = "#ffffff"
            status_bg = "#e9eef5"; plot_bg = "#ffffff"

        self.setStyleSheet(f"""
            QMainWindow {{
                background: {bg};
                color: {text};
            }}
            QTabWidget::pane {{
                border: 1px solid {border};
                background: {panel};
                border-radius: 10px;
                top: -1px;
            }}
            QTabBar::tab {{
                background: {tab_bg};
                color: {muted};
                border: 1px solid {border};
                border-bottom: none;
                padding: {tab_pad_v}px {tab_pad_h}px;
                min-width: 92px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {tab_sel};
                color: {text};
            }}
            QTabBar::tab:hover {{
                color: {text};
            }}
            QMenuBar {{
                background: {panel_alt};
                color: {text};
                border-bottom: 1px solid {border};
                padding: 2px;
            }}
            QMenuBar::item {{
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QMenuBar::item:selected {{
                background: {tab_sel};
            }}
            QMenu {{
                background: {panel};
                border: 1px solid {border};
                padding: 6px;
            }}
            QMenu::item {{
                padding: 7px 16px;
                border-radius: 5px;
            }}
            QMenu::item:selected {{
                background: {panel_alt};
            }}
            QFrame#ControlPanel {{
                background: {panel_alt};
                border: 1px solid {border};
                border-radius: 9px;
                padding: 6px;
            }}
            QLabel {{
                color: {text};
            }}
            QComboBox, QSpinBox, QListWidget, QLineEdit {{
                background: {input_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 7px;
                padding: {input_pad_v}px {input_pad_h}px;
                min-height: {input_min_h}px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QAbstractItemView {{
                background: {input_bg};
                color: {text};
                selection-background-color: {list_sel};
                border: 1px solid {border};
            }}
            QCheckBox {{
                spacing: 8px;
                color: {text};
            }}
            QSlider::groove:horizontal {{
                border: none;
                height: 6px;
                border-radius: 3px;
                background: {border};
            }}
            QSlider::handle:horizontal {{
                background: {accent};
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QPushButton {{
                background: {panel_alt};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: {btn_pad_v}px {btn_pad_h}px;
                min-height: {btn_min_h}px;
            }}
            QPushButton:hover {{
                border-color: {accent};
            }}
            QPushButton:pressed {{
                background: {tab_bg};
            }}
            QPushButton#PrimaryButton {{
                background: {accent};
                color: #ffffff;
                border: 1px solid {accent};
                font-weight: 600;
            }}
            QPushButton#PrimaryButton:hover {{
                background: {accent_hover};
                border-color: {accent_hover};
            }}
            QPushButton#PrimaryButton:pressed {{
                background: {accent_press};
                border-color: {accent_press};
            }}
            QListWidget#BookmarkList {{
                background: {input_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QStatusBar {{
                background: {status_bg};
                color: {text};
                border-top: 1px solid {border};
            }}
            QToolTip {{
                background: {plot_bg};
                color: {text};
                border: 1px solid {border};
                padding: 4px;
            }}
        """)

    def _set_layout_analyst(self, *_):
        self.ui_layout_mode = "analyst"
        self.layout_analyst_action.setChecked(True)
        self.layout_compact_action.setChecked(False)
        self._apply_base_layouts()
        self._apply_theme_all()
        self._on_tab_changed(self.tabs.currentIndex())

    def _set_layout_compact(self, *_):
        self.ui_layout_mode = "compact"
        self.layout_analyst_action.setChecked(False)
        self.layout_compact_action.setChecked(True)
        self._apply_base_layouts()
        self._apply_theme_all()
        self._on_tab_changed(self.tabs.currentIndex())

    # ---- Actions ----
    def open_replay(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona .aoe2record", filter="AoE2 Replay (*.aoe2record)")
        if not path:
            return
        self.replay_files = []
        self.replay_index = -1
        self._load_replay_path(Path(path))

    @staticmethod
    def _extract_game_ids_from_history(payload) -> list[int]:
        if not isinstance(payload, dict):
            return []
        rows = payload.get("matchHistoryStats") or payload.get("match_history_stats") or []
        if not isinstance(rows, list):
            return []
        ids: list[int] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw = row.get("id") or row.get("match_id") or row.get("matchhistory_id")
            try:
                gid = int(raw)
            except Exception:
                continue
            if gid > 0:
                ids.append(gid)
        # Keep order and dedupe
        seen: set[int] = set()
        deduped: list[int] = []
        for gid in ids:
            if gid in seen:
                continue
            seen.add(gid)
            deduped.append(gid)
        return deduped

    def _fetch_recent_game_ids_by_aliases(self, aliases: list[str], per_player_count: int, matchtype_id: int | None) -> list[int]:
        endpoint = "https://aoe-api.reliclink.com/community/leaderboard/getRecentMatchHistory"
        all_ids: list[int] = []
        for alias in aliases:
            a = alias.strip()
            if not a:
                continue
            params = {
                "title": "age2",
                "aliases": json.dumps([a]),
            }
            if matchtype_id is not None:
                params["matchtype_id"] = str(int(matchtype_id))
            resp = requests.get(endpoint, params=params, timeout=45)
            resp.raise_for_status()
            ids = self._extract_game_ids_from_history(resp.json())[: max(1, int(per_player_count))]
            all_ids.extend(ids)
        seen: set[int] = set()
        deduped: list[int] = []
        for gid in all_ids:
            if gid in seen:
                continue
            seen.add(gid)
            deduped.append(gid)
        return deduped

    def download_recent_replays_by_alias(self):
        aliases_raw, ok = QInputDialog.getText(
            self,
            "Descargar recientes",
            "Jugadores (separados por coma):",
            text="Hera, Liereyy",
        )
        if not ok:
            return
        aliases = [x.strip() for x in str(aliases_raw).split(",") if x.strip()]
        if not aliases:
            QMessageBox.information(self, "Sin jugadores", "No se ingresaron aliases de jugadores.")
            return
        count, ok = QInputDialog.getInt(
            self,
            "Descargar recientes",
            "Partidas por jugador:",
            value=3,
            min=1,
            max=50,
        )
        if not ok:
            return
        matchtype, ok = QInputDialog.getInt(
            self,
            "Descargar recientes",
            "matchtype_id (0 = sin filtro):",
            value=0,
            min=0,
            max=1000,
        )
        if not ok:
            return
        folder = QFileDialog.getExistingDirectory(self, "Carpeta destino para descargas", str((Path.cwd() / "downloads").resolve()))
        if not folder:
            return
        download_dir = Path(folder)
        download_dir.mkdir(parents=True, exist_ok=True)

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            game_ids = self._fetch_recent_game_ids_by_aliases(
                aliases=aliases,
                per_player_count=int(count),
                matchtype_id=(None if int(matchtype) == 0 else int(matchtype)),
            )
            if not game_ids:
                QMessageBox.information(self, "Sin partidas", "No se encontraron partidas recientes para los jugadores indicados.")
                return

            downloaded: list[Path] = []
            for gid in game_ids:
                dest = download_dir / f"AgeIIDE_Replay_{gid}.aoe2record"
                path = ParserLayer.download_replay(int(gid), dest=dest)
                downloaded.append(path)

            self.replay_files = downloaded
            self.replay_index = 0
            self._load_replay_path(self.replay_files[0])
            QMessageBox.information(
                self,
                "Descarga completa",
                f"Descargadas {len(downloaded)} partidas.\nPrimera partida cargada en la GUI.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron descargar partidas recientes:\n{e}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def open_replay_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecciona carpeta con replays")
        if not folder:
            return
        root = Path(folder)
        # Include both current folder and subfolders for convenience.
        files = sorted(root.rglob("*.aoe2record"))
        if not files:
            QMessageBox.information(self, "Sin replays", "No se encontraron archivos .aoe2record en la carpeta seleccionada.")
            return
        self.replay_files = files
        self.replay_index = 0
        self._choose_replay_from_folder(default_index=0)

    def open_prev_replay(self):
        if not self.replay_files:
            QMessageBox.information(self, "Sin carpeta", "Primero abrí una carpeta de replays para navegar.")
            return
        self.replay_index = (self.replay_index - 1) % len(self.replay_files)
        self._load_replay_path(self.replay_files[self.replay_index])

    def open_next_replay(self):
        if not self.replay_files:
            QMessageBox.information(self, "Sin carpeta", "Primero abrí una carpeta de replays para navegar.")
            return
        self.replay_index = (self.replay_index + 1) % len(self.replay_files)
        self._load_replay_path(self.replay_files[self.replay_index])

    def _choose_replay_from_folder(self, default_index: int = 0):
        labels = [f"{i+1:03d} - {p.name}" for i, p in enumerate(self.replay_files)]
        default_index = max(0, min(default_index, len(labels) - 1))
        selection, ok = QInputDialog.getItem(
            self,
            "Seleccionar replay",
            "Replay:",
            labels,
            default_index,
            False,
        )
        if not ok or not selection:
            return
        chosen_index = labels.index(selection)
        self.replay_index = chosen_index
        self._load_replay_path(self.replay_files[chosen_index])

    def _load_replay_path(self, replay_path: Path):
        try:
            self.map_playback_is_running = False
            self.map_playback_timer.stop()
            self.map_cine_heat = None
            self.map_cine_center = None
            self.map_cine_radius = None
            self.map_last_time = None
            self.map_cine_signature = None
            if hasattr(self, "map_play_btn"):
                self.map_play_btn.setText("Play")
            self.match = load_match(str(replay_path))
            self.replay_path = replay_path
            self.events_df = extract_raw_events(self.match, match_id=self.replay_path.stem)
            self.map_initial_tcs_df = self._extract_initial_tcs()
            self.map_key_objects_df = self._extract_key_objects()
            self.map_resource_df = self._extract_gaia_resources()
            self.map_build_events_df = self._extract_building_events()
            self.map_delete_events_df = self._extract_delete_events()
            self.map_event_log_df = self._build_map_event_log()
            self._refresh_bookmarks_ui()
            # Populate players list
            self.units_players_list.clear()
            for p in self.match.players:
                item = QListWidgetItem(p.name)
                item.setData(1, int(p.number))
                item.setSelected(True)
                self.units_players_list.addItem(item)
            self.map_player_combo.blockSignals(True)
            self.map_player_combo.clear()
            self.map_player_combo.addItem("Todos")
            for p in self.match.players:
                self.map_player_combo.addItem(p.name)
            self.map_player_combo.blockSignals(False)
            # Trigger updates
            self._apply_theme_all()
            try:
                self.map_slider.setMaximum(max(1, int(self.match.duration.total_seconds())))
                self.map_slider.setValue(0)
            except Exception:
                pass
            self.update_apm(); self.update_units(); self.update_idle(); self.update_res(); self.update_stock(); self.update_score(); self.update_kpis(); self.update_map()
            self._update_replay_status()
        except Exception as e:  # pragma: no cover
            QMessageBox.critical(self, "Error", f"No se pudo abrir el replay:\n{e}\n\n{traceback.format_exc()}")

    def _update_replay_status(self):
        if self.replay_files and 0 <= self.replay_index < len(self.replay_files):
            self.statusBar().showMessage(
                f"Replay {self.replay_index + 1}/{len(self.replay_files)}: {self.replay_files[self.replay_index].name}"
            )
        elif self.replay_path is not None:
            self.statusBar().showMessage(f"Replay: {self.replay_path.name}")

    def _current_replay_key(self) -> str | None:
        if self.replay_path is None:
            return None
        return str(self.replay_path.resolve())

    @staticmethod
    def _fmt_time(sec: float) -> str:
        s = max(0, int(round(float(sec))))
        return f"{s//60}:{s%60:02d}"

    def _refresh_bookmarks_ui(self):
        self.map_bookmarks.clear()
        key = self._current_replay_key()
        if key is None:
            return
        bookmarks = self.bookmarks_by_replay.get(key, [])
        for bm in bookmarks:
            t = float(bm.get("time_sec", 0.0))
            label = str(bm.get("label", "")).strip()
            title = f"{self._fmt_time(t)} - {label}" if label else self._fmt_time(t)
            item = QListWidgetItem(title)
            item.setData(1, t)
            self.map_bookmarks.addItem(item)

    def add_map_bookmark(self):
        if self.match is None:
            return
        t = float(self.map_slider.value()) if hasattr(self, "map_slider") else 0.0
        label, ok = QInputDialog.getText(self, "Nuevo bookmark", "Etiqueta (opcional):")
        if not ok:
            return
        key = self._current_replay_key()
        if key is None:
            return
        bookmarks = self.bookmarks_by_replay.setdefault(key, [])
        bookmarks.append({"time_sec": float(t), "label": str(label).strip()})
        bookmarks.sort(key=lambda x: float(x.get("time_sec", 0.0)))
        self._refresh_bookmarks_ui()
        self.statusBar().showMessage(f"Bookmark agregado en {self._fmt_time(t)}", 4000)

    def remove_map_bookmark(self):
        key = self._current_replay_key()
        if key is None:
            return
        current = self.map_bookmarks.currentItem()
        if current is None:
            return
        t = float(current.data(1))
        bookmarks = self.bookmarks_by_replay.get(key, [])
        for idx, bm in enumerate(bookmarks):
            if abs(float(bm.get("time_sec", 0.0)) - t) < 0.5:
                bookmarks.pop(idx)
                break
        self._refresh_bookmarks_ui()
        self.statusBar().showMessage("Bookmark eliminado", 3000)

    def clear_map_bookmarks(self):
        key = self._current_replay_key()
        if key is None:
            return
        self.bookmarks_by_replay[key] = []
        self._refresh_bookmarks_ui()
        self.statusBar().showMessage("Bookmarks limpiados", 3000)

    def go_to_selected_bookmark(self, *_):
        current = self.map_bookmarks.currentItem()
        if current is None:
            return
        t = int(float(current.data(1)))
        self.map_slider.setValue(max(self.map_slider.minimum(), min(self.map_slider.maximum(), t)))
        self.update_map()

    def _playback_speed(self) -> float:
        raw = self.map_speed_combo.currentText().strip().lower().replace("x", "")
        try:
            return max(0.1, float(raw))
        except Exception:
            return 1.0

    def toggle_map_playback(self):
        if self.match is None:
            return
        self.map_playback_is_running = not self.map_playback_is_running
        if self.map_playback_is_running:
            self.map_playback_pos = float(self.map_slider.value())
            self.map_play_btn.setText("Pausa")
            self.map_playback_timer.start()
        else:
            self.map_play_btn.setText("Play")
            self.map_playback_timer.stop()

    def _playback_tick(self):
        if not self.map_playback_is_running:
            return
        max_t = float(self.map_slider.maximum())
        step_sec = (self.map_playback_timer.interval() / 1000.0) * self._playback_speed()
        self.map_playback_pos += step_sec
        if self.map_playback_pos >= max_t:
            self.map_playback_pos = max_t
            self.map_slider.setValue(int(self.map_playback_pos))
            self.map_playback_is_running = False
            self.map_play_btn.setText("Play")
            self.map_playback_timer.stop()
            return
        self.map_slider.setValue(int(self.map_playback_pos))

    def _extract_key_objects(self):
        import pandas as pd
        frames = []
        if self.events_df is not None and not self.events_df.empty and "payload_json" in self.events_df.columns:
            df = self.events_df
            base = df[
                (df["action_type"] == "BUILD")
                & df["x"].notna()
                & df["y"].notna()
                & df["player_id"].notna()
            ].copy()
            if not base.empty:
                payload_lower = base["payload_json"].astype(str).str.lower()
                is_tc = payload_lower.str.contains("town center", regex=False) | payload_lower.str.contains("centro urbano", regex=False)
                is_castle = payload_lower.str.contains("castle", regex=False) | payload_lower.str.contains("castillo", regex=False)
                key = base[is_tc | is_castle].copy()
                if not key.empty:
                    key["object_kind"] = np.where((is_tc[is_tc | is_castle]).to_numpy(), "tc", "castle")
                    key["x_round"] = key["x"].astype(float).round(1)
                    key["y_round"] = key["y"].astype(float).round(1)
                    key["t_round"] = key["time_sec"].astype(float).round(1)
                    key = key.drop_duplicates(subset=["player_id", "object_kind", "x_round", "y_round", "t_round"], keep="first")
                    team_map = self._player_team_map()
                    key["team_id"] = key["player_id"].map(lambda pid: team_map.get(int(pid), int(pid)))
                    frames.append(key[["time_sec", "player_id", "player_name", "team_id", "x", "y", "object_kind"]].copy())
        if self.map_initial_tcs_df is not None and not self.map_initial_tcs_df.empty:
            frames.append(self.map_initial_tcs_df.copy())
        if not frames:
            return None
        out = pd.concat(frames, ignore_index=True)
        return out.sort_values("time_sec")

    def _player_team_map(self) -> dict[int, int]:
        out: dict[int, int] = {}
        if not self.match:
            return out
        for p in self.match.players:
            pid = int(getattr(p, "number", 0) or 0)
            team_raw = getattr(p, "team_id", None)
            team_id = pid
            if isinstance(team_raw, (list, tuple)) and len(team_raw) > 0:
                team_id = int(team_raw[0])
            elif team_raw is not None:
                try:
                    team_id = int(team_raw)
                except Exception:
                    team_id = pid
            out[pid] = team_id
        return out

    def _map_cine_params(self) -> tuple[float, float, float]:
        # Returns (heat_decay, camera_lerp, zoom_factor)
        smooth_text = self.map_cine_smooth_combo.currentText() if hasattr(self, "map_cine_smooth_combo") else "Medio"
        if smooth_text == "Suave":
            heat_decay = 0.90
            camera_lerp = 0.14
        elif smooth_text == "Fuerte":
            heat_decay = 0.74
            camera_lerp = 0.28
        else:
            heat_decay = 0.82
            camera_lerp = 0.20

        zoom_text = self.map_cine_zoom_combo.currentText() if hasattr(self, "map_cine_zoom_combo") else "Normal"
        if zoom_text == "Amplio":
            zoom_factor = 1.25
        elif zoom_text == "Cercano":
            zoom_factor = 0.78
        else:
            zoom_factor = 1.0
        return heat_decay, camera_lerp, zoom_factor

    @staticmethod
    def _heat_from_cells(gx: np.ndarray, gy: np.ndarray, grid_size: int, weights: np.ndarray | None = None) -> np.ndarray:
        heat = np.zeros((grid_size, grid_size), dtype=float)
        if len(gx) == 0:
            return heat
        if weights is None:
            for cx, cy in zip(gx, gy):
                heat[grid_size - 1 - int(cy), int(cx)] += 1.0
            return heat
        for cx, cy, w in zip(gx, gy, weights):
            heat[grid_size - 1 - int(cy), int(cx)] += float(w)
        return heat

    def _selected_player_team_id(self, selected_player: str) -> int | None:
        if not self.match or selected_player == "Todos":
            return None
        team_map = self._player_team_map()
        for p in self.match.players:
            if p.name == selected_player:
                return int(team_map.get(int(p.number), int(p.number)))
        return None

    def _toggle_map_sidebar(self):
        if not hasattr(self, "map_sidebar"):
            return
        is_visible = self.map_sidebar.isVisible()
        self.map_sidebar.setVisible(not is_visible)
        if hasattr(self, "map_sidebar_toggle_btn"):
            self.map_sidebar_toggle_btn.setText("Mostrar filtros" if is_visible else "Ocultar filtros")

    def _set_map_hover_items(self, items: list[dict[str, float | str]]):
        self.map_hover_items = items
        if self.map_hover_annotation is not None:
            self.map_hover_annotation.set_visible(False)

    def _on_map_hover(self, event):
        if self.map_canvas is None or event is None:
            return
        if self.map_hover_annotation is None:
            ax = self.map_canvas.ax
            self.map_hover_annotation = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(10, 10),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.3", fc="#0f1116" if self.map_canvas.dark else "#ffffff", ec="#777777", alpha=0.95),
                color="#f0f0f0" if self.map_canvas.dark else "#111111",
                fontsize=8,
            )
            self.map_hover_annotation.set_visible(False)
        if event.inaxes != self.map_canvas.ax or event.xdata is None or event.ydata is None or not self.map_hover_items:
            if self.map_hover_annotation.get_visible():
                self.map_hover_annotation.set_visible(False)
                self.map_canvas.draw_idle()
            return
        x = float(event.xdata)
        y = float(event.ydata)
        xlim = self.map_canvas.ax.get_xlim()
        ylim = self.map_canvas.ax.get_ylim()
        xrange = abs(float(xlim[1] - xlim[0])) if xlim is not None else 10.0
        yrange = abs(float(ylim[1] - ylim[0])) if ylim is not None else 10.0
        threshold = max(0.8, min(xrange, yrange) / 28.0)
        best = None
        best_d = 1e9
        for item in self.map_hover_items:
            ix = float(item.get("x", -9999.0))
            iy = float(item.get("y", -9999.0))
            d = float(((ix - x) ** 2 + (iy - y) ** 2) ** 0.5)
            if d < best_d:
                best_d = d
                best = item
        if best is None or best_d > threshold:
            if self.map_hover_annotation.get_visible():
                self.map_hover_annotation.set_visible(False)
                self.map_canvas.draw_idle()
            return
        self.map_hover_annotation.xy = (float(best["x"]), float(best["y"]))
        self.map_hover_annotation.set_text(str(best.get("text", "")))
        self.map_hover_annotation.get_bbox_patch().set_facecolor("#0f1116" if self.map_canvas.dark else "#ffffff")
        self.map_hover_annotation.get_bbox_patch().set_edgecolor("#777777")
        self.map_hover_annotation.set_color("#f0f0f0" if self.map_canvas.dark else "#111111")
        if not self.map_hover_annotation.get_visible():
            self.map_hover_annotation.set_visible(True)
        self.map_canvas.draw_idle()

    def _extract_initial_tcs(self):
        if not self.match:
            return None
        rows = []
        team_map = self._player_team_map()
        for p in self.match.players:
            pid = int(getattr(p, "number", 0) or 0)
            pname = str(getattr(p, "name", "") or "")
            team_id = int(team_map.get(pid, pid))
            objs = list(getattr(p, "objects", []) or [])
            for o in objs:
                name = str(getattr(o, "name", "") or "").strip().lower()
                if name != "town center":
                    continue
                pos = getattr(o, "position", None)
                if pos is None:
                    continue
                x = float(getattr(pos, "x", np.nan))
                y = float(getattr(pos, "y", np.nan))
                if not np.isfinite(x) or not np.isfinite(y):
                    continue
                rows.append((0.0, pid, pname, team_id, x, y, "tc_initial"))
        if not rows:
            return None
        import pandas as pd
        df = pd.DataFrame(rows, columns=["time_sec", "player_id", "player_name", "team_id", "x", "y", "object_kind"])
        df["x_round"] = df["x"].round(1)
        df["y_round"] = df["y"].round(1)
        df = df.drop_duplicates(subset=["player_id", "object_kind", "x_round", "y_round"], keep="first")
        return df[["time_sec", "player_id", "player_name", "team_id", "x", "y", "object_kind"]]

    def _build_map_event_log(self):
        if self.events_df is None or self.events_df.empty:
            return None
        import pandas as pd
        rows: list[tuple[float, str]] = []
        df = self.events_df.sort_values("time_sec")
        for _, r in df.iterrows():
            t = float(r.get("time_sec", 0.0))
            a = str(r.get("action_type", "") or "")
            pname = str(r.get("player_name", "") or "")
            if a not in {"BUILD", "DELETE", "RESEARCH", "DE_ATTACK_MOVE", "PATROL", "TRAIN", "QUEUE"}:
                continue
            detail = ""
            try:
                p = json.loads(str(r.get("payload_json", "{}")))
                if a == "BUILD":
                    detail = str(p.get("building", "") or "")
                elif a == "RESEARCH":
                    detail = str(p.get("technology", "") or p.get("tech", "") or "")
                elif a in {"TRAIN", "QUEUE"}:
                    detail = str(p.get("unit", "") or p.get("object", "") or "")
            except Exception:
                detail = ""
            ts = self._fmt_time(t)
            txt = f"{ts} | {pname or 'N/A'} | {a}"
            if detail:
                txt += f" | {detail}"
            rows.append((t, txt))
        try:
            ev = important_events(self.match)
            for _, r in ev.iterrows():
                t = float(r.get("time_sec", 0.0))
                pid = int(r.get("player", 0) or 0)
                pname = next((str(p.name) for p in self.match.players if int(p.number) == pid), f"P{pid}")
                lbl = str(r.get("label", "") or "")
                kind = str(r.get("kind", "") or "")
                rows.append((t, f"{self._fmt_time(t)} | {pname} | HITO {kind.upper()} | {lbl}"))
        except Exception:
            pass
        if not rows:
            return None
        out = pd.DataFrame(rows, columns=["time_sec", "text"]).sort_values("time_sec")
        out = out.drop_duplicates(subset=["text"], keep="first")
        return out

    def _extract_building_events(self):
        if self.events_df is None or self.events_df.empty:
            return None
        df = self.events_df
        base = df[(df["action_type"] == "BUILD") & df["x"].notna() & df["y"].notna()].copy()
        if base.empty:
            return None

        def _building_name(payload_json: str) -> str:
            try:
                payload = json.loads(str(payload_json))
                return str(payload.get("building", "") or "").strip().lower()
            except Exception:
                return ""

        base["building_name"] = base["payload_json"].map(_building_name)
        base = base[base["building_name"] != ""]
        if base.empty:
            return None
        team_map = self._player_team_map()
        base["team_id"] = base["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid)))
        return base[["time_sec", "player_id", "player_name", "team_id", "x", "y", "building_name"]].sort_values("time_sec")

    def _extract_delete_events(self):
        if self.events_df is None or self.events_df.empty:
            return None
        df = self.events_df
        out = df[(df["action_type"] == "DELETE") & df["x"].notna() & df["y"].notna()].copy()
        if out.empty:
            return None
        team_map = self._player_team_map()
        out["team_id"] = out["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid)))
        return out[["time_sec", "player_id", "player_name", "team_id", "x", "y"]].sort_values("time_sec")

    def _extract_gaia_resources(self):
        if not self.match:
            return None
        gaia = getattr(self.match, "gaia", None)
        if not gaia:
            return None

        # Heuristic mapping of object ids/classes used by DE maps.
        gold_ids = {66}
        stone_ids = {102, 69}
        wood_class_ids = {10, 20}
        food_class_ids = {70}
        rows = []
        for obj in gaia:
            pos = getattr(obj, "position", None)
            if pos is None:
                continue
            x = float(getattr(pos, "x", np.nan))
            y = float(getattr(pos, "y", np.nan))
            if not np.isfinite(x) or not np.isfinite(y):
                continue
            oid = int(getattr(obj, "object_id", 0) or 0)
            cid = int(getattr(obj, "class_id", 0) or 0)
            rtype = None
            if oid in gold_ids:
                rtype = "gold"
            elif oid in stone_ids:
                rtype = "stone"
            elif cid in wood_class_ids:
                rtype = "wood"
            elif cid in food_class_ids:
                rtype = "food"
            if rtype is None:
                continue
            rows.append((x, y, oid, cid, rtype))
        if not rows:
            return None
        import pandas as pd
        return pd.DataFrame(rows, columns=["x", "y", "object_id", "class_id", "resource_type"])

    def _building_heat_persistent(self, t: float, grid_size: int, map_dim: float, selected_player: str, layer: str) -> np.ndarray:
        heat = np.zeros((grid_size, grid_size), dtype=float)
        if self.map_build_events_df is None or self.map_build_events_df.empty:
            return heat
        bdf = self.map_build_events_df[self.map_build_events_df["time_sec"] <= t].copy()
        if bdf.empty:
            return heat
        ddf = self.map_delete_events_df
        team_ref = self._selected_player_team_id(selected_player)
        if selected_player != "Todos" and layer in ("Actividad", "Edificios"):
            bdf = bdf[bdf["player_name"] == selected_player]
            if ddf is not None and not ddf.empty:
                ddf = ddf[(ddf["time_sec"] <= t) & (ddf["player_name"] == selected_player)]
        elif layer in ("Propio", "Enemigo", "Presión"):
            if team_ref is None:
                return heat
            if layer == "Propio":
                bdf = bdf[bdf["team_id"].astype(int) == int(team_ref)]
            elif layer == "Enemigo":
                bdf = bdf[bdf["team_id"].astype(int) != int(team_ref)]
            else:
                own = bdf[bdf["team_id"].astype(int) == int(team_ref)]
                enemy = bdf[bdf["team_id"].astype(int) != int(team_ref)]
                own_h = self._building_heat_from_frames(own, ddf, t, grid_size, map_dim)
                enemy_h = self._building_heat_from_frames(enemy, ddf, t, grid_size, map_dim)
                return enemy_h - own_h
            if ddf is not None and not ddf.empty:
                if layer == "Propio":
                    ddf = ddf[(ddf["time_sec"] <= t) & (ddf["team_id"].astype(int) == int(team_ref))]
                elif layer == "Enemigo":
                    ddf = ddf[(ddf["time_sec"] <= t) & (ddf["team_id"].astype(int) != int(team_ref))]
                else:
                    ddf = ddf[ddf["time_sec"] <= t]
        else:
            if ddf is not None and not ddf.empty:
                ddf = ddf[ddf["time_sec"] <= t]
        return self._building_heat_from_frames(bdf, ddf, t, grid_size, map_dim)

    def _building_heat_from_frames(self, bdf, ddf, t: float, grid_size: int, map_dim: float) -> np.ndarray:
        heat = np.zeros((grid_size, grid_size), dtype=float)
        if bdf is None or bdf.empty:
            return heat
        b_gx = np.floor((bdf["x"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        b_gy = np.floor((bdf["y"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        build_h = self._heat_from_cells(b_gx, b_gy, grid_size)
        if ddf is None or ddf.empty:
            return build_h
        del_df = ddf[ddf["time_sec"] <= t]
        if del_df.empty:
            return build_h
        d_gx = np.floor((del_df["x"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        d_gy = np.floor((del_df["y"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        del_h = self._heat_from_cells(d_gx, d_gy, grid_size)
        return np.maximum(0.0, build_h - del_h)

    def _current_tab_key(self) -> str | None:
        w = self.tabs.currentWidget()
        if w is self.tab_apm:
            return "apm"
        if w is self.tab_units:
            return "units"
        if w is self.tab_idle:
            return "idle"
        if w is self.tab_res:
            return "res"
        if w is self.tab_stock:
            return "stock"
        if w is self.tab_score:
            return "score"
        if w is self.tab_kpis:
            return "kpis"
        if w is self.tab_map:
            return "map"
        return None

    def _canvas_for_key(self, key: str) -> PlotCanvas | None:
        mapping = {
            "apm": self.apm_canvas,
            "units": self.units_canvas,
            "idle": self.idle_canvas,
            "res": self.res_canvas,
            "stock": self.stock_canvas,
            "score": self.score_canvas,
            "kpis": self.kpi_canvas,
            "map": self.map_canvas,
        }
        return mapping.get(key)

    def _set_line_export_cache(self, key: str, x_values, series: dict[str, list | np.ndarray], x_label: str):
        cached_series = {}
        for name, y in series.items():
            cached_series[name] = [float(v) for v in y]
        self.export_cache[key] = {
            "type": "line",
            "x_label": x_label,
            "x_values": [float(v) for v in x_values],
            "series": cached_series,
        }

    def _set_map_export_cache(self, df):
        if df is None or df.empty:
            self.export_cache["map"] = {"type": "none"}
            return
        cols = [c for c in ["time_sec", "player_id", "player_name", "action_type", "action_family", "x", "y", "x_norm", "y_norm", "grid_x", "grid_y"] if c in df.columns]
        self.export_cache["map"] = {
            "type": "table",
            "dataframe": df[cols].copy(),
        }

    def export_current_plot_png(self):
        key = self._current_tab_key()
        if key is None:
            return
        canvas = self._canvas_for_key(key)
        if canvas is None:
            return
        default_name = f"{(self.replay_path.stem if self.replay_path else 'aoe2')}_{key}.png"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar gráfico", default_name, "PNG (*.png)")
        if not path:
            return
        try:
            canvas.figure.savefig(path, dpi=160, bbox_inches="tight")
            self.statusBar().showMessage(f"Gráfico exportado: {Path(path).name}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar el gráfico:\n{e}")

    def export_current_data_csv(self):
        key = self._current_tab_key()
        if key is None:
            return
        state = self.export_cache.get(key, {"type": "none"})
        if state.get("type") == "none":
            QMessageBox.information(self, "Sin datos", "No hay datos filtrados disponibles para exportar en esta pestaña.")
            return
        default_name = f"{(self.replay_path.stem if self.replay_path else 'aoe2')}_{key}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar datos", default_name, "CSV (*.csv)")
        if not path:
            return
        try:
            if state.get("type") == "line":
                x_label = str(state.get("x_label", "x"))
                x_values = list(state.get("x_values", []))
                series: dict[str, list[float]] = state.get("series", {})
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    headers = [x_label] + list(series.keys())
                    writer.writerow(headers)
                    for i, x in enumerate(x_values):
                        row = [x]
                        for label in series.keys():
                            values = series.get(label, [])
                            row.append(values[i] if i < len(values) else "")
                        writer.writerow(row)
            elif state.get("type") == "table":
                df = state.get("dataframe")
                if df is None or df.empty:
                    QMessageBox.information(self, "Sin datos", "No hay datos tabulares disponibles para exportar.")
                    return
                df.to_csv(path, index=False)
            else:
                QMessageBox.information(self, "Sin datos", "Formato de datos no exportable en esta pestaña.")
                return
            self.statusBar().showMessage(f"Datos exportados: {Path(path).name}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar el CSV:\n{e}")

    # ---- Update plots ----
    def update_apm(self):
        if not self.match:
            return
        w = int(self.apm_window.currentText())
        ts = apm_timeseries(self.match, window_sec=w)
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        self._set_line_export_cache("apm", ts.index/60, series, "time_min")
        colors = self._player_color_map()
        self.apm_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'APM', f'APM ventana {w}s', colors)
        self._overlay_important_events(self.apm_canvas)

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
        self._set_line_export_cache("units", ts.index/60, series, "time_min")
        colors = self._player_color_map()
        self.units_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', f'Unidades creadas ({unit_name})', f'{unit_name} — ventana {w}s', colors)
        self._overlay_important_events(self.units_canvas)

    def update_idle(self):
        if not self.match:
            return
        import re
        villager_re = re.compile(r'villager|aldean', re.IGNORECASE)
        w = int(self.idle_window.currentText())
        ts = tc_idle_cumulative_timeseries(self.match, villager_re, window_sec=w)
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        self._set_line_export_cache("idle", ts.index/60, series, "time_min")
        colors = self._player_color_map()
        self.idle_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'Idle TC acumulado (s)', f'Idle TC — ventana {w}s', colors)
        if self.idle_events.isChecked():
            ev = important_events(self.match)
            if not ev.empty:
                ev = ev[ev['kind'].isin(['tc','age'])]
                if not ev.empty:
                    xs = []
                    kinds = []
                    cols = []
                    texts = []
                    col_map = {p.number: colors.get(p.name, 'k') for p in self.match.players}
                    for _, row in ev.iterrows():
                        xs.append(float(row['time_sec'])/60.0)
                        kinds.append(row['kind'])
                        cols.append(col_map.get(int(row['player']), 'k'))
                        if row['kind'] == 'age':
                            ll = str(row['label']).lower()
                            texts.append('F' if 'feudal' in ll else ('C' if 'castle' in ll else ('I' if 'imperial' in ll else 'A')))
                        elif row['kind'] == 'tc':
                            texts.append('TC')
                        else:
                            texts.append('')
                    self.idle_canvas.add_event_markers(xs, kinds, colors=cols, texts=texts)

    def update_res(self):
        if not self.match or not self.replay_path:
            return
        res = self.res_combo.currentText()
        w = int(self.res_window.currentText())
        mode = self.res_mode.currentText()
        # default stock per resource for Balance mode if value is 0
        if mode == "Balance aprox." and self.res_stock.value() == 0:
            defaults = {"food": 200, "wood": 200, "gold": 100, "stone": 200}
            self.res_stock.setValue(defaults.get(res, 0))
        ts = None
        title = ""
        if mode == "Gasto":
            ts = resource_spend_timeseries(self.match, resource=res, window_sec=w)
            title = f"Gasto por ventana — {w}s"
        elif mode == "Balance aprox.":
            ts = resource_balance_timeseries(self.match, resource=res, window_sec=w, start_at=float(self.res_stock.value()))
            title = f"Saldo aprox. (spend + mercado) — ventana {w}s"
        else:
            per_player = resource_totals_postgame(self.replay_path)
            try:
                ts = resource_cumulative_timeseries(self.match, per_player, resource=res, window_sec=w)
            except Exception:
                ts = None
            title = f"{res.title()} acumulado (postgame) — ventana {w}s"
        # If no data or all zeros, show message
        if (ts is None) or ts.empty or ((ts.sum().sum() if not ts.empty else 0.0) == 0.0):
            msg = "Sin datos de recursos (usa 'Gasto' para estimación)" if mode != "Gasto" else "Sin datos suficientes para estimar gasto"
            self.export_cache["res"] = {"type": "none"}
            self.res_canvas.draw_message(msg)
            return
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        ylabel_map = {
            "Gasto": f"Gasto {res}",
            "Balance aprox.": f"Saldo {res}",
            "Postgame (si existe)": f"{res.title()} acumulado",
        }
        ylabel = ylabel_map.get(mode, f"{res}")
        self._set_line_export_cache("res", ts.index/60, series, "time_min")
        colors = self._player_color_map()
        self.res_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', ylabel, title, colors)
        # Add significant events on spend view
        if mode == "Gasto" and self.res_events.isChecked():
            ev = important_events(self.match)
            if not ev.empty:
                xs = []
                kinds = []
                cols = []
                texts = []
                col_map = {p.number: self._player_color_map().get(p.name, 'k') for p in self.match.players}
                for _, row in ev.iterrows():
                    k = row['kind']
                    if k in ('age', 'castle', 'elite', 'tech', 'tc'):
                        xs.append(float(row['time_sec'])/60.0)
                        kinds.append(k)
                        cols.append(col_map.get(int(row['player']), 'k'))
                        # Short text per event
                        lbl = str(row['label']).lower()
                        if k == 'age':
                            if 'feudal' in lbl:
                                texts.append('F')
                            elif 'castle' in lbl:
                                texts.append('C')
                            elif 'imperial' in lbl:
                                texts.append('I')
                            else:
                                texts.append('A')
                        elif k == 'castle':
                            texts.append('C')
                        elif k == 'elite':
                            texts.append('E')
                        elif k == 'tech':
                            texts.append('T')
                        elif k == 'tc':
                            texts.append('TC')
                if xs:
                    self.res_canvas.add_event_markers(xs, kinds, colors=cols, texts=texts)
                    # Add marker legend for clarity
                    try:
                        from matplotlib.lines import Line2D
                        from matplotlib.legend import Legend
                        handles = [
                            Line2D([0], [0], marker='*', color='none', label='Ages (F/C/I)', markerfacecolor='k', markersize=8, linestyle='None'),
                            Line2D([0], [0], marker='s', color='none', label='Castle', markerfacecolor='k', markersize=8, linestyle='None'),
                            Line2D([0], [0], marker='D', color='none', label='Elite', markerfacecolor='k', markersize=8, linestyle='None'),
                            Line2D([0], [0], marker='^', color='none', label='Tech', markerfacecolor='k', markersize=8, linestyle='None'),
                            Line2D([0], [0], marker='v', color='none', label='TC extra', markerfacecolor='k', markersize=8, linestyle='None'),
                        ]
                        leg2 = Legend(self.res_canvas.ax, handles=handles, labels=[h.get_label() for h in handles], loc='upper right', framealpha=0.2, fontsize=8)
                        if self.res_canvas.dark:
                            leg2.get_frame().set_facecolor('#0f1116')
                            leg2.get_frame().set_edgecolor('#5a6472')
                        self.res_canvas.ax.add_artist(leg2)
                    except Exception:
                        pass

    def _setup_score_tab(self):
        layout = QVBoxLayout(); self.tab_score.setLayout(layout)
        self.score_canvas = PlotCanvas(); layout.addWidget(self.score_canvas)

    def _setup_kpis_tab(self):
        layout = QVBoxLayout(); self.tab_kpis.setLayout(layout)
        controls = QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QLabel("Ventana KPI (s):"))
        self.kpi_window = QComboBox()
        self.kpi_window.addItems(["15", "30", "45", "60", "90", "120"])
        self.kpi_window.setCurrentText("60")
        self.kpi_window.currentTextChanged.connect(self.update_kpis)
        controls.addWidget(self.kpi_window)

        controls.addWidget(QLabel("Snapshot minuto:"))
        self.kpi_minute = QSpinBox()
        self.kpi_minute.setRange(1, 180)
        self.kpi_minute.setValue(20)
        self.kpi_minute.valueChanged.connect(self.update_kpis)
        controls.addWidget(self.kpi_minute)

        controls.addWidget(QLabel("Indice:"))
        self.kpi_metric = QComboBox()
        self.kpi_metric.addItems([
            "macro_index",
            "tempo_index",
            "eco_risk_index",
        ])
        self.kpi_metric.setCurrentText("macro_index")
        self.kpi_metric.currentTextChanged.connect(self.update_kpis)
        controls.addWidget(self.kpi_metric)
        controls.addStretch(1)

        self.kpi_canvas = PlotCanvas(); layout.addWidget(self.kpi_canvas, 2)
        self.kpi_table = QTableWidget()
        self.kpi_table.setColumnCount(6)
        self.kpi_table.setHorizontalHeaderLabels([
            "Jugador",
            "Tiempo (min)",
            "Macro Index",
            "Tempo Index",
            "Eco Risk",
            "Diagnostico",
        ])
        self.kpi_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.kpi_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.kpi_table.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.kpi_table, 1)

    def _player_color_map(self):
        if not self.match:
            return {}
        aoe_colors = {
            1: '#0000FF',  # Blue
            2: '#FF0000',  # Red
            3: '#00AA00',  # Green
            4: '#CCCC00',  # Yellow
            5: '#00FFFF',  # Cyan/Teal
            6: '#9400D3',  # Purple
            7: '#808080',  # Gray
            8: '#FF8C00',  # Orange
        }
        return {p.name: aoe_colors.get(getattr(p, 'color_id', 0), None) for p in self.match.players}

    def _toggle_theme(self, checked: bool):
        self._apply_theme_all()
        # redraw current tab
        self._on_tab_changed(self.tabs.currentIndex())

    def _apply_theme_all(self):
        dark = self.dark_action.isChecked()
        self._apply_qt_style(dark)
        for canvas in getattr(self, 'all_canvases', []):
            canvas.set_theme(dark)
            canvas.set_legend_outside(self.legend_out_action.isChecked())
        # lazily collect canvases
        self.all_canvases = [
            getattr(self, 'apm_canvas', None),
            getattr(self, 'units_canvas', None),
            getattr(self, 'idle_canvas', None),
            getattr(self, 'res_canvas', None),
            getattr(self, 'stock_canvas', None),
            getattr(self, 'score_canvas', None),
            getattr(self, 'kpi_canvas', None),
            getattr(self, 'map_canvas', None),
        ]
        self.all_canvases = [c for c in self.all_canvases if c is not None]

    def _toggle_legend_outside(self, checked: bool):
        # Apply to all canvases and redraw current
        for canvas in getattr(self, 'all_canvases', []):
            canvas.set_legend_outside(checked)
        self._on_tab_changed(self.tabs.currentIndex())

    def _toggle_event_overlay(self, checked: bool):
        self._on_tab_changed(self.tabs.currentIndex())

    def _show_glossary(self):
        text = (
            "Hitos y símbolos:\n\n"
            "* (F/C/I): Feudal/Castle/Imperial Age\n"
            "s (C): Castillo construido\n"
            "D (E): Mejora Elite\n"
            "^ (T): Tecnología clave (Wheelbarrow, Hand Cart, Bracer, Chemistry, Conscription, Ballistics, Siege Engineers, Architecture, Thumb Ring)\n"
            "v (TC): Town Center adicional"
        )
        QMessageBox.information(self, "Glosario de hitos", text)

    def _overlay_important_events(self, canvas: PlotCanvas):
        if not self.match:
            return
        if not self.overlay_events_action.isChecked():
            return
        ev = important_events(self.match)
        if ev.empty:
            return
        xs = []
        kinds = []
        cols = []
        texts = []
        colors = self._player_color_map()
        col_map = {p.number: colors.get(p.name, 'k') for p in self.match.players}
        for _, row in ev.iterrows():
            kind = str(row.get("kind", ""))
            if kind not in ("age", "castle", "elite", "tech", "tc"):
                continue
            xs.append(float(row["time_sec"]) / 60.0)
            kinds.append(kind)
            cols.append(col_map.get(int(row["player"]), 'k'))
            label = str(row.get("label", "")).lower()
            if kind == "age":
                if "feudal" in label:
                    texts.append("F")
                elif "castle" in label:
                    texts.append("C")
                elif "imperial" in label:
                    texts.append("I")
                else:
                    texts.append("A")
            elif kind == "castle":
                texts.append("C")
            elif kind == "elite":
                texts.append("E")
            elif kind == "tech":
                texts.append("T")
            elif kind == "tc":
                texts.append("TC")
        if xs:
            canvas.add_event_markers(xs, kinds, colors=cols, texts=texts)
            canvas.draw()

    def update_score(self):
        # Plot relative advantage to avoid duplicating raw stock/spend tabs.
        if not self.match:
            return
        from aoe2stat.metrics import sync_total_resources_timeseries, approximate_total_balance_timeseries
        ts = None
        if self.replay_path is not None:
            ts = sync_total_resources_timeseries(self.replay_path, window_sec=60)
        if ts is None or ts.empty:
            ts = approximate_total_balance_timeseries(self.match, window_sec=60)
        if ts is None or ts.empty:
            self.export_cache["score"] = {"type": "none"}
            self.score_canvas.draw_message("Sin datos suficientes para ventaja relativa")
            return

        # Advantage definition:
        #   own_stock - mean(stock_other_players) per window.
        series = {}
        for pid in ts.columns:
            own = ts[pid].astype(float)
            others = [c for c in ts.columns if c != pid]
            if others:
                others_mean = ts[others].astype(float).mean(axis=1)
            else:
                others_mean = 0.0
            adv = own - others_mean
            pname = next(p.name for p in self.match.players if p.number == pid)
            series[pname] = adv.values

        self._set_line_export_cache("score", ts.index/60, series, "time_min")
        colors = self._player_color_map()
        self.score_canvas.plot_lines(
            ts.index/60,
            series,
            'Tiempo (min)',
            'Ventaja de recursos vs rivales',
            'Ventaja relativa (stock sync / aproximado) — 60s',
            colors,
        )
        try:
            self.score_canvas.ax.axhline(0.0, color=('#dddddd' if not self.score_canvas.dark else '#667188'), linewidth=1.0, linestyle='--', alpha=0.8)
        except Exception:
            pass
        self._overlay_important_events(self.score_canvas)

    def update_stock(self):
        if not self.match or not self.replay_path:
            return
        from aoe2stat.metrics import sync_total_resources_timeseries, approximate_total_balance_timeseries
        ts = sync_total_resources_timeseries(self.replay_path, window_sec=60)
        if ts is None or ts.empty:
            # fallback to approximate total
            ts = approximate_total_balance_timeseries(self.match, window_sec=60)
            if ts is None or ts.empty:
                self.export_cache["stock"] = {"type": "none"}
                self.stock_canvas.draw_message("Sin datos de Stock para este replay")
                return
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        self._set_line_export_cache("stock", ts.index/60, series, "time_min")
        colors = self._player_color_map()
        self.stock_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'Total recursos', 'Stock total por jugador — 60s', colors)
        self._overlay_important_events(self.stock_canvas)

    def update_kpis(self):
        if not self.match:
            return
        metric = self.kpi_metric.currentText()
        window_sec = int(self.kpi_window.currentText())
        minute = int(self.kpi_minute.value())

        df = kpis_by_window(self.match, window_sec=window_sec)
        if df is None or df.empty:
            self.export_cache["kpis"] = {"type": "none"}
            self.kpi_canvas.draw_message("Sin datos KPI para este replay")
            self.kpi_table.setRowCount(0)
            return

        # Derived indices to avoid mirroring exact values from APM/Idle/Recursos tabs.
        df = df.copy()
        df["macro_index"] = df["villagers_created_cum"].astype(float) - (df["idle_tc_cum_sec"].astype(float) / 25.0)
        df["tempo_index"] = (df["apm"].astype(float) * 0.6) + (df["villagers_created_window"].astype(float) * 0.4)
        df["eco_risk_index"] = np.maximum(0.0, df["floating_total"].astype(float)) / 200.0

        if metric not in df.columns:
            self.export_cache["kpis"] = {"type": "none"}
            self.kpi_canvas.draw_message(f"KPI no disponible: {metric}")
            self.kpi_table.setRowCount(0)
            return

        pivot = df.pivot(index="time_sec", columns="player_id", values=metric).sort_index()
        series = {}
        for pid in pivot.columns:
            player_name = next((p.name for p in self.match.players if int(p.number) == int(pid)), f"P{int(pid)}")
            series[player_name] = pivot[pid].astype(float).to_numpy()

        ylabel_map = {
            "macro_index": "Macro Index",
            "tempo_index": "Tempo Index",
            "eco_risk_index": "Eco Risk Index",
        }
        title_map = {
            "macro_index": "Macro index (villagers - penalizacion idle)",
            "tempo_index": "Tempo index (APM + producción por ventana)",
            "eco_risk_index": "Eco risk index (floating positivo)",
        }
        self._set_line_export_cache("kpis", pivot.index/60.0, series, "time_min")
        colors = self._player_color_map()
        self.kpi_canvas.plot_lines(
            pivot.index/60.0,
            series,
            "Tiempo (min)",
            ylabel_map.get(metric, metric),
            f"{title_map.get(metric, metric)} — ventana {window_sec}s",
            colors,
        )
        self._overlay_important_events(self.kpi_canvas)

        # Snapshot table at minute N.
        target_sec = minute * 60
        table_rows = []
        for p in self.match.players:
            pid = int(p.number)
            g = df[(df["player_id"] == pid) & (df["time_sec"] <= target_sec)]
            if g.empty:
                table_rows.append((p.name, 0.0, 0.0, 0, 0.0, 0.0))
                continue
            last = g.iloc[-1]
            table_rows.append((
                p.name,
                float(last["time_sec"]) / 60.0,
                float(last["macro_index"]),
                float(last["tempo_index"]),
                float(last["eco_risk_index"]),
                (
                    "Riesgo eco alto"
                    if float(last["eco_risk_index"]) >= 5.0
                    else ("Macro solida" if float(last["macro_index"]) >= 40.0 else "Presion de ejecucion")
                ),
            ))

        self.kpi_table.setRowCount(len(table_rows))
        for row_idx, row in enumerate(table_rows):
            cells = [
                str(row[0]),
                f"{row[1]:.1f}",
                f"{row[2]:.1f}",
                f"{row[3]:.1f}",
                f"{row[4]:.1f}",
                str(row[5]),
            ]
            for col_idx, value in enumerate(cells):
                self.kpi_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _on_tab_changed(self, idx: int):
        w = self.tabs.widget(idx)
        if w is not self.tab_map and self.map_playback_is_running:
            self.map_playback_is_running = False
            self.map_play_btn.setText("Play")
            self.map_playback_timer.stop()
        if w is self.tab_apm:
            self.update_apm()
        elif w is self.tab_units:
            self.update_units()
        elif w is self.tab_idle:
            self.update_idle()
        elif w is self.tab_res:
            self.update_res()
        elif w is self.tab_stock:
            self.update_stock()
        elif w is self.tab_score:
            self.update_score()
        elif w is self.tab_kpis:
            self.update_kpis()
        elif w is self.tab_map:
            self.update_map()

    def update_map(self):
        if not self.match:
            return
        if not hasattr(self, 'map_slider'):
            return
        self.map_playback_pos = float(self.map_slider.value())
        if self.events_df is None or self.events_df.empty:
            self.export_cache["map"] = {"type": "none"}
            self.map_canvas.draw_message("Sin eventos con posicion para mostrar")
            return

        t = float(self.map_slider.value())
        lookback = int(self.map_window_combo.currentText())
        t0 = max(0.0, t - lookback)
        self.map_time_label.setText(f"{int(t//60)}:{int(t%60):02d}")
        is_cinematic = bool(self.map_cinematic_check.isChecked())
        selected_player = self.map_player_combo.currentText()
        selected_family = self.map_family_combo.currentText()
        layer = self.map_layer_combo.currentText()
        grid_size = int(self.map_fixed_grid_size)
        map_dim = float(getattr(self.match.map, "dimension", 120) or 120)
        map_dim = map_dim if map_dim > 0 else 120.0

        cine_sig = (layer, selected_player, selected_family, grid_size, lookback)
        jumped = self.map_last_time is not None and abs(t - float(self.map_last_time)) > (lookback * 2.0 + 2.0)
        if jumped or (self.map_cine_signature is not None and self.map_cine_signature != cine_sig):
            self.map_cine_heat = None
            self.map_cine_center = None
            self.map_cine_radius = None
        self.map_cine_signature = cine_sig

        df_window = self.events_df
        df_window = df_window[(df_window["time_sec"] >= t0) & (df_window["time_sec"] <= t)]
        df_window = df_window[df_window["x"].notna() & df_window["y"].notna()]
        if selected_family != "Todos":
            df_window = df_window[df_window["action_family"] == selected_family]
        if df_window.empty:
            self.export_cache["map"] = {"type": "none"}
            self.map_canvas.draw_message("Sin eventos espaciales en esta ventana")
            return

        gx_all = np.floor((df_window["x"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        gy_all = np.floor((df_window["y"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1).to_numpy()
        df_export = df_window.copy()
        df_export["x_norm"] = (df_export["x"].astype(float) / map_dim).clip(0.0, 1.0)
        df_export["y_norm"] = (df_export["y"].astype(float) / map_dim).clip(0.0, 1.0)
        df_export["grid_x"] = gx_all
        df_export["grid_y"] = gy_all
        self._set_map_export_cache(df_export)

        team_map = self._player_team_map()
        team_series = df_window["player_id"].astype(int).map(lambda pid: team_map.get(int(pid), int(pid))).to_numpy()
        movement_mask = df_window["action_family"].astype(str).isin(["movement", "military"]).to_numpy()
        pulse_heat = np.zeros((grid_size, grid_size), dtype=float)
        static_heat = np.zeros((grid_size, grid_size), dtype=float)
        layer_label = layer.lower()

        if layer == "Actividad":
            if selected_player != "Todos":
                p_mask = (df_window["player_name"].astype(str).to_numpy() == selected_player)
                pulse_heat = self._heat_from_cells(gx_all[p_mask & movement_mask], gy_all[p_mask & movement_mask], grid_size)
            else:
                pulse_heat = self._heat_from_cells(gx_all[movement_mask], gy_all[movement_mask], grid_size)
            static_heat = self._building_heat_persistent(t=t, grid_size=grid_size, map_dim=map_dim, selected_player=selected_player, layer="Actividad")
        elif layer in ("Propio", "Enemigo", "Presión"):
            sel_team = self._selected_player_team_id(selected_player)
            if sel_team is None:
                self.export_cache["map"] = {"type": "none"}
                self.map_canvas.draw_message("Para capa Propio/Enemigo/Presión, elegí un jugador (no 'Todos').")
                return
            own_mask = (team_series == int(sel_team)) & movement_mask
            enemy_mask = (team_series != int(sel_team)) & movement_mask
            own_pulse = self._heat_from_cells(gx_all[own_mask], gy_all[own_mask], grid_size)
            enemy_pulse = self._heat_from_cells(gx_all[enemy_mask], gy_all[enemy_mask], grid_size)
            own_static = self._building_heat_persistent(t=t, grid_size=grid_size, map_dim=map_dim, selected_player=selected_player, layer="Propio")
            enemy_static = self._building_heat_persistent(t=t, grid_size=grid_size, map_dim=map_dim, selected_player=selected_player, layer="Enemigo")
            if layer == "Propio":
                pulse_heat = own_pulse
                static_heat = own_static
            elif layer == "Enemigo":
                pulse_heat = enemy_pulse
                static_heat = enemy_static
            else:
                pulse_heat = enemy_pulse - own_pulse
                static_heat = enemy_static - own_static
        else:  # Edificios
            static_heat = self._building_heat_persistent(t=t, grid_size=grid_size, map_dim=map_dim, selected_player=selected_player, layer="Edificios")
            layer_label = "edificios"

        pulse_show = pulse_heat
        if is_cinematic:
            heat_decay, _, _ = self._map_cine_params()
            if self.map_cine_heat is None or self.map_cine_heat.shape != pulse_heat.shape:
                self.map_cine_heat = pulse_heat.copy()
            else:
                self.map_cine_heat = (self.map_cine_heat * heat_decay) + pulse_heat
            pulse_show = self.map_cine_heat

        show_pulses = bool(self.map_pulses_check.isChecked()) if hasattr(self, "map_pulses_check") else True
        show_buildings = bool(self.map_buildings_check.isChecked()) if hasattr(self, "map_buildings_check") else True
        pulse_term = pulse_show if show_pulses else np.zeros_like(pulse_show)
        static_term = static_heat if show_buildings else np.zeros_like(static_heat)
        if layer == "Presión":
            heat_show = (pulse_term * 1.0) + (static_term * 0.45)
        elif layer == "Edificios":
            heat_show = static_term
        else:
            heat_show = (pulse_term * 1.0) + (static_term * 0.7)

        self.map_canvas.ax.clear()
        self.map_canvas._apply_theme()
        cmap = "coolwarm" if layer == "Presión" else ("inferno" if self.map_canvas.dark else "YlOrRd")
        self.map_canvas.ax.imshow(heat_show, cmap=cmap, interpolation="nearest", aspect="equal")
        self.map_canvas.ax.set_xlabel("X cell")
        self.map_canvas.ax.set_ylabel("Y cell")
        self.map_canvas.ax.set_xticks(np.linspace(0, grid_size - 1, 5).astype(int))
        self.map_canvas.ax.set_yticks(np.linspace(0, grid_size - 1, 5).astype(int))

        if is_cinematic and len(gx_all) > 0:
            if layer == "Presión":
                focus_weights = np.abs(heat_show).ravel()
                xs, ys = np.meshgrid(np.arange(grid_size), np.arange(grid_size))
                x_cells = xs.ravel()
                y_cells = (grid_size - 1 - ys).ravel()
                if float(np.sum(focus_weights)) > 0:
                    cx_target = float(np.average(x_cells, weights=focus_weights))
                    cy_target = float(np.average(y_cells, weights=focus_weights))
                    spread = float(max(np.std(x_cells), np.std(y_cells), 1.8))
                else:
                    cx_target = float(np.mean(gx_all)); cy_target = float(np.mean(gy_all))
                    spread = float(max(np.std(gx_all), np.std(gy_all), 1.8))
            else:
                cx_target = float(np.mean(gx_all)); cy_target = float(np.mean(gy_all))
                spread = float(max(np.std(gx_all), np.std(gy_all), 1.8))
            _, camera_lerp, zoom_factor = self._map_cine_params()
            radius_target = float(np.clip((spread * 2.8) * zoom_factor, grid_size * 0.14, grid_size * 0.58))
            if self.map_cine_center is None:
                cx, cy = cx_target, cy_target
            else:
                cx_prev, cy_prev = self.map_cine_center
                cx = (cx_prev * (1.0 - camera_lerp)) + (cx_target * camera_lerp)
                cy = (cy_prev * (1.0 - camera_lerp)) + (cy_target * camera_lerp)
            radius = radius_target if self.map_cine_radius is None else ((self.map_cine_radius * (1.0 - camera_lerp)) + (radius_target * camera_lerp))
            self.map_cine_center = (cx, cy)
            self.map_cine_radius = radius
            cx = float(np.clip(cx, 0.0, grid_size - 1.0)); cy = float(np.clip(cy, 0.0, grid_size - 1.0))
            row_center = (grid_size - 1.0) - cy
            self.map_canvas.ax.set_xlim(max(-0.5, cx - radius), min(grid_size - 0.5, cx + radius))
            self.map_canvas.ax.set_ylim(min(grid_size - 0.5, row_center + radius), max(-0.5, row_center - radius))

        hover_items: list[dict[str, float | str]] = []
        if self.map_resources_check.isChecked() and self.map_resource_df is not None and not self.map_resource_df.empty:
            rdf = self.map_resource_df.copy()
            rgx = np.floor((rdf["x"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1)
            rgy = np.floor((rdf["y"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1)
            rdf["gx"] = rgx.to_numpy()
            rdf["row"] = (grid_size - 1 - rgy).to_numpy()
            palette = {"wood": "#2fa54a", "gold": "#ffd34d", "stone": "#9ea7b3", "food": "#c8672a"}
            marker_map = {"wood": ".", "gold": "o", "stone": "s", "food": "^"}
            size_map = {"wood": 8, "gold": 18, "stone": 18, "food": 16}
            for rtype in ["wood", "gold", "stone", "food"]:
                part = rdf[rdf["resource_type"] == rtype]
                if part.empty:
                    continue
                self.map_canvas.ax.scatter(
                    part["gx"], part["row"],
                    s=size_map.get(rtype, 10),
                    marker=marker_map.get(rtype, "o"),
                    c=palette.get(rtype, "#ffffff"),
                    alpha=0.45 if rtype == "wood" else 0.65,
                    linewidths=0.0 if rtype == "wood" else 0.2,
                    edgecolors="none" if rtype == "wood" else "#111111",
                    label=f"Recurso: {rtype}",
                    zorder=3,
                )
                sample = part if len(part) <= 300 else part.sample(300, random_state=42)
                for _, rr in sample.iterrows():
                    hover_items.append({"x": float(rr["gx"]), "y": float(rr["row"]), "text": f"Recurso: {rtype}"})

        markers_drawn = 0
        if self.map_key_objects_check.isChecked() and self.map_key_objects_df is not None and not self.map_key_objects_df.empty:
            key_df = self.map_key_objects_df[self.map_key_objects_df["time_sec"] <= t].copy()
            if selected_player != "Todos":
                key_df = key_df[key_df["player_name"] == selected_player]
            if not key_df.empty:
                key_gx = np.floor((key_df["x"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1)
                key_gy = np.floor((key_df["y"].astype(float) / map_dim) * grid_size).astype(int).clip(0, grid_size - 1)
                key_rows = (grid_size - 1 - key_gy).to_numpy()
                key_cols = key_gx.to_numpy()
                player_colors = self._player_color_map()
                color_by_pid = {int(p.number): player_colors.get(p.name, "#ffffff" if self.map_canvas.dark else "#111111") for p in self.match.players}
                key_df["gx"] = key_cols
                key_df["row"] = key_rows
                key_df["px_color"] = key_df["player_id"].map(lambda pid: color_by_pid.get(int(pid), "#ffffff"))
                key_df = key_df.sort_values("time_sec").drop_duplicates(subset=["player_id", "object_kind", "gx", "row"], keep="last")
                tc_df = key_df[key_df["object_kind"] == "tc"]
                tc0_df = key_df[key_df["object_kind"] == "tc_initial"]
                castle_df = key_df[key_df["object_kind"] == "castle"]
                if not tc_df.empty:
                    self.map_canvas.ax.scatter(tc_df["gx"], tc_df["row"], s=70, marker="^", facecolors=tc_df["px_color"], edgecolors="#000000", linewidths=0.8, alpha=0.95, label="TC")
                if not tc0_df.empty:
                    self.map_canvas.ax.scatter(tc0_df["gx"], tc0_df["row"], s=85, marker="P", facecolors=tc0_df["px_color"], edgecolors="#000000", linewidths=0.8, alpha=0.98, label="TC inicial")
                if not castle_df.empty:
                    self.map_canvas.ax.scatter(castle_df["gx"], castle_df["row"], s=90, marker="s", facecolors=castle_df["px_color"], edgecolors="#000000", linewidths=0.8, alpha=0.95, label="Castillo")
                markers_drawn = int(len(key_df))
                for _, rr in key_df.iterrows():
                    kind = str(rr["object_kind"])
                    kind_lbl = "TC inicial" if kind == "tc_initial" else ("TC" if kind == "tc" else "Castillo")
                    hover_items.append(
                        {
                            "x": float(rr["gx"]),
                            "y": float(rr["row"]),
                            "text": f"{kind_lbl} | {rr['player_name']} | equipo {int(rr['team_id'])} | t={self._fmt_time(float(rr['time_sec']))}",
                        }
                    )

        self.map_canvas.ax.set_title(
            f"Mapa NxN ({grid_size}x{grid_size}) | capa {layer_label} | {selected_player} | {selected_family} | ventana {lookback}s | "
            f"eventos {len(df_window)} | {'cinemático' if is_cinematic else 'estático'} | marcadores {markers_drawn}"
        )
        handles, labels = self.map_canvas.ax.get_legend_handles_labels()
        if handles and labels:
            seen = set()
            h2 = []
            l2 = []
            for h, l in zip(handles, labels):
                if l in seen:
                    continue
                seen.add(l); h2.append(h); l2.append(l)
            self.map_canvas.ax.legend(h2, l2, loc="upper right", framealpha=0.4, fontsize=8)
        self._set_map_hover_items(hover_items)
        if hasattr(self, "map_event_log_list"):
            self.map_event_log_list.clear()
            if self.map_event_log_df is not None and not self.map_event_log_df.empty:
                log_mode = self.map_log_window_combo.currentText() if hasattr(self, "map_log_window_combo") else "120s"
                if log_mode == "Todo":
                    log_df = self.map_event_log_df[self.map_event_log_df["time_sec"] <= t]
                else:
                    try:
                        window_sec = int(str(log_mode).replace("s", ""))
                    except Exception:
                        window_sec = 120
                    log_df = self.map_event_log_df[
                        (self.map_event_log_df["time_sec"] <= t) & (self.map_event_log_df["time_sec"] >= max(0.0, t - float(window_sec)))
                    ]
                max_rows = 250
                if len(log_df) > max_rows:
                    log_df = log_df.iloc[-max_rows:]
                for txt in log_df["text"].tolist():
                    self.map_event_log_list.addItem(str(txt))
                self.map_event_log_list.scrollToBottom()
        self.map_last_time = t
        self.map_canvas.draw()
