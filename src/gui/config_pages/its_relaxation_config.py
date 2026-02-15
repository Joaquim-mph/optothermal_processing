"""
ITS Relaxation Fits Configuration Page.

Configures relaxation fit visualization parameters.
Requires derived metrics (relaxation_time).
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel
from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class ITSRelaxationConfigPage(BaseConfigPage):
    """ITS relaxation fits plot configuration form."""

    PAGE_TITLE = "ITS Relaxation Configuration"
    PAGE_SUBTITLE = "Configure relaxation time fit visualization"

    def _build_form(self) -> None:
        note = QLabel("Requires derived metrics (run 'biotite derive-all-metrics')")
        note.setObjectName("warning-label")
        self._form.addRow("", note)

        self._dark_only_check = self.add_check_row(
            "Dark experiments only:", True
        )
        self._segment_combo = self.add_combo_row(
            "Fit segment:", ["both", "rise", "decay"], "both"
        )

    def _apply_config(self) -> None:
        # These are passed via config dict
        pass

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        self._dark_only_check.setChecked(True)
        self._segment_combo.setCurrentText("both")
