"""
Transconductance Configuration Page.

Configures calculation method, Savitzky-Golay window length, and polynomial order.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class TransconductanceConfigPage(BaseConfigPage):
    """Transconductance plot configuration form."""

    PAGE_TITLE = "Transconductance Configuration"
    PAGE_SUBTITLE = "Configure gm = dI/dVg derivative analysis"

    def _build_form(self) -> None:
        self._method_combo = self.add_combo_row(
            "Calculation method:", ["gradient", "savgol"], "gradient"
        )
        self._window_spin = self.add_spin_row(
            "Window length (savgol):", 3, 51, 9
        )
        self._polyorder_spin = self.add_spin_row(
            "Polynomial order (savgol):", 1, 10, 3
        )

    def _apply_config(self) -> None:
        s = self._window.session
        s.method = self._method_combo.currentText()
        s.window_length = self._window_spin.value()
        # Ensure window_length is odd
        if s.window_length % 2 == 0:
            s.window_length += 1
        s.polyorder = self._polyorder_spin.value()

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        s = self._window.session
        self._method_combo.setCurrentText(s.method)
        self._window_spin.setValue(s.window_length)
        self._polyorder_spin.setValue(s.polyorder)
