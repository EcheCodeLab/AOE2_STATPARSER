from __future__ import annotations

import traceback
from pathlib import Path

try:
    from PySide6 import QtWidgets
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QFileDialog, QMessageBox, QTabWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QCheckBox
    )
    from PySide6.QtGui import QAction
except Exception:  # pragma: no cover
    from PyQt5 import QtWidgets  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QMainWindow, QWidget, QFileDialog, QMessageBox, QTabWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QCheckBox, QAction
    )

import os
# Ensure Matplotlib uses QtAgg with the chosen Qt binding
os.environ.setdefault("QT_API", os.environ.get("QT_API", "pyside6"))
os.environ.setdefault("MPLBACKEND", "QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from aoe2stat.core import load_match
from aoe2stat.metrics import (
    apm_timeseries, unit_created_timeseries, tc_idle_cumulative_timeseries,
    resource_totals_postgame, resource_cumulative_timeseries,
    resource_spend_timeseries, resource_balance_timeseries, important_events,
)
from aoe2stat.patterns import base_unit_patterns, augment_unit_patterns


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
        self.tab_stock = QWidget(); self.tabs.addTab(self.tab_stock, "Stock Total")
        self.tab_score = QWidget(); self.tabs.addTab(self.tab_score, "Score")

        self._setup_menu()
        self._setup_apm_tab()
        self._setup_units_tab()
        self._setup_idle_tab()
        self._setup_res_tab()
        self._setup_stock_tab()
        self._setup_score_tab()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # initialize theme/legend on canvases
        self._apply_theme_all()

    # ---- UI Setup ----
    def _setup_menu(self):
        open_action = QAction("Abrir replay", self)
        open_action.triggered.connect(self.open_replay)
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Archivo")
        file_menu.addAction(open_action)
        view_menu = menubar.addMenu("Ver")
        self.dark_action = QAction("Tema oscuro", self, checkable=True)
        self.dark_action.setChecked(True)
        self.dark_action.toggled.connect(self._toggle_theme)
        view_menu.addAction(self.dark_action)
        self.legend_out_action = QAction("Leyenda fuera", self, checkable=True)
        self.legend_out_action.setChecked(True)
        self.legend_out_action.toggled.connect(self._toggle_legend_outside)
        view_menu.addAction(self.legend_out_action)
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
        self.idle_events = QCheckBox("Eventos"); self.idle_events.setChecked(True)
        self.idle_events.stateChanged.connect(self.update_idle)
        controls.addWidget(self.idle_events)
        self.idle_canvas = PlotCanvas(); layout.addWidget(self.idle_canvas)

    def _setup_res_tab(self):
        layout = QVBoxLayout(); self.tab_res.setLayout(layout)
        controls = QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QLabel("Recurso:"))
        self.res_combo = QComboBox(); self.res_combo.addItems(["food","wood","gold","stone"]) ; self.res_combo.currentTextChanged.connect(self.update_res)
        controls.addWidget(self.res_combo)
        controls.addWidget(QLabel("Modo:"))
        self.res_mode = QComboBox(); self.res_mode.addItems(["Gasto", "Balance aprox.", "Stock (sync)", "Postgame (si existe)"]) ; self.res_mode.setCurrentText("Gasto")
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
        self.res_canvas = PlotCanvas(); layout.addWidget(self.res_canvas)

    def _setup_stock_tab(self):
        layout = QVBoxLayout(); self.tab_stock.setLayout(layout)
        self.stock_canvas = PlotCanvas(); layout.addWidget(self.stock_canvas)

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
            self._apply_theme_all()
            self.update_apm(); self.update_units(); self.update_idle(); self.update_res(); self.update_stock(); self.update_score()
        except Exception as e:  # pragma: no cover
            QMessageBox.critical(self, "Error", f"No se pudo abrir el replay:\n{e}\n\n{traceback.format_exc()}")

    # ---- Update plots ----
    def update_apm(self):
        if not self.match:
            return
        w = int(self.apm_window.currentText())
        ts = apm_timeseries(self.match, window_sec=w)
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        colors = self._player_color_map()
        self.apm_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'APM', f'APM ventana {w}s', colors)

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
        colors = self._player_color_map()
        self.units_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', f'Unidades creadas ({unit_name})', f'{unit_name} — ventana {w}s', colors)

    def update_idle(self):
        if not self.match:
            return
        import re
        villager_re = re.compile(r'villager|aldean', re.IGNORECASE)
        w = int(self.idle_window.currentText())
        ts = tc_idle_cumulative_timeseries(self.match, villager_re, window_sec=w)
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
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
        elif mode == "Stock (sync)":
            from aoe2stat.metrics import sync_total_resources_timeseries
            ts = sync_total_resources_timeseries(self.replay_path, window_sec=w)
            title = f"Total recursos (sync, stock) — ventana {w}s"
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
            self.res_canvas.draw_message(msg)
            return
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        ylabel_map = {
            "Gasto": f"Gasto {res}",
            "Balance aprox.": f"Saldo {res}",
            "Stock (sync)": "Total recursos (sync)",
            "Postgame (si existe)": f"{res.title()} acumulado",
        }
        ylabel = ylabel_map.get(mode, f"{res}")
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
        ]
        self.all_canvases = [c for c in self.all_canvases if c is not None]

    def _toggle_legend_outside(self, checked: bool):
        # Apply to all canvases and redraw current
        for canvas in getattr(self, 'all_canvases', []):
            canvas.set_legend_outside(checked)
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

    def update_score(self):
        # Plot score proxy distinto de stock: gasto total acumulado
        if not self.match:
            return
        from aoe2stat.metrics import total_spend_timeseries
        ts = total_spend_timeseries(self.match, window_sec=60, cumulative=True)
        if ts is None or ts.empty:
            self.score_canvas.draw_message("Sin datos suficientes para score proxy")
            return
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        colors = self._player_color_map()
        self.score_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'Gasto total acumulado', 'Score (proxy por gasto total) — 60s', colors)

    def update_stock(self):
        if not self.match or not self.replay_path:
            return
        from aoe2stat.metrics import sync_total_resources_timeseries, approximate_total_balance_timeseries
        ts = sync_total_resources_timeseries(self.replay_path, window_sec=60)
        if ts is None or ts.empty:
            # fallback to approximate total
            ts = approximate_total_balance_timeseries(self.match, window_sec=60)
            if ts is None or ts.empty:
                self.stock_canvas.draw_message("Sin datos de Stock para este replay")
                return
        series = {next(p.name for p in self.match.players if p.number == pid): ts[pid].values for pid in ts.columns}
        colors = self._player_color_map()
        self.stock_canvas.plot_lines(ts.index/60, series, 'Tiempo (min)', 'Total recursos', 'Stock total por jugador — 60s', colors)

    def _on_tab_changed(self, idx: int):
        w = self.tabs.widget(idx)
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
