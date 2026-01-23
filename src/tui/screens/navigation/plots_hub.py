"""
Plots Hub Screen.

Central hub for all plotting activities:
- New Plot (existing wizard)
- Batch Mode
- Recent Configurations
- Plot Presets
- Browse Generated Plots
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class PlotsHubScreen(WizardScreen):
    """Plots hub menu screen."""

    SCREEN_TITLE = "📊 Plots"
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
        yield Static("Main Menu > Plots", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose plots hub menu."""
        with Vertical():
            yield Button("🆕 New Plot", id="new-plot", variant="primary", classes="hub-button")
            yield Button("📦 Batch Mode", id="batch", variant="default", classes="hub-button")
            yield Button("🔄 Recent Configurations", id="recent", variant="default", classes="hub-button")
            yield Button("🎨 Plot Presets", id="presets", variant="default", classes="hub-button")
            yield Button("🖼️  Browse Generated Plots", id="browse", variant="default", classes="hub-button")

    def on_mount(self) -> None:
        """Focus first button."""
        self.query_one("#new-plot", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "new-plot":
            # Start existing wizard
            self.app.router.go_to_chip_selector(mode="plot")
        elif button_id == "batch":
            # Navigate to Batch Mode hub
            self.app.router.go_to_batch_mode_hub()
        elif button_id == "recent":
            # Navigate to Recent Configurations
            self.app.router.go_to_recent_configs_list()
        elif button_id == "presets":
            # Navigate to Plot Presets
            self.app.router.go_to_preset_selector()
        elif button_id == "browse":
            # Navigate to Browse Plots
            self.app.router.go_to_plot_browser()

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
