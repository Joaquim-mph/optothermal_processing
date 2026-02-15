"""
Reusable progress bar + status label widget.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt


class ProgressPanel(QWidget):
    """Combined progress bar and status label."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        self._status = QLabel("Initializing...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("font-size: 16px;")
        layout.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedWidth(400)
        layout.addWidget(self._bar, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_progress(self, percent: float, status: str) -> None:
        self._bar.setValue(int(percent))
        self._status.setText(status)

    def reset(self) -> None:
        self._bar.setValue(0)
        self._status.setText("Initializing...")
