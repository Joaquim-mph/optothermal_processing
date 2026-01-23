"""
Metrics Explorer Hub Screen.

Central hub for exploring derived metrics with visualizations.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class MetricsExplorerHubScreen(WizardScreen):
    """Metrics explorer hub menu screen."""

    SCREEN_TITLE = "🔬 Metrics Explorer"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("home", "home", "Home", show=True),
    ]

    CSS = WizardScreen.CSS + """
    #breadcrumb {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    .hub-button {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header."""
        yield Static("Main Menu > Histories > Metrics Explorer", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose metrics explorer hub."""
        with Vertical():
            yield Button(
                "📈 CNP Evolution (Dirac point over time)",
                id="cnp",
                variant="default",
                classes="hub-button"
            )
            yield Button(
                "💡 Photoresponse Analysis",
                id="photoresponse",
                variant="default",
                classes="hub-button"
            )
            yield Button(
                "⏱️  Relaxation Times",
                id="relaxation",
                variant="default",
                classes="hub-button"
            )

    def on_mount(self) -> None:
        """Focus first button."""
        self.query_one("#cnp", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "cnp":
            self.app.router.go_to_cnp_evolution()
        elif button_id == "photoresponse":
            self.app.router.go_to_photoresponse_analysis()
        elif button_id == "relaxation":
            self.app.router.go_to_relaxation_times()

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
