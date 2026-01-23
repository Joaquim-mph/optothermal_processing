"""
Help Hub Screen.

Central hub for documentation and support:
- Keyboard Shortcuts
- Workflow Guide
- View Logs
- Documentation
- About
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class HelpHubScreen(WizardScreen):
    """Help hub menu screen."""

    SCREEN_TITLE = "❓ Help"
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
        yield Static("Main Menu > Help", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose help hub menu."""
        with Vertical():
            yield Button("🚀 Quick Start Guide", id="quick-start", variant="default", classes="hub-button")
            yield Button("📖 Command Reference", id="commands", variant="default", classes="hub-button")
            yield Button("🔧 Troubleshooting", id="troubleshooting", variant="default", classes="hub-button")
            yield Button("ℹ️  About", id="about", variant="default", classes="hub-button")

    def on_mount(self) -> None:
        """Focus first button."""
        self.query_one("#quick-start", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "quick-start":
            self.app.router.go_to_quick_start()
        elif button_id == "commands":
            self.app.router.go_to_command_reference()
        elif button_id == "troubleshooting":
            self.app.router.go_to_troubleshooting()
        elif button_id == "about":
            self.app.router.go_to_about()

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
