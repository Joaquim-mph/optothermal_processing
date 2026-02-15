"""
Log Viewer Page.

Displays recent log entries from the GUI/TUI log file.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class LogViewerPage(QWidget):
    """Read-only log viewer."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Application Logs")
        title.setObjectName("page-title")
        layout.addWidget(title)

        self._path_label = QLabel("")
        self._path_label.setObjectName("page-subtitle")
        layout.addWidget(self._path_label)

        self._count_label = QLabel("")
        self._count_label.setObjectName("info-label")
        layout.addWidget(self._count_label)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Log content
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        layout.addWidget(self._log_text, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_logs)
        btn_row.addWidget(refresh_btn)

        btn_row.addStretch()

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        btn_row.addWidget(back_btn)

        layout.addLayout(btn_row)

    def on_enter(self, **kwargs) -> None:
        self._load_logs()

    def _load_logs(self) -> None:
        from src.tui.logging_config import read_recent_logs, get_log_file_path

        log_path = get_log_file_path()
        self._path_label.setText(f"Log file: {log_path}")

        lines = read_recent_logs(max_lines=500)
        self._count_label.setText(f"Showing last {len(lines)} entries")
        self._log_text.setPlainText("".join(lines))

        # Scroll to bottom
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
