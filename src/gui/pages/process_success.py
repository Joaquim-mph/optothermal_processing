"""
Pipeline Success Page.

Displays results after successful data processing.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class ProcessSuccessPage(QWidget):
    """Pipeline success result page."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("Processing Complete")
        self._title.setObjectName("success-label")
        layout.addWidget(self._title)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        results_header = QLabel("Pipeline Results")
        results_header.setObjectName("section-header")
        layout.addWidget(results_header)

        self._results_label = QLabel("")
        self._results_label.setWordWrap(True)
        layout.addWidget(self._results_label)

        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        output_header = QLabel("Output Locations")
        output_header.setObjectName("section-header")
        layout.addWidget(output_header)

        layout.addWidget(QLabel("  data/02_stage/raw_measurements/ - Staged Parquet files"))
        layout.addWidget(QLabel("  data/02_stage/raw_measurements/_manifest/ - Manifest"))
        layout.addWidget(QLabel("  data/02_stage/chip_histories/ - Chip history Parquet"))

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()

        plot_btn = QPushButton("New Plot")
        plot_btn.setObjectName("primary-btn")
        plot_btn.clicked.connect(lambda: self._window.router.navigate_to("chip_selector"))
        btn_row.addWidget(plot_btn)

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        btn_row.addWidget(home_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def on_enter(self, result: dict | None = None, **kwargs) -> None:
        if result is None:
            result = {}

        elapsed = result.get("elapsed", 0)
        files = result.get("files_processed", 0)
        experiments = result.get("experiments", 0)
        histories = result.get("histories", 0)
        chips = result.get("total_chips", 0)

        self._results_label.setText(
            f"CSV files staged: {files}\n"
            f"Experiments in manifest: {experiments}\n"
            f"Chip histories generated: {histories} / {chips} chips\n"
            f"Total processing time: {elapsed:.1f}s"
        )
