"""
Chip Histories Hub Screen.

Central hub for data exploration and analysis:
- View Standard History
- View Enriched History
- Metrics Explorer
- Experiment Browser
- Data Preview (plotext)
- Export History
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class HistoriesHubScreen(WizardScreen):
    """Chip Histories hub menu screen."""

    SCREEN_TITLE = "📂 Chip Histories"
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

    .hub-button:focus {
        background: $primary;
        border: tall $accent;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with breadcrumb and title."""
        yield Static("Main Menu > Chip Histories", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose histories hub menu."""
        with Vertical():
            yield Button("📊 View Standard History", id="standard", variant="default", classes="hub-button")
            yield Button("✨ View Enriched History", id="enriched", variant="default", classes="hub-button")
            yield Button("🔬 Metrics Explorer", id="metrics", variant="default", classes="hub-button")
            yield Button("🔍 Experiment Browser", id="browser", variant="default", classes="hub-button")
            yield Button("👁️  Data Preview", id="preview", variant="default", classes="hub-button")
            yield Button("📤 Export History", id="export", variant="default", classes="hub-button")

    def on_mount(self) -> None:
        """Focus first button."""
        self.query_one("#standard", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "standard":
            self.app.router.go_to_standard_history_browser()
        elif button_id == "enriched":
            self.app.router.go_to_enriched_history_browser()
        elif button_id == "metrics":
            self.app.router.go_to_metrics_explorer_hub()
        elif button_id == "browser":
            self.app.router.go_to_experiment_browser()
        elif button_id == "preview":
            self.app.router.go_to_data_preview()
        elif button_id == "export":
            self.app.router.go_to_export_history()

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
