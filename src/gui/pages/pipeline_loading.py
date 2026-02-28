"""
Pipeline Loading Page.

Shows progress while running pipeline steps (full pipeline or individual).
Uses PipelineWorker for full_pipeline (backward compat) and
PipelineStepWorker for individual steps.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.gui.widgets.progress_panel import ProgressPanel
from src.gui.workers import PipelineWorker, PipelineStepWorker

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PipelineLoadingPage(QWidget):
    """Pipeline execution progress page."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._worker: PipelineWorker | PipelineStepWorker | None = None
        self._step_name = "full_pipeline"
        self._options: dict = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self._title = QLabel("Processing Data...")
        self._title.setObjectName("page-title")
        layout.addWidget(self._title)

        self._step_label = QLabel("Initializing pipeline...")
        self._step_label.setObjectName("info-label")
        layout.addWidget(self._step_label)

        layout.addStretch()
        self._progress = ProgressPanel()
        layout.addWidget(self._progress)
        layout.addStretch()

    def on_enter(self, step_name: str = "full_pipeline", options: dict | None = None, **kwargs) -> None:
        """Start pipeline execution for the given step."""
        self._step_name = step_name
        self._options = options or {}
        self._progress.reset()

        label = PipelineStepWorker.STEP_LABELS.get(step_name, step_name.replace("_", " ").title())
        self._title.setText(f"{label}...")
        self._step_label.setText(f"Starting {label.lower()}...")

        if step_name == "full_pipeline":
            self._worker = PipelineWorker()
        else:
            self._worker = PipelineStepWorker(step_name, self._options)

        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, percent: float, status: str) -> None:
        self._progress.set_progress(percent, status)
        self._step_label.setText(status)

    def _on_finished(self, result: dict) -> None:
        self._window.router.navigate_to(
            "process_success",
            result=result,
            step_name=self._step_name,
        )

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        self._window.router.navigate_to(
            "process_error",
            error_msg=error_msg,
            error_type=error_type,
            error_details=error_details,
            step_name=self._step_name,
            options=self._options,
        )
