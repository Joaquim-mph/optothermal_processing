"""
Pipeline Success Page.

Displays step-specific results after successful data processing.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from src.gui.workers import PipelineStepWorker

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

        self._results_header = QLabel("Results")
        self._results_header.setObjectName("section-header")
        layout.addWidget(self._results_header)

        self._results_label = QLabel("")
        self._results_label.setWordWrap(True)
        layout.addWidget(self._results_label)

        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        self._output_header = QLabel("Output Locations")
        self._output_header.setObjectName("section-header")
        layout.addWidget(self._output_header)

        self._output_label = QLabel("")
        self._output_label.setWordWrap(True)
        layout.addWidget(self._output_label)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()

        plot_btn = QPushButton("New Plot")
        plot_btn.setObjectName("primary-btn")
        plot_btn.clicked.connect(lambda: self._window.router.navigate_to("chip_selector"))
        btn_row.addWidget(plot_btn)

        pipeline_btn = QPushButton("Pipeline Menu")
        pipeline_btn.clicked.connect(lambda: self._window.router.navigate_to("data_pipeline_menu"))
        btn_row.addWidget(pipeline_btn)

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        btn_row.addWidget(home_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def on_enter(self, result: dict | None = None, step_name: str = "full_pipeline", **kwargs) -> None:
        if result is None:
            result = {}

        label = PipelineStepWorker.STEP_LABELS.get(step_name, "Processing")
        self._title.setText(f"{label} Complete")

        elapsed = result.get("elapsed", 0)

        if step_name == "full_pipeline":
            self._results_header.setText("Pipeline Results")
            self._results_label.setText(
                f"CSV files staged: {result.get('files_processed', 0)}\n"
                f"Experiments in manifest: {result.get('experiments', 0)}\n"
                f"Chip histories generated: {result.get('histories', 0)} / {result.get('total_chips', 0)} chips\n"
                f"Total processing time: {elapsed:.1f}s"
            )
            self._output_header.setVisible(True)
            self._output_label.setVisible(True)
            self._output_label.setText(
                "  data/02_stage/raw_measurements/ - Staged Parquet files\n"
                "  data/02_stage/raw_measurements/_manifest/ - Manifest\n"
                "  data/02_stage/chip_histories/ - Chip history Parquet\n"
                "  data/03_derived/_metrics/ - Derived metrics\n"
                "  data/03_derived/chip_histories_enriched/ - Enriched histories"
            )
        else:
            self._results_header.setText("Results")
            summary = result.get("summary", "Operation completed successfully.")
            self._results_label.setText(f"{summary}\nTime: {elapsed:.1f}s")

            # Show step-specific output paths
            output_paths = _get_output_paths(step_name)
            if output_paths:
                self._output_header.setVisible(True)
                self._output_label.setVisible(True)
                self._output_label.setText(output_paths)
            else:
                self._output_header.setVisible(False)
                self._output_label.setVisible(False)


def _get_output_paths(step_name: str) -> str:
    """Return output path descriptions for a given step."""
    paths = {
        "stage_all": (
            "  data/02_stage/raw_measurements/ - Staged Parquet files\n"
            "  data/02_stage/raw_measurements/_manifest/ - Manifest"
        ),
        "build_histories": (
            "  data/02_stage/chip_histories/ - Chip history Parquet files"
        ),
        "derive_all_metrics": (
            "  data/03_derived/_metrics/metrics.parquet - All derived metrics"
        ),
        "derive_fitting_metrics": (
            "  data/03_derived/_metrics/metrics.parquet - Fitting metrics"
        ),
        "derive_consecutive_sweeps": (
            "  data/03_derived/_metrics/metrics.parquet - Sweep difference metrics"
        ),
        "enrich_history": (
            "  data/03_derived/chip_histories_enriched/ - Enriched histories"
        ),
    }
    return paths.get(step_name, "")
