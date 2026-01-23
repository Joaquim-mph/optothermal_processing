"""CNP Evolution visualization screen (placeholder)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class CNPEvolutionScreen(WizardScreen):
    """CNP evolution visualization screen."""

    SCREEN_TITLE = "📈 CNP Evolution"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Histories > Metrics > CNP Evolution", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical():
            yield Label("CNP Evolution visualization - Coming soon!")
            yield Label("\nThis screen will show:")
            yield Label("  • Terminal plot (plotext): CNP voltage vs Time")
            yield Label("  • Statistics: Mean, Std Dev, Range, Trend")
            yield Label("  • Actions: Export Data, Create Full Plot, View Details")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
