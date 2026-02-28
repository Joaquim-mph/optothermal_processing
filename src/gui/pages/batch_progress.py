"""
Batch Plot Progress Page.

Shows per-plot progress with a log of completed plots and a cancel button.
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QPlainTextEdit,
)
from PyQt6.QtCore import Qt

from src.gui.workers import BatchPlotWorker

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class BatchProgressPage(QWidget):
    """Batch plot execution progress with per-plot log."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._worker: BatchPlotWorker | None = None
        self._config_path: str = ""
        self._results: list = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("Running Batch...")
        self._title.setObjectName("page-title")
        layout.addWidget(self._title)

        self._status_label = QLabel("Initializing...")
        self._status_label.setObjectName("info-label")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._current_label = QLabel("")
        self._current_label.setObjectName("page-subtitle")
        layout.addWidget(self._current_label)

        log_header = QLabel("Log")
        log_header.setObjectName("section-header")
        layout.addWidget(log_header)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log, stretch=1)

        # Cancel button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("danger-btn")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    def on_enter(self, config_path: str = "", parallel: bool = False, workers: int = 4, **kwargs) -> None:
        """Start batch plot worker."""
        self._config_path = config_path
        self._results = []
        self._log.clear()
        self._progress.setValue(0)
        self._cancel_btn.setEnabled(True)

        config_name = Path(config_path).stem if config_path else "unknown"
        mode = f"parallel ({workers} workers)" if parallel else "sequential"
        self._title.setText(f"Running Batch: {config_name}")
        self._status_label.setText(f"Starting ({mode})...")
        self._current_label.setText("")

        self._worker = BatchPlotWorker(config_path, parallel=parallel, workers=workers)
        self._worker.plot_started.connect(self._on_plot_started)
        self._worker.plot_finished.connect(self._on_plot_finished)
        self._worker.all_finished.connect(self._on_all_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_plot_started(self, index: int, total: int, desc: str) -> None:
        pct = int((index / total) * 100) if total > 0 else 0
        self._progress.setValue(pct)
        self._status_label.setText(f"Plot {index + 1} / {total}")
        self._current_label.setText(f"Processing: {desc}")

    def _on_plot_finished(self, index: int, result) -> None:
        self._results.append(result)
        if result.success:
            tag_str = f" ({result.spec.tag})" if result.spec.tag else ""
            plots_info = f" [{result.plots_generated} plots]" if result.plots_generated > 1 else ""
            self._log.appendPlainText(
                f"  {result.spec.type}{tag_str}{plots_info} ({result.elapsed:.1f}s)"
            )
        else:
            tag_str = f" ({result.spec.tag})" if result.spec.tag else ""
            error_msg = result.error or "unknown error"
            self._log.appendPlainText(
                f"  FAIL {result.spec.type}{tag_str}: {error_msg}"
            )

    def _on_all_finished(self, results: list) -> None:
        self._progress.setValue(100)
        self._cancel_btn.setEnabled(False)

        self._window.router.navigate_to(
            "batch_results",
            results=results,
            config_path=self._config_path,
        )

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        self._cancel_btn.setEnabled(False)
        self._status_label.setText(f"Error: {error_type}")
        self._current_label.setText(error_msg)
        self._log.appendPlainText(f"\n--- ERROR ---\n{error_details}")

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._status_label.setText("Cancelling...")
