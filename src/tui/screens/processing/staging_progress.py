"""Staging Progress Screen (placeholder - uses background worker)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label, ProgressBar, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class StagingProgressScreen(WizardScreen):
    """Staging progress screen."""

    SCREEN_TITLE = "⏳ Staging Progress"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("c", "cancel", "Cancel", show=True)]

    CSS = WizardScreen.CSS + """
    #progress-container {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
        height: 15;
    }
    """

    def __init__(self, raw_path: str, force_overwrite: bool, strict_mode: bool, workers: int):
        super().__init__()
        self.raw_path = raw_path
        self.force_overwrite = force_overwrite
        self.strict_mode = strict_mode
        self.workers = workers

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Process > Stage > Progress", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="progress-container"):
            yield Label(f"Staging from: {self.raw_path}")
            yield Label(f"Workers: {self.workers} | Force: {self.force_overwrite} | Strict: {self.strict_mode}\n")
            yield ProgressBar(id="progress-bar", total=100)
            yield Label("\nCurrent: Initializing...", id="current-file")
            yield Label("✅ Processed: 0 | ⚠️  Warnings: 0 | ❌ Errors: 0", id="stats")

        yield Button("🛑 Cancel", id="cancel-btn", variant="error")

    def action_cancel(self) -> None:
        self.app.notify("Staging cancelled", severity="warning")
        self.action_back()

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
