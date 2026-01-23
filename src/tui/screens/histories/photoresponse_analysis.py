"""Photoresponse Analysis screen (placeholder)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class PhotoresponseAnalysisScreen(WizardScreen):
    """Photoresponse analysis screen."""

    SCREEN_TITLE = "💡 Photoresponse Analysis"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Histories > Metrics > Photoresponse", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical():
            yield Label("Photoresponse Analysis - Coming soon!")
            yield Label("\nThis screen will show:")
            yield Label("  • Filters: Wavelength, Gate Voltage, Date Range")
            yield Label("  • Terminal plot: ΔI vs Time")
            yield Label("  • Statistics: Mean, Max, Min photoresponse")
            yield Label("  • Actions: Compare Wavelengths, Export Data")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
