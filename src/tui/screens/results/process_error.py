"""
Data Processing Error Screen.

Shows error details if processing fails.
"""

from __future__ import annotations
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import ErrorScreen


class ProcessErrorScreen(ErrorScreen):
    """Error screen if data processing fails."""

    SCREEN_TITLE = "Processing Failed ✗"

    def __init__(self, error_type: str, error_msg: str, error_details: str = ""):
        super().__init__()
        self.error_type = error_type
        self.error_msg = error_msg
        self.error_details = error_details

    BINDINGS = ErrorScreen.BINDINGS + []

    def compose_content(self) -> ComposeResult:
        """Compose error screen content."""
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
        """Return to main menu using router."""
        self.app.router.return_to_main_menu()

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
