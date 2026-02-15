"""
Plot Error Page.

Displays error message and traceback with action buttons.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PlotErrorPage(QWidget):
    """Error display page with traceback."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("Plot Generation Failed")
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

        # Action buttons
        btn_row = QHBoxLayout()

        retry_btn = QPushButton("Retry")
        retry_btn.clicked.connect(self._retry)
        btn_row.addWidget(retry_btn)

        back_btn = QPushButton("Change Config")
        back_btn.clicked.connect(self._go_back_to_config)
        btn_row.addWidget(back_btn)

        btn_row.addStretch()

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        btn_row.addWidget(home_btn)

        layout.addLayout(btn_row)

    def on_enter(self, error_msg="", error_type="", error_details="", **kwargs) -> None:
        """Display the error."""
        self._title.setText(f"Plot Generation Failed: {error_type}")
        self._error_msg.setText(error_msg)
        self._traceback.setPlainText(error_details)

    def _retry(self) -> None:
        """Retry plot generation with same config."""
        self._window.router.navigate_to("plot_generation")

    def _go_back_to_config(self) -> None:
        """Go back to configuration page."""
        plot_type = self._window.session.plot_type
        config_page_map = {
            "ITS": "its_config",
            "IVg": "ivg_config",
            "VVg": "vvg_config",
            "Vt": "vt_config",
            "Transconductance": "transconductance_config",
            "CNP": "cnp_config",
            "Photoresponse": "photoresponse_config",
            "LaserCalibration": "laser_calibration_config",
            "ITSRelaxation": "its_relaxation_config",
        }
        page = config_page_map.get(plot_type, "experiment_selector")
        self._window.router.navigate_to(page)
