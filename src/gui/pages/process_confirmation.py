"""
Process Confirmation Page.

Confirmation dialog before running the full data processing pipeline.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class ProcessConfirmationPage(QWidget):
    """Confirmation before pipeline execution."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Run Full Pipeline?")
        title.setObjectName("page-title")
        layout.addWidget(title)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        desc = QLabel(
            "This will run the complete data processing pipeline:\n\n"
            "  Step 1: Stage raw CSVs -> Parquet (schema-validated)\n"
            "  Step 2: Build chip histories from manifest\n"
            "  Step 3: Extract derived metrics (CNP, photoresponse, power)\n"
            "  Step 4: Enrich histories (join calibrations + metrics)\n\n"
            "Data paths:\n"
            "  Raw:      data/01_raw/\n"
            "  Staged:   data/02_stage/raw_measurements/\n"
            "  Histories: data/02_stage/chip_histories/\n"
            "  Derived:  data/03_derived/_metrics/\n"
            "  Enriched: data/03_derived/chip_histories_enriched/"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        warning = QLabel("This may take several minutes for large datasets.")
        warning.setObjectName("warning-label")
        layout.addWidget(warning)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._window.router.go_back)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()

        confirm_btn = QPushButton("Start Processing")
        confirm_btn.setObjectName("primary-btn")
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)

        layout.addLayout(btn_row)

    def _on_confirm(self) -> None:
        self._window.router.navigate_to("pipeline_loading")
