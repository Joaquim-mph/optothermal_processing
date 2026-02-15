"""
Plot Success Page.

Displays the generated plot image, file info, and action buttons.
"""

from __future__ import annotations
import subprocess
import sys
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PlotSuccessPage(QWidget):
    """Displays generated plot and provides action buttons."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._output_path = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("Plot Generated Successfully")
        self._title.setObjectName("success-label")
        layout.addWidget(self._title)

        self._info = QLabel("")
        self._info.setObjectName("info-label")
        layout.addWidget(self._info)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Image preview (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._image_label = QLabel("No preview available")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(self._image_label)
        layout.addWidget(scroll, stretch=1)

        # Action buttons
        btn_row = QHBoxLayout()

        open_btn = QPushButton("Open File")
        open_btn.clicked.connect(self._open_file)
        btn_row.addWidget(open_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self._open_folder)
        btn_row.addWidget(open_folder_btn)

        btn_row.addStretch()

        another_btn = QPushButton("Plot Another")
        another_btn.setObjectName("primary-btn")
        another_btn.clicked.connect(lambda: self._window.router.navigate_to("chip_selector"))
        btn_row.addWidget(another_btn)

        home_btn = QPushButton("Main Menu")
        home_btn.clicked.connect(self._window.router.return_to_main_menu)
        btn_row.addWidget(home_btn)

        layout.addLayout(btn_row)

    def on_enter(self, result=None, **kwargs) -> None:
        """Display the result."""
        if result is None:
            return

        self._output_path = result.output_path

        self._info.setText(
            f"File: {result.output_path.name}   |   "
            f"Size: {result.file_size_mb:.2f} MB   |   "
            f"Experiments: {result.num_experiments}   |   "
            f"Time: {result.elapsed_seconds:.1f}s"
        )

        # Load image preview
        path_str = str(result.output_path)
        if result.output_path.exists() and path_str.lower().endswith((".png", ".jpg", ".jpeg")):
            pixmap = QPixmap(path_str)
            if not pixmap.isNull():
                # Scale to fit width (max 900px) while keeping aspect ratio
                scaled = pixmap.scaledToWidth(
                    min(900, pixmap.width()),
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled)
            else:
                self._image_label.setText("Failed to load image preview")
        else:
            self._image_label.setText(f"Plot saved to:\n{result.output_path}")

    def _open_file(self) -> None:
        """Open the generated file with the system default application."""
        if self._output_path and self._output_path.exists():
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", str(self._output_path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._output_path)])
            else:
                subprocess.Popen(["start", str(self._output_path)], shell=True)

    def _open_folder(self) -> None:
        """Open the containing folder."""
        if self._output_path and self._output_path.parent.exists():
            folder = str(self._output_path.parent)
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", folder])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["explorer", folder])
