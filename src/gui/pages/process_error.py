"""
Pipeline Error Page.

Displays error details if data processing fails, with step-aware retry.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame,
)

from src.gui.workers import PipelineStepWorker

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class ProcessErrorPage(QWidget):
    """Pipeline error result page with traceback."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._step_name = "full_pipeline"
        self._options: dict = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("Processing Failed")
        self._title.setObjectName("error-label")
        layout.addWidget(self._title)

        self._error_msg = QLabel("")
        self._error_msg.setWordWrap(True)
        layout.addWidget(self._error_msg)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        details_label = QLabel("Traceback:")
        details_label.setObjectName("section-header")
        layout.addWidget(details_label)

        self._traceback = QPlainTextEdit()
        self._traceback.setReadOnly(True)
        layout.addWidget(self._traceback, stretch=1)

        self._suggestion = QLabel("")
        self._suggestion.setObjectName("warning-label")
        self._suggestion.setWordWrap(True)
        layout.addWidget(self._suggestion)

        # Buttons
        btn_row = QHBoxLayout()

        self._retry_btn = QPushButton("Retry")
        self._retry_btn.clicked.connect(self._on_retry)
        btn_row.addWidget(self._retry_btn)

        pipeline_btn = QPushButton("Pipeline Menu")
        pipeline_btn.clicked.connect(lambda: self._window.router.navigate_to("data_pipeline_menu"))
        btn_row.addWidget(pipeline_btn)

        btn_row.addStretch()

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        btn_row.addWidget(home_btn)

        layout.addLayout(btn_row)

    def on_enter(
        self,
        error_msg="",
        error_type="",
        error_details="",
        step_name: str = "full_pipeline",
        options: dict | None = None,
        **kwargs,
    ) -> None:
        self._step_name = step_name
        self._options = options or {}

        label = PipelineStepWorker.STEP_LABELS.get(step_name, "Processing")
        self._title.setText(f"{label} Failed: {error_type}")
        self._error_msg.setText(error_msg)
        self._traceback.setPlainText(error_details)

        # Generate suggestion
        lower = error_msg.lower()
        if "not found" in lower or "does not exist" in lower:
            suggestion = "Verify that all required directories and files exist."
        elif "permission" in lower:
            suggestion = "Check file permissions on data directories."
        else:
            cli_cmd = _step_to_cli_command(step_name)
            suggestion = (
                f"You can also run this from the command line:\n"
                f"  biotite {cli_cmd}"
            )
        self._suggestion.setText(suggestion)

    def _on_retry(self) -> None:
        self._window.router.navigate_to(
            "pipeline_loading",
            step_name=self._step_name,
            options=self._options,
        )


def _step_to_cli_command(step_name: str) -> str:
    """Map step name to CLI command for suggestions."""
    mapping = {
        "full_pipeline": "full-pipeline",
        "stage_all": "stage-all",
        "build_histories": "build-all-histories",
        "derive_all_metrics": "derive-all-metrics",
        "derive_fitting_metrics": "derive-fitting-metrics",
        "derive_consecutive_sweeps": "derive-consecutive-sweeps",
        "enrich_history": "enrich-history",
        "validate_manifest": "validate-manifest",
        "staging_stats": "staging-stats",
    }
    return mapping.get(step_name, "full-pipeline")
