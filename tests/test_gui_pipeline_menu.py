"""
Tests for the Data Pipeline Menu page.

Verifies that every button in the Process Data side panel:
- Creates the correct worker type with the expected step name and options
- Puts the card into running state
- Handles success callbacks (card shows success)
- Handles error callbacks (card shows error)
- Passes global settings (workers, force) correctly
- Respects per-card options (strict, skip_metrics, etc.)
"""

import os
import sys
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    from src.gui.theme import STYLESHEET

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setStyleSheet(STYLESHEET)
    yield app


@pytest.fixture
def main_window(qapp):
    from src.gui.app import MainWindow
    window = MainWindow()
    yield window
    window.close()


@pytest.fixture
def page(main_window):
    """Navigate to the pipeline menu and return the page widget."""
    main_window.router.navigate_to("data_pipeline_menu")
    p = main_window.stack.currentWidget()
    # Reset state between tests
    p._active_workers.clear()
    p._global_force.setChecked(False)
    p._workers.setValue(6)
    p._stage_strict.setChecked(False)
    p._fp_skip_metrics.setChecked(False)
    p._fp_skip_enrichment.setChecked(False)
    yield p


# ── Fake worker that records calls without starting a QThread ──────


class FakeSignal:
    """Minimal fake signal that supports connect()."""

    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in self._slots:
            slot(*args)


class FakeWorker:
    """Fake worker that records creation args without starting a QThread."""

    instances = []

    def __init__(self, step_name=None, options=None, parent=None):
        self.step_name = step_name
        self.options = options or {}
        self.started = False
        self.progress = FakeSignal()
        self.completed = FakeSignal()
        self.error = FakeSignal()
        self.log_output = FakeSignal()
        FakeWorker.instances.append(self)

    def deleteLater(self):
        pass

    def start(self):
        self.started = True


class FakePipelineWorker(FakeWorker):
    """Fake for the full pipeline worker (no step_name arg)."""

    def __init__(self, parent=None):
        super().__init__(step_name="full_pipeline", parent=parent)


def _click_button(page, card_attr):
    """Click a card's Run button with mocked workers, return the captured FakeWorker."""
    FakeWorker.instances.clear()

    with patch("src.gui.pages.data_pipeline_menu.PipelineStepWorker", FakeWorker), \
         patch("src.gui.pages.data_pipeline_menu.PipelineWorker", FakePipelineWorker):
        page._active_workers.clear()
        card = getattr(page, card_attr)
        card.reset()
        card.run_button.click()

    if FakeWorker.instances:
        return FakeWorker.instances[-1]
    return None


# ═══════════════════════════════════════════════════════════════════
# Button → Worker mapping tests
# ═══════════════════════════════════════════════════════════════════


def test_full_pipeline_button(page):
    worker = _click_button(page, "_hero_card")
    assert worker is not None, "Full Pipeline button should create a worker"
    assert worker.step_name == "full_pipeline"
    assert worker.started


def test_stage_all_button(page):
    worker = _click_button(page, "_stage_card")
    assert worker is not None
    assert worker.step_name == "stage_all"
    assert "force" in worker.options
    assert "strict" in worker.options
    assert "workers" in worker.options
    assert worker.started


def test_build_histories_button(page):
    worker = _click_button(page, "_history_card")
    assert worker is not None
    assert worker.step_name == "build_histories"
    assert worker.started


def test_derive_all_metrics_button(page):
    worker = _click_button(page, "_all_metrics_card")
    assert worker is not None
    assert worker.step_name == "derive_all_metrics"
    assert "force" in worker.options
    assert "workers" in worker.options
    assert worker.started


def test_derive_fitting_metrics_button(page):
    worker = _click_button(page, "_fitting_card")
    assert worker is not None
    assert worker.step_name == "derive_fitting_metrics"
    assert "force" in worker.options
    assert "workers" in worker.options
    assert worker.started


def test_derive_consecutive_sweeps_button(page):
    worker = _click_button(page, "_sweeps_card")
    assert worker is not None
    assert worker.step_name == "derive_consecutive_sweeps"
    assert "force" in worker.options
    assert "workers" in worker.options
    assert worker.started


def test_enrich_history_button(page):
    worker = _click_button(page, "_enrich_card")
    assert worker is not None
    assert worker.step_name == "enrich_history"
    assert worker.options.get("all_chips") is True
    assert worker.started


def test_validate_manifest_button(page):
    worker = _click_button(page, "_validate_card")
    assert worker is not None
    assert worker.step_name == "validate_manifest"
    assert worker.started


def test_staging_stats_button(page):
    worker = _click_button(page, "_stats_card")
    assert worker is not None
    assert worker.step_name == "staging_stats"
    assert worker.started


# ═══════════════════════════════════════════════════════════════════
# Card state transition tests
# ═══════════════════════════════════════════════════════════════════


def test_card_enters_running_state(page):
    worker = _click_button(page, "_stage_card")
    card = page._stage_card
    assert card._state == "running"
    assert not card._run_btn.isEnabled()
    # Use isHidden() instead of isVisible() — offscreen windows never report visible
    assert not card._progress_widget.isHidden()


def test_success_callback_updates_card(page):
    card = page._history_card
    card.reset()

    page._on_step_done(card, {
        "elapsed": 2.5,
        "histories": 5,
        "total_chips": 3,
        "summary": "Generated 5 chip histories from 3 chips",
    })

    assert card._state == "success"
    assert card._run_btn.isEnabled()
    assert "5 chip histories" in card._status_label.text()


def test_error_callback_updates_card(page):
    card = page._all_metrics_card
    card.reset()

    page._on_step_error(
        card, "Manifest not found", "FileNotFoundError", "Traceback (most recent call last)..."
    )

    assert card._state == "error"
    assert card._run_btn.isEnabled()
    assert "FileNotFoundError" in card._status_label.text()
    assert not card._results.isHidden()
    assert "Traceback" in card._results.toPlainText()


def test_full_pipeline_success_shows_detailed_stats(page):
    card = page._hero_card
    card.reset()

    page._on_step_done(card, {
        "elapsed": 15.3,
        "files_processed": 100,
        "histories": 8,
        "total_chips": 4,
        "experiments": 90,
    })

    assert card._state == "success"
    status = card._status_label.text()
    assert "100 files" in status
    assert "8 histories" in status
    assert "4 chips" in status


def test_info_step_shows_output(page):
    card = page._validate_card
    card.reset()

    page._on_step_done(card, {
        "elapsed": 0.5,
        "summary": "Manifest validated: 90 OK",
        "output": "Manifest: data/02_stage/...\nTotal rows: 90\nOK: 90  Errors: 0",
    })

    assert card._state == "success"
    assert not card._results.isHidden()
    assert "Total rows: 90" in card._results.toPlainText()


# ═══════════════════════════════════════════════════════════════════
# Global settings propagation tests
# ═══════════════════════════════════════════════════════════════════


def test_force_flag_passed_when_checked(page):
    page._global_force.setChecked(True)
    # Patch _confirm_force to bypass QMessageBox
    with patch.object(page, "_confirm_force", return_value=True):
        worker = _click_button(page, "_stage_card")
    # Force is read at click time, but our mock captures it before _confirm_force patch
    # Re-test with inline approach
    FakeWorker.instances.clear()
    page._active_workers.clear()
    page._stage_card.reset()
    page._global_force.setChecked(True)
    with patch("src.gui.pages.data_pipeline_menu.PipelineStepWorker", FakeWorker), \
         patch("src.gui.pages.data_pipeline_menu.PipelineWorker", FakePipelineWorker), \
         patch.object(page, "_confirm_force", return_value=True):
        page._stage_card.run_button.click()
    worker = FakeWorker.instances[-1] if FakeWorker.instances else None
    assert worker is not None
    assert worker.options["force"] is True


def test_force_flag_not_passed_when_unchecked(page):
    page._global_force.setChecked(False)
    worker = _click_button(page, "_stage_card")
    assert worker.options["force"] is False


def test_workers_value_passed(page):
    page._workers.setValue(12)
    worker = _click_button(page, "_stage_card")
    assert worker.options["workers"] == 12


def test_strict_option_on_stage(page):
    page._stage_strict.setChecked(True)
    worker = _click_button(page, "_stage_card")
    assert worker.options["strict"] is True


def test_strict_option_off_by_default(page):
    worker = _click_button(page, "_stage_card")
    assert worker.options["strict"] is False


# ═══════════════════════════════════════════════════════════════════
# Duplicate run prevention
# ═══════════════════════════════════════════════════════════════════


def test_no_duplicate_worker_while_running(page):
    """Clicking Run while a step is already running should be a no-op."""
    # First click
    worker1 = _click_button(page, "_stage_card")
    assert worker1 is not None

    # Manually put the card back into _active_workers (simulating still running)
    FakeWorker.instances.clear()
    page._active_workers[page._stage_card] = worker1

    with patch("src.gui.pages.data_pipeline_menu.PipelineStepWorker", FakeWorker), \
         patch("src.gui.pages.data_pipeline_menu.PipelineWorker", FakePipelineWorker):
        page._stage_card.run_button.click()

    # Should NOT have created a new worker
    assert len(FakeWorker.instances) == 0


# ═══════════════════════════════════════════════════════════════════
# Force overwrite confirmation dialog
# ═══════════════════════════════════════════════════════════════════


def test_force_confirm_bypassed_when_unchecked(page):
    """When force is unchecked, _confirm_force returns True without dialog."""
    page._global_force.setChecked(False)
    assert page._confirm_force() is True


def test_force_confirm_shows_dialog_when_checked(page):
    """When force is checked, _confirm_force asks for confirmation."""
    page._global_force.setChecked(True)
    from PyQt6.QtWidgets import QMessageBox
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        assert page._confirm_force() is True
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        assert page._confirm_force() is False


# ═══════════════════════════════════════════════════════════════════
# Card reset
# ═══════════════════════════════════════════════════════════════════


def test_card_reset_returns_to_idle(page):
    card = page._stage_card
    card.set_running()
    assert card._state == "running"

    card.reset()
    assert card._state == "idle"
    assert card._run_btn.isEnabled()
    assert card._progress_widget.isHidden()
    assert card._results.isHidden()
