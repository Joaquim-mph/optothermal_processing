"""
Process Confirmation Page.

Step-specific confirmation dialog before running pipeline operations.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

if TYPE_CHECKING:
    from src.gui.app import MainWindow


# Step-specific confirmation details
_STEP_INFO: dict[str, dict[str, str]] = {
    "full_pipeline": {
        "title": "Run Full Pipeline?",
        "description": (
            "This will run the complete data processing pipeline:\n\n"
            "  Step 1: Stage raw CSVs -> Parquet (schema-validated)\n"
            "  Step 2: Build chip histories from manifest\n"
            "  Step 3: Extract derived metrics (CNP, photoresponse, power)\n"
            "  Step 4: Enrich histories (join calibrations + metrics)\n\n"
            "Data paths:\n"
            "  Raw:      data/01_raw/\n"
            "  Staged:   data/02_stage/raw_measurements/\n"
            "  Histories: data/02_stage/chip_histories/\n"
            "  Derived:  data/03_derived/_metrics/\n"
            "  Enriched: data/03_derived/chip_histories_enriched/"
        ),
        "warning": "This may take several minutes for large datasets.",
    },
    "stage_all": {
        "title": "Stage All CSVs?",
        "description": (
            "This will stage all raw CSV files from data/01_raw/ to Parquet\n"
            "format in data/02_stage/raw_measurements/.\n\n"
            "Each CSV is parsed, schema-validated against config/procedures.yml,\n"
            "and stored as a Parquet file. A manifest is built/updated."
        ),
        "warning": "Staging large datasets may take a few minutes.",
    },
    "build_histories": {
        "title": "Build Chip Histories?",
        "description": (
            "This will generate per-chip history Parquet files from the\n"
            "manifest in data/02_stage/raw_measurements/_manifest/.\n\n"
            "Each chip gets a history file with sequential experiment numbers\n"
            "and references to staged measurement Parquet files."
        ),
        "warning": "",
    },
    "derive_all_metrics": {
        "title": "Derive All Metrics?",
        "description": (
            "This will extract all analytical metrics from staged measurements:\n\n"
            "  - CNP (Charge Neutrality Point) from IVg/VVg sweeps\n"
            "  - Photoresponse (delta-I/delta-V) from It/Vt time-series\n\n"
            "Results are saved to data/03_derived/_metrics/metrics.parquet."
        ),
        "warning": "This may take a few minutes depending on dataset size.",
    },
    "derive_fitting_metrics": {
        "title": "Derive Fitting Metrics?",
        "description": (
            "This will extract Numba-accelerated fitting metrics:\n\n"
            "  - ITS Relaxation time constants (exponential fits)\n"
            "  - Three-phase fits (pre-dark, light, post-dark)\n"
            "  - Linear drift rates from time-series\n\n"
            "These are computationally intensive and use Numba JIT compilation."
        ),
        "warning": "First run may be slow due to Numba JIT compilation.",
    },
    "derive_consecutive_sweeps": {
        "title": "Derive Consecutive Sweep Differences?",
        "description": (
            "This will extract pairwise differences between consecutive\n"
            "IVg/VVg sweeps on the same chip.\n\n"
            "Uses Numba-accelerated linear interpolation for 8x speedup.\n"
            "Results include delta-CNP, delta-current, and hysteresis metrics."
        ),
        "warning": "",
    },
    "enrich_history": {
        "title": "Enrich Chip Histories?",
        "description": (
            "This will join derived metrics and calibration data into\n"
            "chip history files.\n\n"
            "Enriched histories are saved to:\n"
            "  data/03_derived/chip_histories_enriched/"
        ),
        "warning": "",
    },
}


class ProcessConfirmationPage(QWidget):
    """Step-specific confirmation before pipeline execution."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._step_name = "full_pipeline"
        self._options: dict = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("Run Full Pipeline?")
        self._title.setObjectName("page-title")
        layout.addWidget(self._title)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        layout.addWidget(self._desc)

        self._options_label = QLabel("")
        self._options_label.setObjectName("info-label")
        self._options_label.setWordWrap(True)
        layout.addWidget(self._options_label)

        self._warning = QLabel("")
        self._warning.setObjectName("warning-label")
        layout.addWidget(self._warning)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._window.router.go_back)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()

        self._confirm_btn = QPushButton("Start Processing")
        self._confirm_btn.setObjectName("primary-btn")
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self._confirm_btn)

        layout.addLayout(btn_row)

    def on_enter(self, step_name: str = "full_pipeline", options: dict | None = None, **kwargs) -> None:
        self._step_name = step_name
        self._options = options or {}

        info = _STEP_INFO.get(step_name, _STEP_INFO["full_pipeline"])
        self._title.setText(info["title"])
        self._desc.setText(info["description"])
        self._warning.setText(info["warning"])
        self._warning.setVisible(bool(info["warning"]))

        # Show options summary
        opts_text = self._format_options()
        self._options_label.setText(opts_text)
        self._options_label.setVisible(bool(opts_text))

    def _format_options(self) -> str:
        """Format the options dict into a readable string."""
        if not self._options:
            return ""

        parts = []
        for key, val in self._options.items():
            if isinstance(val, bool):
                if val:
                    parts.append(f"  {key.replace('_', ' ').title()}: Yes")
            elif val:
                parts.append(f"  {key.replace('_', ' ').title()}: {val}")

        if not parts:
            return ""
        return "Options:\n" + "\n".join(parts)

    def _on_confirm(self) -> None:
        self._window.router.navigate_to(
            "pipeline_loading",
            step_name=self._step_name,
            options=self._options,
        )
