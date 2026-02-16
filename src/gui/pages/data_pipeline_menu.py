"""
Data Pipeline Control Center.

Sectioned page with collapsible groups for running individual pipeline
steps (staging, histories, metrics, enrichment) with configurable options.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QCheckBox, QSpinBox, QLineEdit, QPlainTextEdit,
)

from src.gui.workers import PipelineStepWorker

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class _CollapsibleSection(QWidget):
    """A collapsible section with a clickable header and content area."""

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self._header = QPushButton(f"  {title}")
        self._header.setObjectName("section-header-btn")
        self._header.setCheckable(True)
        self._header.setChecked(True)
        self._header.setStyleSheet(
            "QPushButton#section-header-btn {"
            "  text-align: left; font-size: 15px; font-weight: bold;"
            "  padding: 10px 12px; border: none; border-radius: 6px;"
            "}"
        )
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # Description
        desc = QLabel(description)
        desc.setObjectName("page-subtitle")
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 0 12px 4px 12px; font-size: 12px;")
        layout.addWidget(desc)

        # Content container
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 4, 12, 12)
        self._content_layout.setSpacing(8)
        layout.addWidget(self._content)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def _toggle(self) -> None:
        self._content.setVisible(self._header.isChecked())


class DataPipelineMenuPage(QWidget):
    """Pipeline control center with sectioned operations."""

    # Info-only steps that show results in-page instead of navigating
    _INFO_STEPS = {"validate_manifest", "staging_stats"}

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._worker: PipelineStepWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Pipeline Control Center")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Run individual pipeline steps or the full pipeline")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Global workers setting
        workers_row = QHBoxLayout()
        workers_row.addWidget(QLabel("Parallel workers:"))
        self._workers = QSpinBox()
        self._workers.setRange(1, 32)
        self._workers.setValue(6)
        self._workers.setFixedWidth(70)
        workers_row.addWidget(self._workers)
        workers_row.addStretch()
        layout.addLayout(workers_row)

        # Scroll area for sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        self._sections_layout = QVBoxLayout(scroll_content)
        self._sections_layout.setContentsMargins(0, 0, 0, 0)
        self._sections_layout.setSpacing(16)

        self._build_full_pipeline_section()
        self._build_staging_section()
        self._build_history_section()
        self._build_metrics_section()
        self._build_enrichment_section()

        # Results panel (for info-only commands like validate/stats)
        self._results_panel = QPlainTextEdit()
        self._results_panel.setReadOnly(True)
        self._results_panel.setVisible(False)
        self._results_panel.setMaximumHeight(250)
        self._results_panel.setPlaceholderText("Results will appear here...")
        self._sections_layout.addWidget(self._results_panel)

        self._sections_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    # ── Section builders ──────────────────────────────────────────

    def _build_full_pipeline_section(self) -> None:
        section = _CollapsibleSection(
            "Full Pipeline",
            "Run all steps: stage -> histories -> metrics -> enrichment",
        )

        row1 = QHBoxLayout()
        self._fp_force = QCheckBox("Force overwrite")
        row1.addWidget(self._fp_force)
        self._fp_skip_metrics = QCheckBox("Skip metrics")
        row1.addWidget(self._fp_skip_metrics)
        self._fp_skip_enrichment = QCheckBox("Skip enrichment")
        row1.addWidget(self._fp_skip_enrichment)
        row1.addStretch()
        section.content_layout.addLayout(row1)

        btn = QPushButton("Run Full Pipeline")
        btn.setObjectName("primary-btn")
        btn.setFixedHeight(40)
        btn.clicked.connect(self._on_run_full_pipeline)
        section.content_layout.addWidget(btn)

        self._sections_layout.addWidget(section)

    def _build_staging_section(self) -> None:
        section = _CollapsibleSection(
            "Staging",
            "Stage raw CSVs to Parquet format with schema validation",
        )

        row = QHBoxLayout()
        self._stage_force = QCheckBox("Force")
        row.addWidget(self._stage_force)
        self._stage_strict = QCheckBox("Strict")
        row.addWidget(self._stage_strict)
        row.addStretch()
        section.content_layout.addLayout(row)

        btn_row = QHBoxLayout()
        stage_btn = QPushButton("Stage All")
        stage_btn.setObjectName("primary-btn")
        stage_btn.clicked.connect(self._on_stage_all)
        btn_row.addWidget(stage_btn)

        validate_btn = QPushButton("Validate Manifest")
        validate_btn.clicked.connect(self._on_validate_manifest)
        btn_row.addWidget(validate_btn)

        stats_btn = QPushButton("Staging Stats")
        stats_btn.clicked.connect(self._on_staging_stats)
        btn_row.addWidget(stats_btn)

        btn_row.addStretch()
        section.content_layout.addLayout(btn_row)

        self._sections_layout.addWidget(section)

    def _build_history_section(self) -> None:
        section = _CollapsibleSection(
            "Chip Histories",
            "Build per-chip history Parquets from the manifest",
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("Group filter:"))
        self._hist_group = QLineEdit()
        self._hist_group.setPlaceholderText("e.g. Alisson (blank = all)")
        self._hist_group.setFixedWidth(200)
        row.addWidget(self._hist_group)

        row.addSpacing(16)
        row.addWidget(QLabel("Min experiments:"))
        self._hist_min_exp = QSpinBox()
        self._hist_min_exp.setRange(1, 1000)
        self._hist_min_exp.setValue(1)
        self._hist_min_exp.setFixedWidth(70)
        row.addWidget(self._hist_min_exp)
        row.addStretch()
        section.content_layout.addLayout(row)

        btn = QPushButton("Build All Histories")
        btn.setObjectName("primary-btn")
        btn.clicked.connect(self._on_build_histories)
        section.content_layout.addWidget(btn)

        self._sections_layout.addWidget(section)

    def _build_metrics_section(self) -> None:
        section = _CollapsibleSection(
            "Derived Metrics",
            "Extract analytical metrics (CNP, photoresponse, relaxation, drift, sweep differences)",
        )

        row = QHBoxLayout()
        self._met_force = QCheckBox("Force re-extract")
        row.addWidget(self._met_force)
        row.addStretch()
        section.content_layout.addLayout(row)

        btn_row = QHBoxLayout()
        all_btn = QPushButton("All Metrics")
        all_btn.setObjectName("primary-btn")
        all_btn.clicked.connect(self._on_derive_all_metrics)
        btn_row.addWidget(all_btn)

        fit_btn = QPushButton("Fitting Metrics")
        fit_btn.clicked.connect(self._on_derive_fitting_metrics)
        btn_row.addWidget(fit_btn)

        sweep_btn = QPushButton("Consecutive Sweeps")
        sweep_btn.clicked.connect(self._on_derive_consecutive_sweeps)
        btn_row.addWidget(sweep_btn)

        btn_row.addStretch()
        section.content_layout.addLayout(btn_row)

        self._sections_layout.addWidget(section)

    def _build_enrichment_section(self) -> None:
        section = _CollapsibleSection(
            "Enrichment",
            "Join derived metrics and calibrations into chip histories",
        )

        row = QHBoxLayout()
        self._enrich_all = QCheckBox("All chips")
        self._enrich_all.setChecked(True)
        self._enrich_all.toggled.connect(self._on_enrich_all_toggled)
        row.addWidget(self._enrich_all)

        row.addSpacing(16)
        row.addWidget(QLabel("Chip #:"))
        self._enrich_chip = QSpinBox()
        self._enrich_chip.setRange(1, 999)
        self._enrich_chip.setValue(67)
        self._enrich_chip.setFixedWidth(70)
        self._enrich_chip.setEnabled(False)
        row.addWidget(self._enrich_chip)
        row.addStretch()
        section.content_layout.addLayout(row)

        btn = QPushButton("Enrich Histories")
        btn.setObjectName("primary-btn")
        btn.clicked.connect(self._on_enrich_history)
        section.content_layout.addWidget(btn)

        self._sections_layout.addWidget(section)

    # ── UI callbacks ──────────────────────────────────────────────

    def _on_enrich_all_toggled(self, checked: bool) -> None:
        self._enrich_chip.setEnabled(not checked)

    # ── Step launchers ────────────────────────────────────────────

    def _on_run_full_pipeline(self) -> None:
        options = {
            "force": self._fp_force.isChecked(),
            "workers": self._workers.value(),
            "skip_metrics": self._fp_skip_metrics.isChecked(),
            "skip_enrichment": self._fp_skip_enrichment.isChecked(),
        }
        self._window.router.navigate_to(
            "process_confirmation",
            step_name="full_pipeline",
            options=options,
        )

    def _on_stage_all(self) -> None:
        options = {
            "force": self._stage_force.isChecked(),
            "strict": self._stage_strict.isChecked(),
            "workers": self._workers.value(),
        }
        self._window.router.navigate_to(
            "process_confirmation",
            step_name="stage_all",
            options=options,
        )

    def _on_build_histories(self) -> None:
        options = {
            "chip_group": self._hist_group.text().strip(),
            "min_experiments": self._hist_min_exp.value(),
        }
        self._window.router.navigate_to(
            "process_confirmation",
            step_name="build_histories",
            options=options,
        )

    def _on_derive_all_metrics(self) -> None:
        options = {
            "force": self._met_force.isChecked(),
            "workers": self._workers.value(),
        }
        self._window.router.navigate_to(
            "process_confirmation",
            step_name="derive_all_metrics",
            options=options,
        )

    def _on_derive_fitting_metrics(self) -> None:
        options = {
            "force": self._met_force.isChecked(),
            "workers": self._workers.value(),
        }
        self._window.router.navigate_to(
            "process_confirmation",
            step_name="derive_fitting_metrics",
            options=options,
        )

    def _on_derive_consecutive_sweeps(self) -> None:
        options = {
            "force": self._met_force.isChecked(),
            "workers": self._workers.value(),
        }
        self._window.router.navigate_to(
            "process_confirmation",
            step_name="derive_consecutive_sweeps",
            options=options,
        )

    def _on_enrich_history(self) -> None:
        options = {
            "all_chips": self._enrich_all.isChecked(),
            "chip_number": self._enrich_chip.value(),
        }
        self._window.router.navigate_to(
            "process_confirmation",
            step_name="enrich_history",
            options=options,
        )

    def _on_validate_manifest(self) -> None:
        self._run_info_step("validate_manifest")

    def _on_staging_stats(self) -> None:
        self._run_info_step("staging_stats")

    # ── Info step runner (results in-page) ────────────────────────

    def _run_info_step(self, step_name: str) -> None:
        """Run a quick info command and show results in the results panel."""
        self._results_panel.setVisible(True)
        self._results_panel.setPlainText(f"Running {step_name}...")

        self._worker = PipelineStepWorker(step_name)
        self._worker.log_output.connect(self._on_info_output)
        self._worker.finished.connect(self._on_info_finished)
        self._worker.error.connect(self._on_info_error)
        self._worker.start()

    def _on_info_output(self, text: str) -> None:
        self._results_panel.setPlainText(text)

    def _on_info_finished(self, result: dict) -> None:
        if "output" in result:
            self._results_panel.setPlainText(result["output"])
        else:
            self._results_panel.setPlainText(result.get("summary", "Done."))

    def _on_info_error(self, error_msg: str, error_type: str, tb: str) -> None:
        self._results_panel.setPlainText(f"ERROR ({error_type}): {error_msg}\n\n{tb}")
