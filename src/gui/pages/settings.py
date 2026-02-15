"""
Settings Page.

Theme selector and UI preferences.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class SettingsPage(QWidget):
    """Application settings (theme, preferences)."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Configure application preferences")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Theme selector
        theme_header = QLabel("Theme")
        theme_header.setObjectName("section-header")
        layout.addWidget(theme_header)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Current theme:"))
        self._theme_combo = QComboBox()
        theme_row.addWidget(self._theme_combo)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_theme)
        theme_row.addWidget(apply_btn)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_defaults)
        theme_row.addWidget(reset_btn)

        theme_row.addStretch()
        layout.addLayout(theme_row)

        self._status_label = QLabel("")
        self._status_label.setObjectName("info-label")
        layout.addWidget(self._status_label)

        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # Info
        info_header = QLabel("Application Info")
        info_header.setObjectName("section-header")
        layout.addWidget(info_header)

        layout.addWidget(QLabel("Biotite Lab Plotter - PyQt6 GUI"))
        layout.addWidget(QLabel("Data: Polars Parquet pipeline"))
        layout.addWidget(QLabel("Plots: Matplotlib + scienceplots"))

        layout.addStretch()

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    def on_enter(self, **kwargs) -> None:
        self._populate_themes()

    def _populate_themes(self) -> None:
        self._theme_combo.clear()
        try:
            themes = self._window.settings_manager.get_available_themes()
            current = self._window.settings_manager.theme
            for theme in themes:
                display = self._window.settings_manager.get_theme_display_name(theme)
                self._theme_combo.addItem(display, theme)
            # Select current
            idx = self._theme_combo.findData(current)
            if idx >= 0:
                self._theme_combo.setCurrentIndex(idx)
        except Exception:
            self._theme_combo.addItem("Tokyo Night", "tokyo-night")

    def _apply_theme(self) -> None:
        theme_id = self._theme_combo.currentData()
        if theme_id:
            self._window.settings_manager.theme = theme_id
            display = self._theme_combo.currentText()
            self._status_label.setText(f"Theme saved: {display}")

    def _reset_defaults(self) -> None:
        self._window.settings_manager.reset_to_defaults()
        self._populate_themes()
        self._status_label.setText("Reset to defaults")
