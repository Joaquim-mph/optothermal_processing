"""
Plot Generation Page.

Shows a progress bar driven by PlotWorker signals.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.gui.widgets.progress_panel import ProgressPanel
from src.gui.workers import PlotWorker
from src.core.plot_executor import PlotRequest, PlotResult

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PlotGenerationPage(QWidget):
    """Plot generation progress page."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._worker: PlotWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Generating Plot...")
        title.setObjectName("page-title")
        layout.addWidget(title)

        layout.addStretch()
        self._progress = ProgressPanel()
        layout.addWidget(self._progress)
        layout.addStretch()

    def on_enter(self, **kwargs) -> None:
        """Start plot generation."""
        self._progress.reset()

        session = self._window.session
        request = PlotRequest(
            chip_number=session.chip_number,
            chip_group=session.chip_group,
            plot_type=session.plot_type,
            seq_numbers=list(session.seq_numbers),
            config=session.to_config_dict(),
            stage_dir=session.stage_dir,
            history_dir=session.history_dir,
            output_dir=session.output_dir,
        )

        self._worker = PlotWorker(request)
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, percent: float, status: str) -> None:
        self._progress.set_progress(percent, status)

    def _on_finished(self, result: PlotResult) -> None:
        # Save configuration for reuse
        try:
            save_config = {
                **self._window.session.to_config_dict(),
                "chip_number": self._window.session.chip_number,
                "chip_group": self._window.session.chip_group,
                "plot_type": self._window.session.plot_type,
                "seq_numbers": list(self._window.session.seq_numbers),
            }
            self._window.config_manager.save_config(save_config)
        except Exception:
            pass

        self._window.router.navigate_to(
            "plot_success",
            result=result,
        )

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        self._window.router.navigate_to(
            "plot_error",
            error_msg=error_msg,
            error_type=error_type,
            error_details=error_details,
        )
