"""Relaxation Times analysis screen (placeholder)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class RelaxationTimesScreen(WizardScreen):
    """Relaxation times analysis screen."""

    SCREEN_TITLE = "⏱️  Relaxation Times"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Histories > Metrics > Relaxation Times", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical():
            yield Label("Relaxation Times Analysis - Coming soon!")
            yield Label("\nThis screen will show:")
            yield Label("  • Terminal plot: τ vs Experiment")
            yield Label("  • Fit quality indicators (Good, Poor, Failed)")
            yield Label("  • Statistics: Mean τ, Mean β, R² range")
            yield Label("  • Actions: View Poor Fits, Export Data, Refit Selected")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
