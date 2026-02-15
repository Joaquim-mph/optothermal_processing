"""
Plot Type Selector Page.

Displays radio-style list of plot types with descriptions.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


# Plot type definitions: (id, label, description, config_page)
PLOT_TYPES = [
    ("ITS", "It (Current vs Time)",
     "Photocurrent time series with light/dark cycles", "its_config"),
    ("IVg", "IVg (Transfer Curves)",
     "Gate voltage sweep characteristics (Id vs Vg)", "ivg_config"),
    ("Transconductance", "Transconductance (gm)",
     "gm = dI/dVg derivative analysis from IVg data", "transconductance_config"),
    ("VVg", "VVg (Drain-Source vs Gate)",
     "Drain-source voltage vs gate voltage sweeps", "vvg_config"),
    ("Vt", "Vt (Voltage vs Time)",
     "Voltage time series measurements", "vt_config"),
    ("CNP", "CNP Time Evolution",
     "Charge Neutrality Point evolution over time (requires enriched history)", "cnp_config"),
    ("Photoresponse", "Photoresponse Analysis",
     "Device response vs power, wavelength, gate voltage, or time (requires enriched history)", "photoresponse_config"),
    ("ITSRelaxation", "It Relaxation Fits",
     "Stretched exponential relaxation time fits (requires derived metrics)", "its_relaxation_config"),
    ("LaserCalibration", "Laser Calibration",
     "Laser power vs control voltage calibration curves (global)", "laser_calibration_config"),
]


class PlotTypeSelectorPage(QWidget):
    """Plot type selection page."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._button_group = QButtonGroup(self)
        self._type_map: dict[int, tuple[str, str | None]] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Select Plot Type")
        title.setObjectName("page-title")
        layout.addWidget(title)

        chip_label = QLabel("")
        chip_label.setObjectName("page-subtitle")
        self._chip_label = chip_label
        layout.addWidget(chip_label)

        # Scrollable list of plot types
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setSpacing(8)

        for i, (type_id, label, desc, config_page) in enumerate(PLOT_TYPES):
            radio = QRadioButton(label)
            radio.setToolTip(desc)
            radio.setStyleSheet("font-size: 14px; padding: 6px 0;")
            self._button_group.addButton(radio, i)
            self._type_map[i] = (type_id, config_page)

            desc_label = QLabel(desc)
            desc_label.setObjectName("info-label")
            desc_label.setStyleSheet("margin-left: 26px; margin-bottom: 4px;")

            list_layout.addWidget(radio)
            list_layout.addWidget(desc_label)

        list_layout.addStretch()
        scroll.setWidget(list_container)
        layout.addWidget(scroll, stretch=1)

        # Navigation buttons
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()

        next_btn = QPushButton("Next")
        next_btn.setObjectName("primary-btn")
        next_btn.clicked.connect(self._on_next)
        nav_row.addWidget(next_btn)
        layout.addLayout(nav_row)

    def on_enter(self, **kwargs) -> None:
        """Update chip label."""
        if self._window.session.chip_number is not None:
            self._chip_label.setText(
                f"Chip: {self._window.session.chip_group}{self._window.session.chip_number}"
            )
        # Pre-select ITS by default
        btn = self._button_group.button(0)
        if btn:
            btn.setChecked(True)

    def _on_next(self) -> None:
        """Handle Next button click."""
        checked_id = self._button_group.checkedId()
        if checked_id < 0:
            return

        type_id, config_page = self._type_map[checked_id]
        self._window.session.plot_type = type_id

        if config_page:
            self._window.router.navigate_to(config_page)
        else:
            # Skip config for types without a config page (go straight to experiment selector)
            self._window.router.navigate_to("experiment_selector")
