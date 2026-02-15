"""
CNP Time Evolution Configuration Page.

Configures metric selection and illumination display for CNP plots.
Requires enriched chip history.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel
from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class CNPConfigPage(BaseConfigPage):
    """CNP time evolution plot configuration form."""

    PAGE_TITLE = "CNP Configuration"
    PAGE_SUBTITLE = "Configure Charge Neutrality Point time evolution plot"

    def _build_form(self) -> None:
        note = QLabel("Requires enriched chip history (run 'biotite enrich-history')")
        note.setObjectName("warning-label")
        self._form.addRow("", note)

        self._metric_combo = self.add_combo_row(
            "CNP metric:", ["cnp_voltage", "cnp_current", "mobility"], "cnp_voltage"
        )
        self._illumination_check = self.add_check_row(
            "Show illumination periods:", True
        )

    def _apply_config(self) -> None:
        s = self._window.session
        s.cnp_metric = self._metric_combo.currentText()
        s.cnp_show_illumination = self._illumination_check.isChecked()

    def _on_next(self) -> None:
        """CNP plots don't use experiment selector -- go straight to generation."""
        self._apply_config()
        # CNP uses the full enriched history, no experiment selection needed
        self._window.session.seq_numbers = []
        self._window.router.navigate_to("preview")

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        s = self._window.session
        self._metric_combo.setCurrentText(s.cnp_metric)
        self._illumination_check.setChecked(s.cnp_show_illumination)
