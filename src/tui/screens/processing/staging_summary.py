"""Staging Summary Screen (placeholder)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class StagingSummaryScreen(WizardScreen):
    """Staging summary screen."""

    SCREEN_TITLE = "✅ Staging Complete"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Process > Stage > Summary", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical():
            yield Label("🎉 Staging completed successfully!\n")
            yield Label("✅ Success: 118 files")
            yield Label("⚠️  Warnings: 5 files")
            yield Label("❌ Errors: 2 files")
            yield Label("\nTotal time: 1m 41s")
            yield Label("Manifest updated: 118 new entries\n")

        yield Button("🏠 Return to Main Menu", id="home-btn", variant="primary")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
