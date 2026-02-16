"""
Data Pipeline Control Center.

Card-based dashboard for running individual pipeline steps. Each operation
runs inline — progress, success, and errors are shown directly inside the
card that triggered them, so the user never leaves the page.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QCheckBox, QSpinBox, QPlainTextEdit,
    QGridLayout, QSizePolicy, QGraphicsDropShadowEffect,
    QProgressBar, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from src.gui.workers import PipelineStepWorker, PipelineWorker

if TYPE_CHECKING:
    from src.gui.app import MainWindow


# ── Accent colors per category ────────────────────────────────────
_ACCENTS = {
    "pipeline": "#7aa2f7",   # blue  — full pipeline
    "staging":  "#9ece6a",   # green — staging / CSV
    "history":  "#bb9af7",   # magenta — histories
    "metrics":  "#ff9e64",   # orange — derived metrics
    "enrich":   "#7dcfff",   # cyan — enrichment
    "info":     "#565f89",   # gray — info-only commands
}


def _make_shadow(parent: QWidget | None = None) -> QGraphicsDropShadowEffect:
    shadow = QGraphicsDropShadowEffect(parent)
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 60))
    return shadow


# ── Card states ───────────────────────────────────────────────────

class _CardState:
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class _PipelineCard(QFrame):
    """
    Pipeline step card with inline progress feedback.

    Layout:
    ┌─accent─┬──────────────────────────────────────┐
    │ 5px    │  Title                    [Run btn]  │
    │ color  │  Description text                    │
    │ bar    │  (options row — if has settings)      │
    │        │  [progress bar]  status text          │
    │        │  (results panel — expandable)         │
    └────────┴──────────────────────────────────────┘
    """

    def __init__(
        self,
        title: str,
        description: str,
        accent_color: str,
        run_label: str = "Run",
        hero: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._hero = hero
        self._run_label = run_label
        self._state = _CardState.IDLE
        self._accent_color = accent_color

        self.setObjectName("pipeline-card-hero" if hero else "pipeline-card")
        self.setGraphicsEffect(_make_shadow(self))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Colored accent bar
        self._accent = QLabel()
        self._accent.setObjectName("card-accent")
        self._accent.setFixedWidth(5)
        self._accent.setStyleSheet(
            f"background-color: {accent_color}; border-radius: 4px 0 0 4px;"
        )
        root.addWidget(self._accent)

        # Card body
        body = QVBoxLayout()
        pad = (16, 14, 16, 14) if hero else (12, 10, 12, 10)
        body.setContentsMargins(*pad)
        body.setSpacing(4 if not hero else 6)

        # Row 1: title + run button
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        lbl = QLabel(title)
        lbl.setObjectName("card-title-hero" if hero else "card-title")
        top_row.addWidget(lbl)
        top_row.addStretch()

        self._run_btn = QPushButton(run_label)
        self._run_btn.setObjectName("card-run-btn")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if hero:
            self._run_btn.setFixedHeight(34)
        top_row.addWidget(self._run_btn)
        body.addLayout(top_row)

        # Row 2: description
        self._desc = QLabel(description)
        self._desc.setObjectName("card-desc")
        self._desc.setWordWrap(True)
        body.addWidget(self._desc)

        # Row 3: options (hidden by default)
        self._options_widget = QWidget()
        self._options_widget.setObjectName("card-options")
        self._options_layout = QHBoxLayout(self._options_widget)
        self._options_layout.setContentsMargins(8, 6, 8, 6)
        self._options_layout.setSpacing(12)
        self._options_widget.setVisible(False)
        body.addWidget(self._options_widget)

        # Row 4: inline progress area (hidden until running)
        self._progress_widget = QWidget()
        self._progress_widget.setVisible(False)
        progress_layout = QVBoxLayout(self._progress_widget)
        progress_layout.setContentsMargins(0, 4, 0, 0)
        progress_layout.setSpacing(3)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("card-progress")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        progress_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setObjectName("card-status")
        progress_layout.addWidget(self._status_label)

        body.addWidget(self._progress_widget)

        # Row 5: results panel (for text output / errors)
        self._results = QPlainTextEdit()
        self._results.setReadOnly(True)
        self._results.setVisible(False)
        self._results.setMaximumHeight(180)
        body.addWidget(self._results)

        root.addLayout(body, stretch=1)

    # ── Public API ────────────────────────────────────────────────

    @property
    def run_button(self) -> QPushButton:
        return self._run_btn

    @property
    def options_layout(self) -> QHBoxLayout:
        return self._options_layout

    def show_options(self) -> None:
        self._options_widget.setVisible(True)

    # ── State transitions ─────────────────────────────────────────

    def set_running(self) -> None:
        """Transition to running state."""
        self._state = _CardState.RUNNING
        self._run_btn.setText("Running...")
        self._run_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet("")  # reset to default blue
        self._status_label.setText("Starting...")
        self._status_label.setObjectName("card-status")
        self._status_label.setStyle(self._status_label.style())  # force refresh
        self._progress_widget.setVisible(True)
        self._results.setVisible(False)

    def set_progress(self, percent: float, status: str) -> None:
        """Update progress bar and status text."""
        self._progress_bar.setValue(int(percent))
        self._status_label.setText(status)

    def set_success(self, summary: str) -> None:
        """Transition to success state."""
        self._state = _CardState.SUCCESS
        self._run_btn.setText(self._run_label)
        self._run_btn.setEnabled(True)
        self._progress_bar.setValue(100)
        self._progress_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #9ece6a; border-radius: 3px; }"
        )
        self._status_label.setText(summary)
        self._status_label.setObjectName("card-status-success")
        self._status_label.setStyle(self._status_label.style())

    def set_error(self, error_msg: str, traceback_text: str = "") -> None:
        """Transition to error state with optional traceback."""
        self._state = _CardState.ERROR
        self._run_btn.setText(self._run_label)
        self._run_btn.setEnabled(True)
        self._progress_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #f7768e; border-radius: 3px; }"
        )
        self._status_label.setText(error_msg)
        self._status_label.setObjectName("card-status-error")
        self._status_label.setStyle(self._status_label.style())
        if traceback_text:
            self._results.setPlainText(traceback_text)
            self._results.setVisible(True)

    def show_results(self, text: str) -> None:
        """Show text results (for info-only cards)."""
        self._results.setVisible(True)
        self._results.setPlainText(text)

    def reset(self) -> None:
        """Return to idle state."""
        self._state = _CardState.IDLE
        self._run_btn.setText(self._run_label)
        self._run_btn.setEnabled(True)
        self._progress_widget.setVisible(False)
        self._results.setVisible(False)
        self._progress_bar.setStyleSheet("")


class DataPipelineMenuPage(QWidget):
    """Card-based pipeline control center with inline progress."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        # Track active workers keyed by card to allow multiple concurrent steps
        self._active_workers: dict[_PipelineCard, PipelineStepWorker | PipelineWorker] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(10)

        title = QLabel("Process Data")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Run the full pipeline or individual steps")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        # Global settings bar
        settings_bar = QHBoxLayout()
        settings_bar.setSpacing(16)

        wlabel = QLabel("Workers:")
        wlabel.setObjectName("settings-bar-label")
        settings_bar.addWidget(wlabel)
        self._workers = QSpinBox()
        self._workers.setRange(1, 32)
        self._workers.setValue(6)
        self._workers.setFixedWidth(60)
        self._workers.setToolTip("Number of parallel worker threads")
        settings_bar.addWidget(self._workers)

        self._global_force = QCheckBox("Force overwrite")
        self._global_force.setToolTip("Re-process files that already exist")
        settings_bar.addWidget(self._global_force)

        settings_bar.addStretch()
        layout.addLayout(settings_bar)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        self._content = QVBoxLayout(scroll_content)
        self._content.setContentsMargins(0, 8, 0, 0)
        self._content.setSpacing(12)

        self._build_hero_card()
        self._build_step_grid()
        self._content.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Navigation
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    # ── Card builders ─────────────────────────────────────────────

    def _build_hero_card(self) -> None:
        self._hero_card = _PipelineCard(
            title="Full Pipeline",
            description=(
                "Run all steps in sequence: stage raw CSVs, build chip histories, "
                "extract derived metrics, and enrich histories with calibrations."
            ),
            accent_color=_ACCENTS["pipeline"],
            run_label="Run Full Pipeline",
            hero=True,
        )
        self._hero_card.run_button.clicked.connect(self._on_run_full_pipeline)

        self._fp_skip_metrics = QCheckBox("Skip metrics")
        self._hero_card.options_layout.addWidget(self._fp_skip_metrics)
        self._fp_skip_enrichment = QCheckBox("Skip enrichment")
        self._hero_card.options_layout.addWidget(self._fp_skip_enrichment)
        self._hero_card.options_layout.addStretch()
        self._hero_card.show_options()

        self._content.addWidget(self._hero_card)

    def _build_step_grid(self) -> None:
        steps_label = QLabel("Individual Steps")
        steps_label.setObjectName("section-header")
        self._content.addWidget(steps_label)

        grid = QGridLayout()
        grid.setSpacing(12)

        # Row 0: Staging + Histories
        self._stage_card = self._make_card(
            "Stage All",
            "Parse raw CSVs and stage to Parquet with schema validation",
            _ACCENTS["staging"], "Stage",
        )
        self._stage_strict = QCheckBox("Strict")
        self._stage_card.options_layout.addWidget(self._stage_strict)
        self._stage_card.options_layout.addStretch()
        self._stage_card.show_options()
        self._stage_card.run_button.clicked.connect(self._on_stage_all)
        grid.addWidget(self._stage_card, 0, 0)

        self._history_card = self._make_card(
            "Build Histories",
            "Generate per-chip history Parquets from the manifest",
            _ACCENTS["history"], "Build",
        )
        self._history_card.run_button.clicked.connect(self._on_build_histories)
        grid.addWidget(self._history_card, 0, 1)

        # Row 1: Metrics
        self._all_metrics_card = self._make_card(
            "All Metrics",
            "Extract CNP, photoresponse, and all standard metrics",
            _ACCENTS["metrics"], "Extract",
        )
        self._all_metrics_card.run_button.clicked.connect(self._on_derive_all_metrics)
        grid.addWidget(self._all_metrics_card, 1, 0)

        self._fitting_card = self._make_card(
            "Fitting Metrics",
            "Numba-accelerated relaxation, 3-phase fits, drift rates",
            _ACCENTS["metrics"], "Extract",
        )
        self._fitting_card.run_button.clicked.connect(self._on_derive_fitting_metrics)
        grid.addWidget(self._fitting_card, 1, 1)

        # Row 2: Sweeps + Enrichment
        self._sweeps_card = self._make_card(
            "Consecutive Sweeps",
            "Pairwise IVg/VVg sweep differences with Numba interpolation",
            _ACCENTS["metrics"], "Extract",
        )
        self._sweeps_card.run_button.clicked.connect(self._on_derive_consecutive_sweeps)
        grid.addWidget(self._sweeps_card, 2, 0)

        self._enrich_card = self._make_card(
            "Enrich Histories",
            "Join derived metrics and calibrations into chip histories",
            _ACCENTS["enrich"], "Enrich",
        )
        self._enrich_card.run_button.clicked.connect(self._on_enrich_history)
        grid.addWidget(self._enrich_card, 2, 1)

        self._content.addLayout(grid)

        # Diagnostics section
        info_label = QLabel("Diagnostics")
        info_label.setObjectName("section-header")
        self._content.addWidget(info_label)

        info_grid = QGridLayout()
        info_grid.setSpacing(12)

        self._validate_card = self._make_card(
            "Validate Manifest",
            "Check schema, duplicates, field completeness, and date range",
            _ACCENTS["info"], "Validate",
        )
        self._validate_card.run_button.clicked.connect(self._on_validate_manifest)
        info_grid.addWidget(self._validate_card, 0, 0)

        self._stats_card = self._make_card(
            "Staging Stats",
            "Directory sizes, file counts, and manifest summary",
            _ACCENTS["info"], "Show Stats",
        )
        self._stats_card.run_button.clicked.connect(self._on_staging_stats)
        info_grid.addWidget(self._stats_card, 0, 1)

        self._content.addLayout(info_grid)

    def _make_card(self, title: str, desc: str, accent: str, label: str) -> _PipelineCard:
        return _PipelineCard(title=title, description=desc, accent_color=accent, run_label=label)

    # ── Force-overwrite confirmation ──────────────────────────────

    def _confirm_force(self) -> bool:
        """Show confirmation dialog when force-overwrite is on. Returns True to proceed."""
        if not self._global_force.isChecked():
            return True
        reply = QMessageBox.question(
            self,
            "Force overwrite?",
            "Force is enabled — this will re-process all files,\n"
            "overwriting existing staged data and metrics.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    # ── Inline step execution ─────────────────────────────────────

    def _run_step(self, card: _PipelineCard, step_name: str, options: dict) -> None:
        """Run a pipeline step with inline progress in the card."""
        if card in self._active_workers:
            return  # already running

        if not self._confirm_force():
            return

        card.set_running()

        if step_name == "full_pipeline":
            worker = PipelineWorker()
        else:
            worker = PipelineStepWorker(step_name, options)

        self._active_workers[card] = worker

        worker.progress.connect(lambda pct, msg, c=card: c.set_progress(pct, msg))
        worker.finished.connect(lambda result, c=card: self._on_step_done(c, result))
        worker.error.connect(lambda msg, tp, tb, c=card: self._on_step_error(c, msg, tp, tb))

        # For info steps, also wire log_output
        if isinstance(worker, PipelineStepWorker):
            worker.log_output.connect(lambda text, c=card: c.show_results(text))

        worker.start()

    def _on_step_done(self, card: _PipelineCard, result: dict) -> None:
        self._active_workers.pop(card, None)
        elapsed = result.get("elapsed", 0)
        summary = result.get("summary", "Done")
        card.set_success(f"{summary}  ({elapsed:.1f}s)")

        # For full pipeline, show detailed stats
        if "files_processed" in result and "histories" in result:
            card.set_success(
                f"Staged {result.get('files_processed', 0)} files, "
                f"{result.get('histories', 0)} histories, "
                f"{result.get('total_chips', 0)} chips  "
                f"({elapsed:.1f}s)"
            )

        # For info steps with text output, show it
        if "output" in result:
            card.show_results(result["output"])

    def _on_step_error(self, card: _PipelineCard, msg: str, tp: str, tb: str) -> None:
        self._active_workers.pop(card, None)
        card.set_error(f"{tp}: {msg}", tb)

    # ── Button handlers ───────────────────────────────────────────

    def _on_run_full_pipeline(self) -> None:
        self._run_step(self._hero_card, "full_pipeline", {
            "force": self._global_force.isChecked(),
            "workers": self._workers.value(),
            "skip_metrics": self._fp_skip_metrics.isChecked(),
            "skip_enrichment": self._fp_skip_enrichment.isChecked(),
        })

    def _on_stage_all(self) -> None:
        self._run_step(self._stage_card, "stage_all", {
            "force": self._global_force.isChecked(),
            "strict": self._stage_strict.isChecked(),
            "workers": self._workers.value(),
        })

    def _on_build_histories(self) -> None:
        self._run_step(self._history_card, "build_histories", {})

    def _on_derive_all_metrics(self) -> None:
        self._run_step(self._all_metrics_card, "derive_all_metrics", {
            "force": self._global_force.isChecked(),
            "workers": self._workers.value(),
        })

    def _on_derive_fitting_metrics(self) -> None:
        self._run_step(self._fitting_card, "derive_fitting_metrics", {
            "force": self._global_force.isChecked(),
            "workers": self._workers.value(),
        })

    def _on_derive_consecutive_sweeps(self) -> None:
        self._run_step(self._sweeps_card, "derive_consecutive_sweeps", {
            "force": self._global_force.isChecked(),
            "workers": self._workers.value(),
        })

    def _on_enrich_history(self) -> None:
        self._run_step(self._enrich_card, "enrich_history", {"all_chips": True})

    def _on_validate_manifest(self) -> None:
        self._run_step(self._validate_card, "validate_manifest", {})

    def _on_staging_stats(self) -> None:
        self._run_step(self._stats_card, "staging_stats", {})
