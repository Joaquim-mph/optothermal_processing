"""
Config Mode Selector Page.

Offers Quick / Custom / Preset / Recent modes for plot configuration.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


# Plot types that have preset configurations
PRESET_PLOT_TYPES = {"ITS", "Vt"}

# Map plot type -> config page name
CONFIG_PAGE_MAP = {
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

# Map plot type -> preset selector page name
PRESET_PAGE_MAP = {
    "ITS": "its_preset_selector",
    "Vt": "vt_preset_selector",
}


class ConfigModeSelectorPage(QWidget):
    """Configuration mode selection: Quick / Custom / Preset / Recent."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Configuration Mode")
        title.setObjectName("page-title")
        layout.addWidget(title)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("page-subtitle")
        layout.addWidget(self._subtitle)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Mode buttons
        self._quick_btn = self._make_mode_button(
            "Quick",
            "Use default settings and go straight to experiment selection",
            self._on_quick,
        )
        layout.addWidget(self._quick_btn)

        self._custom_btn = self._make_mode_button(
            "Custom",
            "Configure all plot parameters manually",
            self._on_custom,
        )
        layout.addWidget(self._custom_btn)

        self._preset_btn = self._make_mode_button(
            "Preset",
            "Choose from predefined configurations (ITS, Vt)",
            self._on_preset,
        )
        layout.addWidget(self._preset_btn)

        self._recent_btn = self._make_mode_button(
            "Recent",
            "Load a previously saved configuration",
            self._on_recent,
        )
        layout.addWidget(self._recent_btn)

        layout.addStretch()

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    def _make_mode_button(self, label: str, description: str, callback) -> QPushButton:
        btn = QPushButton(f"{label}\n{description}")
        btn.setObjectName("chip-card")  # Reuse card style
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(64)
        btn.clicked.connect(callback)
        return btn

    def on_enter(self, **kwargs) -> None:
        plot_type = self._window.session.plot_type or "?"
        chip_name = ""
        if self._window.session.chip_number is not None:
            chip_name = f"{self._window.session.chip_group}{self._window.session.chip_number}"
        self._subtitle.setText(f"Chip: {chip_name}  |  Plot: {plot_type}")

        # Enable/disable preset button based on plot type
        has_presets = plot_type in PRESET_PLOT_TYPES
        self._preset_btn.setEnabled(has_presets)

    def _on_quick(self) -> None:
        """Skip config, go straight to experiment selector with defaults."""
        self._window.router.navigate_to("experiment_selector")

    def _on_custom(self) -> None:
        """Go to the plot-type-specific config page."""
        plot_type = self._window.session.plot_type
        page = CONFIG_PAGE_MAP.get(plot_type, "experiment_selector")
        self._window.router.navigate_to(page)

    def _on_preset(self) -> None:
        """Go to preset selector for the current plot type."""
        plot_type = self._window.session.plot_type
        page = PRESET_PAGE_MAP.get(plot_type)
        if page:
            self._window.router.navigate_to(page)
        else:
            # Fallback to custom config
            self._on_custom()

    def _on_recent(self) -> None:
        """Go to recent configs page."""
        self._window.router.navigate_to("recent_configs")
