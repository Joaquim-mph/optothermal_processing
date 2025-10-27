"""
Data Processing Error Screen.

Shows error details if processing fails.
"""

from __future__ import annotations
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.binding import Binding


class ProcessErrorScreen(Screen):
    """Error screen if data processing fails."""

    def __init__(self, error_type: str, error_msg: str, error_details: str = ""):
        super().__init__()
        self.error_type = error_type
        self.error_msg = error_msg
        self.error_details = error_details

    BINDINGS = [
        Binding("escape", "main_menu", "Main Menu", priority=True),
    ]

    CSS = """
    ProcessErrorScreen {
        align: center middle;
    }

    #main-container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $error;
        padding: 2 4;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $error;
        margin-bottom: 2;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }

    .error-text {
        color: $text;
        margin-left: 2;
        margin-bottom: 1;
    }

    .suggestion-text {
        color: $warning;
        margin-left: 2;
        margin-bottom: 1;
        text-style: italic;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        margin-top: 2;
    }

    .nav-button {
        width: 1fr;
        margin: 0 1;
    }

    .nav-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        """Create error screen widgets."""
        yield Header()

        with Container(id="main-container"):
            yield Static("Processing Failed ✗", id="title")

            yield Static("Error Type:", classes="section-title")
            yield Static(self.error_type, classes="error-text")

            yield Static("Message:", classes="section-title")
            yield Static(self.error_msg, classes="error-text")

            # Generate suggestion based on error
            suggestion = self._generate_suggestion()
            if suggestion:
                yield Static("Suggestion:", classes="section-title")
                yield Static(suggestion, classes="suggestion-text")

            with Horizontal(id="button-container"):
                yield Button("View Details", id="details-button", variant="default", classes="nav-button")
                yield Button("Main Menu", id="menu-button", variant="default", classes="nav-button")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the main menu button."""
        self.query_one("#menu-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "details-button":
            self.action_view_details()
        elif event.button.id == "menu-button":
            self.action_main_menu()

    def action_view_details(self) -> None:
        """View error details."""
        if self.error_details:
            # Show full traceback in a notification
            self.app.notify(
                f"Full traceback:\n{self.error_details}",
                severity="error",
                timeout=10
            )
        else:
            self.app.notify("No additional error details available", severity="information")

    def action_main_menu(self) -> None:
        """Return to main menu."""
        # Pop all screens until we're back at the main menu (keep base + MainMenuScreen)
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()

    def _generate_suggestion(self) -> Optional[str]:
        """Generate helpful suggestion based on error."""
        error_lower = self.error_msg.lower()

        if "no data folders found" in error_lower:
            return "Make sure raw_data/ directory exists and contains subdirectories with CSV files."
        elif "no chips found" in error_lower:
            return "Check that your CSV files have valid 'Chip number' metadata."
        elif "not found" in error_lower or "does not exist" in error_lower:
            return "Verify that all required directories and files exist."
        elif "permission" in error_lower:
            return "Check file permissions on metadata/ and chip_histories/ directories."
        else:
            return "Check the error details and try again. You may need to run this from the command line for more information."
