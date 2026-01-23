"""Search Results screen (placeholder)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class SearchResultsScreen(WizardScreen):
    """Search results display screen."""

    SCREEN_TITLE = "📋 Search Results"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Histories > Experiment Browser > Results", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical():
            yield Label("Search Results - Coming soon!")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
