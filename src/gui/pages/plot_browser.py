"""
Plot Browser Page.

Two-pane layout: QTreeView (directory tree) + QLabel (image preview).
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeView, QSplitter, QFrame, QScrollArea,
)
from PyQt6.QtGui import QPixmap, QFileSystemModel
from PyQt6.QtCore import Qt, QModelIndex

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PlotBrowserPage(QWidget):
    """Browse generated plots with directory tree and image preview."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._current_path: Path | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Plot Browser")
        title.setObjectName("page-title")
        layout.addWidget(title)

        # Splitter: tree | preview
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: directory tree
        self._fs_model = QFileSystemModel()
        self._fs_model.setNameFilters(["*.png", "*.jpg", "*.jpeg", "*.pdf"])
        self._fs_model.setNameFilterDisables(False)

        self._tree = QTreeView()
        self._tree.setModel(self._fs_model)
        self._tree.setHeaderHidden(False)
        # Hide Size, Type, Date Modified columns (keep Name)
        for col in (1, 2, 3):
            self._tree.setColumnHidden(col, True)
        self._tree.clicked.connect(self._on_tree_clicked)
        splitter.addWidget(self._tree)

        # Right: image preview + metadata
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._image_label = QLabel("Select a plot file to preview")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setWordWrap(True)
        scroll.setWidget(self._image_label)
        right_layout.addWidget(scroll, stretch=1)

        self._meta_label = QLabel("")
        self._meta_label.setObjectName("info-label")
        self._meta_label.setWordWrap(True)
        right_layout.addWidget(self._meta_label)

        # Action buttons
        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open in Viewer")
        open_btn.clicked.connect(self._open_external)
        btn_row.addWidget(open_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_tree)
        btn_row.addWidget(refresh_btn)

        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter, stretch=1)

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    def on_enter(self, **kwargs) -> None:
        """Set the root to the figs/ directory."""
        figs_dir = Path(self._window.session.output_dir)
        if not figs_dir.exists():
            self._image_label.setText(
                f"No plots directory found.\n\n"
                f"Expected: {figs_dir.absolute()}\n\n"
                f"Generate some plots first!"
            )
            return

        root_path = str(figs_dir.absolute())
        self._fs_model.setRootPath(root_path)
        self._tree.setRootIndex(self._fs_model.index(root_path))

    def _on_tree_clicked(self, index: QModelIndex) -> None:
        path = Path(self._fs_model.filePath(index))
        if not path.is_file():
            return
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            self._image_label.setText(f"Cannot preview: {path.name}")
            return

        self._current_path = path

        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            scaled = pixmap.scaledToWidth(
                min(800, pixmap.width()),
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image_label.setPixmap(scaled)
        else:
            self._image_label.setText("Failed to load image")

        # Metadata
        try:
            stat = path.stat()
            size_mb = stat.st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            self._meta_label.setText(
                f"File: {path.name}  |  Size: {size_mb:.2f} MB  |  Modified: {modified}"
            )
        except Exception:
            self._meta_label.setText(f"File: {path.name}")

    def _open_external(self) -> None:
        if self._current_path and self._current_path.exists():
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", str(self._current_path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._current_path)])
            else:
                subprocess.Popen(["start", str(self._current_path)], shell=True)

    def _refresh_tree(self) -> None:
        figs_dir = Path(self._window.session.output_dir)
        if figs_dir.exists():
            root_path = str(figs_dir.absolute())
            self._fs_model.setRootPath(root_path)
            self._tree.setRootIndex(self._fs_model.index(root_path))
