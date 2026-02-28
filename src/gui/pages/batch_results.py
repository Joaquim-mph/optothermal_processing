"""
Batch Plot Results Page.

Displays a summary table of batch plot results with success/fail counts,
timing info, and action buttons.
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class BatchResultsPage(QWidget):
    """Results summary table for batch plot execution."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._config_path: str = ""
        self._chip: int | None = None
        self._chip_group: str = "Alisson"
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("Batch Complete")
        self._title.setObjectName("success-label")
        layout.addWidget(self._title)

        self._summary = QLabel("")
        self._summary.setObjectName("page-subtitle")
        layout.addWidget(self._summary)

        # Results table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Type", "Tag", "Status", "Time"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()

        self._open_btn = QPushButton("Open Output Folder")
        self._open_btn.clicked.connect(self._open_output_folder)
        btn_row.addWidget(self._open_btn)

        run_another_btn = QPushButton("Run Another")
        run_another_btn.setObjectName("primary-btn")
        run_another_btn.clicked.connect(
            lambda: self._window.router.navigate_to("batch_plot")
        )
        btn_row.addWidget(run_another_btn)

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        btn_row.addWidget(home_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def on_enter(self, results: list | None = None, config_path: str = "", **kwargs) -> None:
        """Populate results table from PlotResult list."""
        self._config_path = config_path
        results = results or []

        # Try to extract chip info from config
        self._chip = None
        self._chip_group = "Alisson"
        if config_path:
            try:
                from src.plotting.batch import load_batch_config
                chip, chip_group, _ = load_batch_config(Path(config_path))
                self._chip = chip
                self._chip_group = chip_group
            except Exception:
                pass

        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded
        total_time = sum(r.elapsed for r in results)

        if failed > 0:
            self._title.setText("Batch Complete (with errors)")
            self._title.setObjectName("warning-label")
        else:
            self._title.setText("Batch Complete")
            self._title.setObjectName("success-label")
        # Force style refresh after objectName change
        self._title.style().unpolish(self._title)
        self._title.style().polish(self._title)

        self._summary.setText(
            f"{succeeded}/{len(results)} succeeded  |  "
            f"{failed} failed  |  {total_time:.1f}s total"
        )

        # Populate table
        self._table.setRowCount(len(results))
        for row, result in enumerate(results):
            # Type
            type_item = QTableWidgetItem(result.spec.type)
            self._table.setItem(row, 0, type_item)

            # Tag
            tag_item = QTableWidgetItem(result.spec.tag or "")
            self._table.setItem(row, 1, tag_item)

            # Status
            if result.success:
                plots_info = f" [{result.plots_generated}]" if result.plots_generated > 1 else ""
                status_item = QTableWidgetItem(f"OK{plots_info}")
                status_item.setForeground(QColor("#9ece6a"))
            else:
                error_short = (result.error or "error")[:40]
                status_item = QTableWidgetItem(f"FAIL: {error_short}")
                status_item.setForeground(QColor("#f7768e"))
            self._table.setItem(row, 2, status_item)

            # Time
            time_item = QTableWidgetItem(f"{result.elapsed:.1f}s")
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 3, time_item)

    def _open_output_folder(self) -> None:
        """Open the figs output directory in the system file manager."""
        if self._chip is not None:
            folder = Path("figs") / f"{self._chip_group}{self._chip}"
        else:
            folder = Path("figs")

        folder = folder.resolve()
        if not folder.exists():
            folder = Path("figs").resolve()

        if sys.platform == "linux":
            subprocess.Popen(["xdg-open", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["explorer", str(folder)])
