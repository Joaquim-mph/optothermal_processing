"""
Pipeline Loading Page.

Shows progress while running the full data processing pipeline.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

from src.gui.widgets.progress_panel import ProgressPanel
from src.gui.workers import PipelineWorker

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PipelineLoadingPage(QWidget):
    """Pipeline execution progress page."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._worker: PipelineWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Processing Data...")
        title.setObjectName("page-title")
        layout.addWidget(title)

        self._step_label = QLabel("Initializing pipeline...")
        self._step_label.setObjectName("info-label")
        layout.addWidget(self._step_label)

        layout.addStretch()
        self._progress = ProgressPanel()
        layout.addWidget(self._progress)
        layout.addStretch()

    def on_enter(self, **kwargs) -> None:
        """Start pipeline execution."""
        self._progress.reset()
        self._step_label.setText("Starting full pipeline...")

        self._worker = PipelineWorker()
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, percent: float, status: str) -> None:
        self._progress.set_progress(percent, status)
        self._step_label.setText(status)

    def _on_finished(self, result: dict) -> None:
        self._window.router.navigate_to("process_success", result=result)

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        self._window.router.navigate_to(
            "process_error",
            error_msg=error_msg,
            error_type=error_type,
            error_details=error_details,
        )
