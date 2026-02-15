"""
ITS Preset Selector Page.

Lists available ITS presets for quick configuration.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt

from src.plotting.its_presets import PRESETS, preset_summary

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class ITSPresetSelectorPage(QWidget):
    """ITS preset selection page."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Choose ITS Preset")
        title.setObjectName("page-title")
        layout.addWidget(title)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("page-subtitle")
        layout.addWidget(self._subtitle)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Scrollable preset list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setSpacing(8)

        for preset_id, preset in PRESETS.items():
            btn = QPushButton(f"{preset.name}\n{preset.description}")
            btn.setObjectName("chip-card")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(64)
            btn.setToolTip(preset_summary(preset))
            btn.clicked.connect(lambda checked, pid=preset_id: self._select_preset(pid))
            list_layout.addWidget(btn)

        list_layout.addStretch()
        scroll.setWidget(list_container)
        layout.addWidget(scroll, stretch=1)

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    def on_enter(self, **kwargs) -> None:
        if self._window.session.chip_number is not None:
            chip_name = f"{self._window.session.chip_group}{self._window.session.chip_number}"
            self._subtitle.setText(f"Chip: {chip_name}  |  Plot: ITS")

    def _select_preset(self, preset_id: str) -> None:
        preset = PRESETS.get(preset_id)
        if preset is None:
            return

        # Apply preset to session
        s = self._window.session
        s.baseline_mode = preset.baseline_mode
        s.baseline = preset.baseline_value
        s.baseline_auto_divisor = preset.baseline_auto_divisor
        s.plot_start_time = preset.plot_start_time
        s.legend_by = preset.legend_by
        s.padding = preset.padding
        s.check_duration_mismatch = preset.check_duration_mismatch
        s.duration_tolerance = preset.duration_tolerance

        # Navigate to experiment selector with preset applied
        self._window.router.navigate_to("experiment_selector")
