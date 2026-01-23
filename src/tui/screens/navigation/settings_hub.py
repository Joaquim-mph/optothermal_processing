"""
Settings Hub Screen.

Central hub for application configuration:
- Theme
- Output Paths
- Default Parameters
- Plugin Configuration
- Export/Import Settings
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class SettingsHubScreen(WizardScreen):
    """Settings hub menu screen."""

    SCREEN_TITLE = "🛠️  Settings"
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
        yield Static("Main Menu > Settings", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose settings hub menu."""
        with Vertical():
            yield Button("🎨 TUI Preferences", id="preferences", variant="default", classes="hub-button")
            yield Button("📁 Data Paths", id="paths", variant="default", classes="hub-button")
            yield Button("⚙️  Pipeline Defaults", id="defaults", variant="default", classes="hub-button")
            yield Button("🖥️  Display Settings", id="display", variant="default", classes="hub-button")

    def on_mount(self) -> None:
        """Focus first button."""
        self.query_one("#preferences", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "preferences":
            self.app.router.go_to_tui_preferences()
        elif button_id == "paths":
            self.app.router.go_to_data_paths()
        elif button_id == "defaults":
            self.app.router.go_to_pipeline_defaults()
        elif button_id == "display":
            self.app.router.go_to_display_settings()

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
