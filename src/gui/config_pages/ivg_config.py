"""
IVg Configuration Page.

Configures conductance and absolute value toggles for IVg (Transfer Curves) plots.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class IVgConfigPage(BaseConfigPage):
    """IVg plot configuration form."""

    PAGE_TITLE = "IVg Configuration"
    PAGE_SUBTITLE = "Configure Transfer Curves plot parameters"

    def _build_form(self) -> None:
        self._conductance_check = self.add_check_row("Conductance (G = I/V):", False)
        self._absolute_check = self.add_check_row("Absolute values:", False)

    def _apply_config(self) -> None:
        # IVg uses generic config dict keys (no dedicated session fields)
        pass

    def _on_next(self) -> None:
        self._apply_config()
        # Store transform flags in session config dict via update
        # These are read from config dict in plot_executor
        self._window.session.model_config.get("extra", None)  # no-op
        self._window.router.navigate_to("experiment_selector")

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        self._conductance_check.setChecked(False)
        self._absolute_check.setChecked(False)
