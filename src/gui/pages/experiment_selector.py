"""
Experiment Selector Page.

Displays a QTableView with checkboxes for selecting experiments from chip history.
Supports select all/none and filters by procedure type.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List

import polars as pl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow

# Map plot types to their underlying data procedure names
PROC_MAPPING = {
    "ITS": "It",
    "Transconductance": "IVg",
    "Vt": "Vt",
    "VVg": "VVg",
    "IVg": "IVg",
    "CNP": None,       # Uses enriched history, no proc filter
    "Photoresponse": None,
    "LaserCalibration": "LaserCalibration",
    "ITSRelaxation": "It",
}


class ExperimentSelectorPage(QWidget):
    """Experiment selection page with checkbox table."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._experiments: pl.DataFrame | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Select Experiments")
        title.setObjectName("page-title")
        layout.addWidget(title)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("page-subtitle")
        layout.addWidget(self._subtitle)

        # Select all/none buttons
        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.clicked.connect(self._select_all)
        sel_row.addWidget(sel_all_btn)

        sel_none_btn = QPushButton("Select None")
        sel_none_btn.clicked.connect(self._select_none)
        sel_row.addWidget(sel_none_btn)

        self._count_label = QLabel("0 selected")
        self._count_label.setObjectName("info-label")
        sel_row.addWidget(self._count_label)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        # Table
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table, stretch=1)

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()

        next_btn = QPushButton("Generate Plot")
        next_btn.setObjectName("primary-btn")
        next_btn.clicked.connect(self._on_next)
        self._next_btn = next_btn
        nav_row.addWidget(next_btn)
        layout.addLayout(nav_row)

    def on_enter(self, **kwargs) -> None:
        """Load experiments from chip history."""
        session = self._window.session
        chip_name = f"{session.chip_group}{session.chip_number}"
        plot_type = session.plot_type or "?"
        self._subtitle.setText(f"Chip: {chip_name}  |  Plot: {plot_type}")

        self._load_experiments()

    def _load_experiments(self) -> None:
        """Load and filter experiments from chip history."""
        session = self._window.session
        chip_name = f"{session.chip_group}{session.chip_number}"
        history_file = session.history_dir / f"{chip_name}_history.parquet"

        if not history_file.exists():
            self._show_error(f"History file not found: {history_file}")
            return

        try:
            history = pl.read_parquet(history_file)
        except Exception as e:
            self._show_error(f"Failed to load history: {e}")
            return

        # Filter by procedure
        proc_filter = PROC_MAPPING.get(session.plot_type, session.plot_type)
        if proc_filter and "proc" in history.columns:
            history = history.filter(pl.col("proc") == proc_filter)

        if history.height == 0:
            self._show_error("No matching experiments found")
            return

        self._experiments = history
        self._populate_table(history)

    def _populate_table(self, df: pl.DataFrame) -> None:
        """Fill the table with experiment data."""
        self._table.blockSignals(True)

        # Choose columns to display
        display_cols = []
        for col in ["seq", "proc", "date", "date_local", "has_light", "vg_v", "wavelength_nm",
                     "laser_voltage_v", "vds_v", "run_id"]:
            if col in df.columns:
                display_cols.append(col)

        self._table.setColumnCount(len(display_cols) + 1)  # +1 for checkbox
        self._table.setHorizontalHeaderLabels([""] + display_cols)
        self._table.setRowCount(df.height)

        for row_idx in range(df.height):
            # Checkbox column
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Checked)
            self._table.setItem(row_idx, 0, check_item)

            # Data columns
            for col_idx, col_name in enumerate(display_cols):
                value = df[col_name][row_idx]
                text = str(value) if value is not None else ""
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._table.setItem(row_idx, col_idx + 1, item)

        # Auto-resize columns
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col_idx in range(1, len(display_cols) + 1):
            self._table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)

        self._table.blockSignals(False)
        self._update_count()

    def _show_error(self, msg: str) -> None:
        """Show error in the table area."""
        self._table.setRowCount(0)
        self._table.setColumnCount(1)
        self._table.setHorizontalHeaderLabels(["Error"])
        self._table.setRowCount(1)
        item = QTableWidgetItem(msg)
        self._table.setItem(0, 0, item)
        self._next_btn.setEnabled(False)

    def _get_selected_seqs(self) -> List[int]:
        """Get list of selected sequence numbers."""
        if self._experiments is None:
            return []
        seqs = []
        for row_idx in range(self._table.rowCount()):
            item = self._table.item(row_idx, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                if "seq" in self._experiments.columns:
                    seqs.append(int(self._experiments["seq"][row_idx]))
        return seqs

    def _select_all(self) -> None:
        self._table.blockSignals(True)
        for row_idx in range(self._table.rowCount()):
            item = self._table.item(row_idx, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
        self._table.blockSignals(False)
        self._update_count()

    def _select_none(self) -> None:
        self._table.blockSignals(True)
        for row_idx in range(self._table.rowCount()):
            item = self._table.item(row_idx, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._table.blockSignals(False)
        self._update_count()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._update_count()

    def _update_count(self) -> None:
        count = len(self._get_selected_seqs())
        total = self._table.rowCount()
        self._count_label.setText(f"{count} / {total} selected")
        self._next_btn.setEnabled(count > 0)

    def _on_next(self) -> None:
        """Save selection and proceed to preview."""
        seqs = self._get_selected_seqs()
        if not seqs:
            return
        self._window.session.seq_numbers = seqs
        self._window.router.navigate_to("preview")
