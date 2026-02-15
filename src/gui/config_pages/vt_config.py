"""
Vt Configuration Page.

Configures legend, baseline, resistance, and absolute value for Vt plots.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class VtConfigPage(BaseConfigPage):
    """Vt plot configuration form."""

    PAGE_TITLE = "Vt Configuration"
    PAGE_SUBTITLE = "Configure Voltage vs Time plot parameters"

    def _build_form(self) -> None:
        self._legend_combo = self.add_combo_row(
            "Legend grouping:", ["vg", "led_voltage", "wavelength"], "wavelength"
        )
        self._baseline_mode_combo = self.add_combo_row(
            "Baseline mode:", ["fixed", "auto", "none"], "fixed"
        )
        self._baseline_spin = self.add_double_spin_row(
            "Baseline time (s):", 0.0, 600.0, 60.0, decimals=1, step=5.0
        )
        self._baseline_divisor_spin = self.add_double_spin_row(
            "Auto baseline divisor:", 1.0, 10.0, 2.0, decimals=1, step=0.5
        )
        self._start_time_spin = self.add_double_spin_row(
            "Plot start time (s):", 0.0, 300.0, 20.0, decimals=1, step=5.0
        )
        self._padding_spin = self.add_double_spin_row(
            "Y-axis padding:", 0.0, 1.0, 0.05, decimals=2, step=0.01
        )
        self._resistance_check = self.add_check_row("Resistance (R = V/I):", False)
        self._absolute_check = self.add_check_row("Absolute values:", False)

    def _apply_config(self) -> None:
        s = self._window.session
        s.legend_by = self._legend_combo.currentText()
        s.baseline_mode = self._baseline_mode_combo.currentText()
        s.baseline = self._baseline_spin.value()
        s.baseline_auto_divisor = self._baseline_divisor_spin.value()
        s.plot_start_time = self._start_time_spin.value()
        s.padding = self._padding_spin.value()

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        s = self._window.session
        self._legend_combo.setCurrentText("wavelength")  # Vt default
        self._baseline_mode_combo.setCurrentText(s.baseline_mode)
        self._baseline_spin.setValue(s.baseline or 60.0)
        self._baseline_divisor_spin.setValue(s.baseline_auto_divisor)
        self._start_time_spin.setValue(s.plot_start_time)
        self._padding_spin.setValue(s.padding)
        self._resistance_check.setChecked(False)
        self._absolute_check.setChecked(False)
