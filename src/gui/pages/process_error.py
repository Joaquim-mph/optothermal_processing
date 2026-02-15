"""
Pipeline Error Page.

Displays error details if data processing fails.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class ProcessErrorPage(QWidget):
    """Pipeline error result page with traceback."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
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

        retry_btn = QPushButton("Retry")
        retry_btn.clicked.connect(lambda: self._window.router.navigate_to("pipeline_loading"))
        btn_row.addWidget(retry_btn)

        btn_row.addStretch()

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        btn_row.addWidget(home_btn)

        layout.addLayout(btn_row)

    def on_enter(self, error_msg="", error_type="", error_details="", **kwargs) -> None:
        self._title.setText(f"Processing Failed: {error_type}")
        self._error_msg.setText(error_msg)
        self._traceback.setPlainText(error_details)

        # Generate suggestion
        lower = error_msg.lower()
        if "not found" in lower or "does not exist" in lower:
            suggestion = "Verify that all required directories and files exist."
        elif "permission" in lower:
            suggestion = "Check file permissions on data directories."
        else:
            suggestion = (
                "You can also run the pipeline from the command line:\n"
                "  biotite full-pipeline"
            )
        self._suggestion.setText(suggestion)
