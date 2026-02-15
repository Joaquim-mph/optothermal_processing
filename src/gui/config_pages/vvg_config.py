"""
VVg Configuration Page.

Configures resistance, absolute value, and plotting mode for VVg plots.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class VVgConfigPage(BaseConfigPage):
    """VVg plot configuration form."""

    PAGE_TITLE = "VVg Configuration"
    PAGE_SUBTITLE = "Configure Drain-Source vs Gate plot parameters"

    def _build_form(self) -> None:
        self._mode_combo = self.add_combo_row(
            "Plotting mode:", ["standard", "normalized", "derivative"], "standard"
        )
        self._resistance_check = self.add_check_row("Resistance (R = V/I):", False)
        self._absolute_check = self.add_check_row("Absolute values:", False)

    def _apply_config(self) -> None:
        self._window.session.vvg_vt_mode = self._mode_combo.currentText()

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        self._mode_combo.setCurrentText(self._window.session.vvg_vt_mode)
        self._resistance_check.setChecked(False)
        self._absolute_check.setChecked(False)
