"""
Data Pipeline Menu Page.

Shows pipeline operation buttons for staging, history building, etc.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class DataPipelineMenuPage(QWidget):
    """Menu for data processing pipeline operations."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Process Data")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Run the data processing pipeline")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Pipeline description
        desc = QLabel(
            "The full pipeline stages raw CSVs to Parquet, builds chip histories,\n"
            "extracts derived metrics (CNP, photoresponse, power), and enriches\n"
            "histories with calibration and metric data."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        # Pipeline steps info
        steps_label = QLabel("Pipeline Steps:")
        steps_label.setObjectName("section-header")
        layout.addWidget(steps_label)

        steps = [
            "1. Stage raw CSVs -> Parquet (schema-validated)",
            "2. Build chip histories from manifest",
            "3. Extract derived metrics (CNP, photoresponse, relaxation)",
            "4. Enrich histories (join calibrations + metrics)",
        ]
        for step in steps:
            layout.addWidget(QLabel(f"  {step}"))

        layout.addSpacing(16)

        # Action button
        run_btn = QPushButton("Run Full Pipeline")
        run_btn.setObjectName("primary-btn")
        run_btn.setFixedHeight(48)
        run_btn.clicked.connect(self._on_run_pipeline)
        layout.addWidget(run_btn)

        layout.addStretch()

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    def _on_run_pipeline(self) -> None:
        self._window.router.navigate_to("process_confirmation")
