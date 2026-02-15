"""
Laser Calibration Configuration Page.

Configures power unit, wavelength grouping, markers, and comparison mode.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class LaserCalibrationConfigPage(BaseConfigPage):
    """Laser calibration plot configuration form."""

    PAGE_TITLE = "Laser Calibration Configuration"
    PAGE_SUBTITLE = "Configure laser power vs control voltage calibration plot"

    def _build_form(self) -> None:
        self._power_unit_combo = self.add_combo_row(
            "Power unit:", ["uW", "mW", "W", "nW"], "uW"
        )
        self._group_by_wl_check = self.add_check_row(
            "Group by wavelength:", True
        )
        self._show_markers_check = self.add_check_row(
            "Show markers:", False
        )
        self._comparison_check = self.add_check_row(
            "Comparison mode:", False
        )

    def _apply_config(self) -> None:
        # These are stored in the config dict passed to plot_executor
        pass

    def _on_next(self) -> None:
        self._apply_config()
        self._window.router.navigate_to("experiment_selector")

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        self._power_unit_combo.setCurrentText("uW")
        self._group_by_wl_check.setChecked(True)
        self._show_markers_check.setChecked(False)
        self._comparison_check.setChecked(False)
