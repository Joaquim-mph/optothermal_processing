"""
History Browser Page.

Displays chip experiment history in a filterable QTableWidget.
Matches the TUI history browser's column layout, formatting, and stats.
Self-contained with a chip selector combo box.

Includes a live pyqtgraph plot panel for interactive experiment exploration.
"""

from __future__ import annotations
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QFrame, QSplitter, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

import pyqtgraph as pg

if TYPE_CHECKING:
    from src.gui.app import MainWindow

from src.gui.theme import COLORS

# Fixed columns matching the TUI history browser (same order)
TABLE_COLUMNS = ["Light", "Seq", "Date", "Time", "Proc", "VG", "LED V", "\u03bb (nm)", "VDS (V)"]

# Procedure → (x_column, y_column, x_label, y_label)
PROC_AXES = {
    "It":  ("t (s)", "I (A)", "Time (s)", "Current (A)"),
    "IVg": ("Vg (V)", "I (A)", "Gate Voltage (V)", "Current (A)"),
    "VVg": ("Vg (V)", "VDS (V)", "Gate Voltage (V)", "Drain-Source Voltage (V)"),
    "Vt":  ("t (s)", "VDS (V)", "Time (s)", "Drain-Source Voltage (V)"),
    "IV":  ("Vsd (V)", "I (A)", "Source-Drain Voltage (V)", "Current (A)"),
    "LaserCalibration": ("VL (V)", "Power (W)", "Laser Voltage (V)", "Power (W)"),
}

# Tokyo Night plot line color cycle
PLOT_COLORS = [
    "#7aa2f7",  # blue
    "#9ece6a",  # green
    "#bb9af7",  # magenta
    "#7dcfff",  # cyan
    "#ff9e64",  # orange
    "#e0af68",  # yellow
    "#f7768e",  # red
]

# Max cached dataframes
_CACHE_MAX = 20


class _LRUCache(OrderedDict):
    """Simple LRU cache based on OrderedDict."""

    def __init__(self, maxsize: int = _CACHE_MAX):
        super().__init__()
        self._maxsize = maxsize

    def get_or_load(self, key: str, loader):
        if key in self:
            self.move_to_end(key)
            return self[key]
        value = loader()
        self[key] = value
        if len(self) > self._maxsize:
            self.popitem(last=False)
        return value


class HistoryBrowserPage(QWidget):
    """Chip history browser matching the TUI's column layout and formatting."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._history_df: pl.DataFrame | None = None
        self._filtered_df: pl.DataFrame | None = None
        self._has_light: bool = False
        self._data_cache = _LRUCache(_CACHE_MAX)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        # ── Title row ──
        title = QLabel("Chip Experiment Timeline")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # ── Stats line (matches TUI: "Alisson67 | Total: 90 | IVg: 39  It: 51") ──
        self._stats_header = QLabel("")
        self._stats_header.setObjectName("info-label")
        self._stats_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._stats_header)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Filter bar ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)

        filter_row.addWidget(QLabel("Chip:"))
        self._chip_combo = QComboBox()
        self._chip_combo.setMinimumWidth(200)
        self._chip_combo.currentIndexChanged.connect(self._on_chip_changed)
        filter_row.addWidget(self._chip_combo)

        filter_row.addSpacing(16)

        filter_row.addWidget(QLabel("Procedure:"))
        self._proc_combo = QComboBox()
        self._proc_combo.addItem("All")
        self._proc_combo.setMinimumWidth(100)
        self._proc_combo.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(self._proc_combo)

        filter_row.addSpacing(16)

        # Light filter buttons (matching TUI's All / Light / Dark buttons)
        filter_row.addWidget(QLabel("Light:"))
        self._light_all_btn = QPushButton("All")
        self._light_light_btn = QPushButton("Light")
        self._light_dark_btn = QPushButton("Dark")

        for btn in (self._light_all_btn, self._light_light_btn, self._light_dark_btn):
            btn.setCheckable(True)
            btn.setFixedWidth(70)
            filter_row.addWidget(btn)

        self._light_all_btn.setChecked(True)
        self._light_all_btn.clicked.connect(lambda: self._set_light_filter("all"))
        self._light_light_btn.clicked.connect(lambda: self._set_light_filter("light"))
        self._light_dark_btn.clicked.connect(lambda: self._set_light_filter("dark"))
        self._light_filter = "all"

        filter_row.addStretch()

        # Plot panel toggle
        self._plot_toggle_btn = QPushButton("Show Plot")
        self._plot_toggle_btn.setCheckable(True)
        self._plot_toggle_btn.setChecked(False)
        self._plot_toggle_btn.setFixedWidth(90)
        self._plot_toggle_btn.clicked.connect(self._toggle_plot_panel)
        filter_row.addWidget(self._plot_toggle_btn)

        layout.addLayout(filter_row)

        # ── Splitter: table on left, plot on right ──
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Table ──
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setColumnCount(len(TABLE_COLUMNS))
        self._table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self._table.horizontalHeader().setStretchLastSection(True)
        # Fixed column widths matching TUI proportions
        widths = [50, 50, 90, 70, 50, 120, 60, 60, 60]
        for i, w in enumerate(widths):
            self._table.setColumnWidth(i, w)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._splitter.addWidget(self._table)

        # ── Plot panel (toolbar + PlotWidget) ──
        self._plot_container = QWidget()
        plot_container = self._plot_container
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(4)

        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self._clear_plot)
        toolbar.addWidget(clear_btn)

        self._conductance_cb = QCheckBox("Conductance (G=I/V)")
        self._conductance_cb.setVisible(False)
        self._conductance_cb.toggled.connect(self._on_transform_toggled)
        toolbar.addWidget(self._conductance_cb)

        self._resistance_cb = QCheckBox("Resistance (R=V/I)")
        self._resistance_cb.setVisible(False)
        self._resistance_cb.toggled.connect(self._on_transform_toggled)
        toolbar.addWidget(self._resistance_cb)

        self._plot_info = QLabel("")
        self._plot_info.setObjectName("info-label")
        toolbar.addStretch()
        toolbar.addWidget(self._plot_info)

        plot_layout.addLayout(toolbar)

        # pyqtgraph PlotWidget
        pg.setConfigOptions(antialias=True)
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground(COLORS["bg"])
        self._plot_widget.showGrid(x=False, y=False)

        # Style axes to match Tokyo Night
        for axis_name in ("bottom", "left"):
            axis = self._plot_widget.getAxis(axis_name)
            axis.setPen(pg.mkPen(COLORS["fg"], width=1))
            axis.setTextPen(pg.mkPen(COLORS["fg"]))

        # Add legend
        self._legend = self._plot_widget.addLegend(
            offset=(10, 10),
            labelTextColor=COLORS["fg"],
        )

        plot_layout.addWidget(self._plot_widget, stretch=1)
        self._splitter.addWidget(plot_container)

        # Default split: 50% table, 50% plot
        self._splitter.setSizes([500, 500])

        # Start with plot hidden
        self._plot_container.setVisible(False)

        layout.addWidget(self._splitter, stretch=1)

        # ── Status bar (matches TUI: "Showing 51 of 90 experiments — Filters: proc=It") ──
        self._status_bar = QLabel("")
        self._status_bar.setObjectName("page-subtitle")
        self._status_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_bar.setStyleSheet(
            f"background-color: #1f2335; padding: 6px; border-top: 1px solid #3b4261;"
        )
        layout.addWidget(self._status_bar)

        # ── Navigation ──
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        nav_row.addWidget(home_btn)
        layout.addLayout(nav_row)

    # ── Lifecycle ──

    def on_enter(self, **kwargs) -> None:
        self._populate_chip_combo()

    # ── Chip selector ──

    def _populate_chip_combo(self) -> None:
        self._chip_combo.blockSignals(True)
        self._chip_combo.clear()

        try:
            from src.tui.utils import discover_chips
            chips = discover_chips(
                self._window.session.history_dir,
                self._window.session.chip_group,
            )
        except Exception:
            chips = []

        if not chips:
            self._chip_combo.addItem("No chips found")
            self._chip_combo.blockSignals(False)
            self._stats_header.setText("No chip data available — run 'biotite full-pipeline' first")
            self._table.setRowCount(0)
            return

        for chip in chips:
            display = f"{chip.chip_group}{chip.chip_number} ({chip.total_experiments} experiments)"
            self._chip_combo.addItem(display, chip.chip_number)

        # Pre-select chip from session
        session_chip = self._window.session.chip_number
        if session_chip is not None:
            for i in range(self._chip_combo.count()):
                if self._chip_combo.itemData(i) == session_chip:
                    self._chip_combo.setCurrentIndex(i)
                    break

        self._chip_combo.blockSignals(False)
        self._on_chip_changed()

    def _on_chip_changed(self) -> None:
        chip_number = self._chip_combo.currentData()
        if chip_number is None:
            self._history_df = None
            self._table.setRowCount(0)
            self._stats_header.setText("")
            self._status_bar.setText("")
            self._clear_plot()
            return
        self._load_history(chip_number)

    # ── Data loading ──

    def _load_history(self, chip_number: int) -> None:
        session = self._window.session
        chip_name = f"{session.chip_group}{chip_number}"
        history_file = session.history_dir / f"{chip_name}_history.parquet"

        if not history_file.exists():
            self._stats_header.setText(f"History file not found for {chip_name}")
            self._history_df = None
            self._table.setRowCount(0)
            self._status_bar.setText("")
            return

        try:
            self._history_df = pl.read_parquet(history_file)
        except Exception as e:
            self._stats_header.setText(f"Load error: {e}")
            self._history_df = None
            return

        self._has_light = "has_light" in self._history_df.columns

        # Update stats header (matching TUI: "Alisson67 | Total: 90 | IVg: 39  It: 51")
        self._update_stats_header(chip_name)

        # Populate procedure filter
        self._proc_combo.blockSignals(True)
        self._proc_combo.clear()
        self._proc_combo.addItem("All")
        if "proc" in self._history_df.columns:
            procs = sorted(self._history_df["proc"].unique().to_list())
            self._proc_combo.addItems(procs)
        self._proc_combo.blockSignals(False)

        # Enable/disable light filter buttons
        for btn in (self._light_all_btn, self._light_light_btn, self._light_dark_btn):
            btn.setEnabled(self._has_light)

        self._light_filter = "all"
        self._highlight_light_filter()

        # Clear plot and cache on chip change
        self._data_cache = _LRUCache(_CACHE_MAX)
        self._clear_plot()

        self._apply_filters()

    def _update_stats_header(self, chip_name: str) -> None:
        """Build TUI-style stats: 'Alisson67 | Total: 90 | IVg: 39  It: 51'."""
        if self._history_df is None:
            return

        total = self._history_df.height
        proc_counts = (
            self._history_df.group_by("proc")
            .agg(pl.len().alias("count"))
            .sort("count", descending=True)
        )

        proc_parts = []
        for row in proc_counts.iter_rows(named=True):
            proc_parts.append(f"{row['proc']}: {row['count']}")

        self._stats_header.setText(
            f"{chip_name}  |  Total: {total}  |  " + "  ".join(proc_parts)
        )

    # ── Light filter ──

    def _set_light_filter(self, value: str) -> None:
        self._light_filter = value
        self._highlight_light_filter()
        self._apply_filters()

    def _highlight_light_filter(self) -> None:
        self._light_all_btn.setChecked(self._light_filter == "all")
        self._light_light_btn.setChecked(self._light_filter == "light")
        self._light_dark_btn.setChecked(self._light_filter == "dark")

    # ── Filtering ──

    def _apply_filters(self) -> None:
        if self._history_df is None:
            return

        df = self._history_df
        applied: list[str] = []

        # Procedure filter
        proc = self._proc_combo.currentText()
        if proc and proc != "All" and "proc" in df.columns:
            df = df.filter(pl.col("proc") == proc)
            applied.append(f"proc={proc}")

        # Light filter
        if self._has_light and self._light_filter != "all":
            if self._light_filter == "light":
                df = df.filter(pl.col("has_light") == True)
                applied.append("light=on")
            elif self._light_filter == "dark":
                df = df.filter(pl.col("has_light") == False)
                applied.append("light=off")

        self._filtered_df = df

        # Update status bar (matching TUI style)
        total = self._history_df.height
        filtered = df.height
        if applied:
            filter_text = ", ".join(applied)
            self._status_bar.setText(
                f"Showing {filtered} of {total} experiments \u2014 Filters: {filter_text}"
            )
        else:
            self._status_bar.setText(f"Showing all {total} experiments")

        self._populate_table(df)

        # Clear plot on filter change (selected rows no longer match)
        self._clear_plot()

    # ── Table population (matching TUI formatting exactly) ──

    def _populate_table(self, df: pl.DataFrame) -> None:
        self._table.setRowCount(0)  # clear
        self._table.setRowCount(df.height)

        for row_idx, row in enumerate(df.iter_rows(named=True)):
            # Light column returns (text, color); others return plain str
            light_text, light_color = self._fmt_light(row)
            values = [
                light_text,
                str(row.get("seq", "")),
                str(row.get("date", "")),
                str(row.get("time_hms", "")),
                str(row.get("proc", "")),
                self._fmt_vg(row),
                self._fmt_led(row),
                self._fmt_wavelength(row),
                self._fmt_vds(row),
            ]

            for col_idx, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

                # Center-align Light column + apply color
                if col_idx == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if light_color is not None:
                        item.setForeground(light_color)
                # Right-align numeric columns (Seq, LED V, λ, VDS)
                elif col_idx in (1, 6, 7, 8):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )

                self._table.setItem(row_idx, col_idx, item)

        # Resize columns to fit content, but keep stretch on last
        header = self._table.horizontalHeader()
        for col_idx in range(len(TABLE_COLUMNS) - 1):
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(TABLE_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)

    # ── Live plot ──

    def _on_selection_changed(self) -> None:
        """Handle table row selection changes — plot selected experiments."""
        if self._filtered_df is None or not self._plot_container.isVisible():
            return

        selected_rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        if not selected_rows:
            self._plot_widget.clear()
            self._legend.clear()
            self._plot_info.setText("")
            return

        self._plot_selected(selected_rows)

    def _resolve_parquet_path(self, row: dict) -> Path | None:
        """Resolve the parquet file path for a history row."""
        # Try parquet_path column first
        ppath = row.get("parquet_path")
        if ppath is not None:
            p = Path(str(ppath))
            if p.exists():
                return p

        # Build path from components
        session = self._window.session
        stage_dir = Path(session.config.get("stage_dir", "data/02_stage/raw_measurements"))
        proc = row.get("proc", "")
        date = row.get("date", "")
        run_id = row.get("run_id", "")
        if proc and date and run_id:
            p = stage_dir / f"proc={proc}" / f"date={date}" / f"run_id={run_id}" / "part-000.parquet"
            if p.exists():
                return p

        return None

    def _load_experiment_data(self, row: dict) -> pl.DataFrame | None:
        """Load measurement data for an experiment row, with LRU caching."""
        run_id = row.get("run_id", "")
        if not run_id:
            return None

        def loader():
            path = self._resolve_parquet_path(row)
            if path is None:
                return None
            try:
                return pl.read_parquet(path)
            except Exception:
                return None

        return self._data_cache.get_or_load(run_id, loader)

    def _plot_selected(self, selected_rows: list[int]) -> None:
        """Plot data for all selected table rows."""
        self._plot_widget.clear()
        self._legend.clear()

        df = self._filtered_df
        if df is None:
            return

        # Determine procedure type for axis labels and transforms
        procs_in_selection = set()
        items_to_plot: list[tuple[dict, pl.DataFrame]] = []

        for row_idx in selected_rows:
            if row_idx >= df.height:
                continue
            row = df.row(row_idx, named=True)
            data = self._load_experiment_data(row)
            if data is not None:
                items_to_plot.append((row, data))
                procs_in_selection.add(row.get("proc", ""))

        if not items_to_plot:
            self._plot_info.setText("No data available for selected experiments")
            return

        # Use the first procedure for axis config (all same proc if filtered)
        proc = next(iter(procs_in_selection))
        axes_cfg = PROC_AXES.get(proc)

        # Update transform checkboxes visibility
        self._update_transform_controls(proc)

        # Determine if transform is active
        use_conductance = self._conductance_cb.isVisible() and self._conductance_cb.isChecked()
        use_resistance = self._resistance_cb.isVisible() and self._resistance_cb.isChecked()

        if axes_cfg is None:
            self._plot_info.setText(f"Unknown procedure: {proc}")
            return

        x_col, y_col, x_label, y_label = axes_cfg

        # Apply transform labels
        if use_conductance:
            y_label = "Conductance (S)"
        elif use_resistance:
            y_label = "Resistance (\u03a9)"

        self._plot_widget.setLabel("bottom", x_label)
        self._plot_widget.setLabel("left", y_label)

        for i, (row, data) in enumerate(items_to_plot):
            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            if x_col not in data.columns or y_col not in data.columns:
                continue

            x = data[x_col].to_numpy()
            y = data[y_col].to_numpy()

            # Apply transforms
            if use_conductance:
                vds = row.get("vds_v")
                if vds is not None and float(vds) != 0:
                    y = y / float(vds)
            elif use_resistance:
                ids = data[y_col].to_numpy()
                # R = V/I — need VDS from data or metadata
                vds = row.get("vds_v")
                if vds is not None:
                    import numpy as np
                    with np.errstate(divide="ignore", invalid="ignore"):
                        y = float(vds) / ids
                        y = np.where(np.isfinite(y), y, 0.0)

            # Build legend label
            seq = row.get("seq", "?")
            wl = row.get("wavelength_nm")
            label = f"Seq {seq}"
            if wl is not None:
                try:
                    label += f" - {float(wl):.0f}nm"
                except (TypeError, ValueError):
                    pass

            pen = pg.mkPen(color=color, width=2)
            self._plot_widget.plot(x, y, pen=pen, name=label)

        n = len(items_to_plot)
        proc_text = proc if len(procs_in_selection) == 1 else "mixed"
        self._plot_info.setText(f"{n} experiment{'s' if n != 1 else ''} ({proc_text})")

    def _update_transform_controls(self, proc: str) -> None:
        """Show/hide conductance or resistance checkbox based on procedure."""
        # Conductance: applicable to It, IVg (current-based)
        # Resistance: applicable to VVg, Vt (voltage-based)
        show_conductance = proc in ("It", "IVg")
        show_resistance = proc in ("VVg", "Vt")
        self._conductance_cb.setVisible(show_conductance)
        self._resistance_cb.setVisible(show_resistance)

    def _on_transform_toggled(self) -> None:
        """Re-plot when conductance/resistance checkbox is toggled."""
        selected_rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        if selected_rows:
            self._plot_selected(selected_rows)

    def _toggle_plot_panel(self) -> None:
        """Show or hide the plot panel."""
        visible = self._plot_toggle_btn.isChecked()
        self._plot_container.setVisible(visible)
        self._plot_toggle_btn.setText("Hide Plot" if visible else "Show Plot")
        if not visible:
            self._plot_widget.clear()
            self._legend.clear()
            self._plot_info.setText("")
            self._conductance_cb.setVisible(False)
            self._resistance_cb.setVisible(False)
        else:
            # If rows are already selected, plot them
            selected_rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
            if selected_rows and self._filtered_df is not None:
                self._plot_selected(selected_rows)

    def _clear_plot(self) -> None:
        """Clear plot and deselect all table rows."""
        self._plot_widget.clear()
        self._legend.clear()
        self._table.clearSelection()
        self._plot_info.setText("")
        self._conductance_cb.setVisible(False)
        self._resistance_cb.setVisible(False)

    # ── Cell formatters (matching TUI exactly) ──

    def _fmt_light(self, row: dict) -> tuple[str, QColor | None]:
        """Return (display_text, foreground_color) for the Light column."""
        if not self._has_light:
            return ("", None)
        value = row.get("has_light")
        if value is True:
            return ("\u2600", QColor("#e0af68"))   # ☀  yellow/amber
        if value is False:
            return ("\u263e", QColor("#7aa2f7"))    # ☾  blue
        return ("?", QColor("#565f89"))             # muted grey

    @staticmethod
    def _fmt_vg(row: dict) -> str:
        vg_start = row.get("vg_start_v")
        vg_end = row.get("vg_end_v")
        vg_fixed = row.get("vg_fixed_v")

        if vg_start is not None and vg_end is not None:
            return f"{vg_start:.2f} \u2192 {vg_end:.2f}"

        if vg_fixed is not None:
            try:
                return f"{float(vg_fixed):.2f}"
            except (TypeError, ValueError):
                return str(vg_fixed)

        return "-"

    @staticmethod
    def _fmt_led(row: dict) -> str:
        value = row.get("laser_voltage_v")
        if value is None:
            return "-"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _fmt_wavelength(row: dict) -> str:
        value = row.get("wavelength_nm")
        if value is None:
            return "-"
        try:
            return f"{float(value):.0f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _fmt_vds(row: dict) -> str:
        value = row.get("vds_v")
        if value is None:
            return "-"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)
