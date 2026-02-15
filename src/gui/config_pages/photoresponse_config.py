"""
Photoresponse Analysis Configuration Page.

Configures mode, filters, and normalization for photoresponse plots.
Requires enriched chip history.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QDoubleSpinBox, QSpinBox
from src.gui.config_pages.base_config import BaseConfigPage

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PhotoresponseConfigPage(BaseConfigPage):
    """Photoresponse analysis plot configuration form."""

    PAGE_TITLE = "Photoresponse Configuration"
    PAGE_SUBTITLE = "Configure photoresponse analysis plot"

    def _build_form(self) -> None:
        note = QLabel("Requires enriched chip history (run 'biotite enrich-history')")
        note.setObjectName("warning-label")
        self._form.addRow("", note)

        self._mode_combo = self.add_combo_row(
            "Plot mode:", ["power", "wavelength", "gate_voltage", "time"], "power"
        )

        # Optional filters (0 = no filter)
        self._filter_vg_spin = self.add_double_spin_row(
            "Filter by Vg (V):", -100.0, 100.0, 0.0, decimals=1, step=0.5
        )
        self._filter_wl_spin = self.add_spin_row(
            "Filter by wavelength (nm):", 0, 2000, 0
        )
        self._normalize_check = self.add_check_row(
            "Normalize to dark current:", False
        )

    def _apply_config(self) -> None:
        s = self._window.session
        s.photoresponse_mode = self._mode_combo.currentText()

        vg_val = self._filter_vg_spin.value()
        s.photoresponse_filter_vg = vg_val if vg_val != 0.0 else None

        wl_val = self._filter_wl_spin.value()
        s.photoresponse_filter_wl = wl_val if wl_val != 0 else None

        s.photoresponse_normalize = self._normalize_check.isChecked()

    def _on_next(self) -> None:
        """Photoresponse plots don't use experiment selector."""
        self._apply_config()
        self._window.session.seq_numbers = []
        self._window.router.navigate_to("preview")

    def on_enter(self, **kwargs) -> None:
        super().on_enter(**kwargs)
        s = self._window.session
        self._mode_combo.setCurrentText(s.photoresponse_mode)
        self._filter_vg_spin.setValue(s.photoresponse_filter_vg or 0.0)
        self._filter_wl_spin.setValue(s.photoresponse_filter_wl or 0)
        self._normalize_check.setChecked(s.photoresponse_normalize)
