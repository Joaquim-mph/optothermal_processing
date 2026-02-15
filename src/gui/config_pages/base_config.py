"""
Base Config Page with form layout helpers.

Provides factory functions for creating labeled form rows
(combo boxes, spin boxes, checkboxes, etc.) used by all config pages.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Sequence

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class BaseConfigPage(QWidget):
    """
    Base class for plot configuration pages.

    Subclasses implement _build_form() to add fields to self._form.
    """

    PAGE_TITLE = "Configuration"
    PAGE_SUBTITLE = ""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._form = QFormLayout()
        self._form.setSpacing(12)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel(self.PAGE_TITLE)
        title.setObjectName("page-title")
        layout.addWidget(title)

        self._subtitle_label = QLabel(self.PAGE_SUBTITLE)
        self._subtitle_label.setObjectName("page-subtitle")
        layout.addWidget(self._subtitle_label)

        # Form area
        form_container = QWidget()
        form_container.setLayout(self._form)
        layout.addWidget(form_container)

        # Subclass populates the form
        self._build_form()

        layout.addStretch()

        # Navigation
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

    def _build_form(self) -> None:
        """Override in subclass to populate the form."""
        pass

    def _on_next(self) -> None:
        """Apply config and navigate to experiment selector. Override to customize."""
        self._apply_config()
        self._window.router.navigate_to("experiment_selector")

    def _apply_config(self) -> None:
        """Override to write form values back to session."""
        pass

    def on_enter(self, **kwargs) -> None:
        """Called when page is navigated to."""
        if self._window.session.chip_number is not None:
            chip_name = f"{self._window.session.chip_group}{self._window.session.chip_number}"
            self._subtitle_label.setText(f"Chip: {chip_name}  |  Plot: {self._window.session.plot_type}")

    # ── Form helpers ──

    def add_combo_row(self, label: str, items: Sequence[str], default: str = "") -> QComboBox:
        """Add a labeled combo box to the form."""
        combo = QComboBox()
        combo.addItems(items)
        if default and default in items:
            combo.setCurrentText(default)
        self._form.addRow(label, combo)
        return combo

    def add_spin_row(self, label: str, min_val: int, max_val: int, default: int) -> QSpinBox:
        """Add a labeled integer spin box."""
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        self._form.addRow(label, spin)
        return spin

    def add_double_spin_row(
        self, label: str, min_val: float, max_val: float, default: float,
        decimals: int = 2, step: float = 0.01,
    ) -> QDoubleSpinBox:
        """Add a labeled float spin box."""
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(default)
        self._form.addRow(label, spin)
        return spin

    def add_check_row(self, label: str, default: bool = False) -> QCheckBox:
        """Add a labeled checkbox."""
        check = QCheckBox()
        check.setChecked(default)
        self._form.addRow(label, check)
        return check
