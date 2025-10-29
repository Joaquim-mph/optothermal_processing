"""
Plot Generation Error Screen.

Shows error details if plot generation fails.
"""

from __future__ import annotations
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Button
from textual.binding import Binding
from textual import events

from src.tui.screens.base import ErrorScreen


class PlotErrorScreen(ErrorScreen):
    """Error screen if plot generation fails."""

    SCREEN_TITLE = "Plot Generation Failed ✗"

    def __init__(self, error_type: str, error_msg: str, config: dict, error_details: str = ""):
        super().__init__()
        self.error_type = error_type
        self.error_msg = error_msg
        self.config = config
        self.error_details = error_details

    BINDINGS = ErrorScreen.BINDINGS + [
        Binding("enter", "main_menu", "Main Menu", priority=True),
    ]

    def compose_content(self) -> ComposeResult:
        """Compose error screen content."""
        yield Static("Error Type:", classes="section-title")
        yield Static(self.error_type, classes="error-text", markup=False)

        yield Static("Message:", classes="section-title")
        yield Static(self.error_msg, classes="error-text", markup=False)

        # Generate suggestion based on error
        suggestion = self._generate_suggestion()
        if suggestion:
            yield Static("Suggestion:", classes="section-title")
            yield Static(suggestion, classes="suggestion-text", markup=False)

        with Horizontal(id="button-container"):
            yield Button("View Details", id="details-button", variant="default", classes="nav-button")
            yield Button("Edit Config", id="edit-button", variant="default", classes="nav-button")
            yield Button("Main Menu", id="menu-button", variant="default", classes="nav-button")

    def on_mount(self) -> None:
        """Focus the edit config button."""
        self.query_one("#edit-button", Button).focus()

    def on_key(self, event: events.Key) -> None:
        """Handle arrow key navigation between buttons."""
        buttons = [
            self.query_one("#details-button", Button),
            self.query_one("#edit-button", Button),
            self.query_one("#menu-button", Button),
        ]

        focused_idx = next((i for i, b in enumerate(buttons) if b.has_focus), None)

        if focused_idx is not None:
            if event.key in ("left", "up"):
                new_idx = (focused_idx - 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()
            elif event.key in ("right", "down"):
                new_idx = (focused_idx + 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()

    def on_button_focus(self, event) -> None:
        """Add arrow indicator to focused button."""
        # Remove arrows from all buttons
        for button in self.query(".nav-button"):
            label = str(button.label)
            if label.startswith("→ "):
                button.label = label[2:]

        # Add arrow to focused button
        focused_button = event.button
        label = str(focused_button.label)
        if not label.startswith("→ "):
            focused_button.label = f"→ {label}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "details-button":
            self.action_view_details()
        elif event.button.id == "edit-button":
            self.action_edit_config()
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

    def action_edit_config(self) -> None:
        """Go back to edit configuration."""
        # Pop this error screen to go back to preview
        self.app.pop_screen()

    def action_main_menu(self) -> None:
        """Return to main menu using router."""
        self.app.router.return_to_main_menu()

    def _generate_suggestion(self) -> Optional[str]:
        """Generate helpful suggestion based on error."""
        error_lower = self.error_msg.lower()

        if "filter" in error_lower:
            return "Try adjusting or removing filters to include more experiments."
        elif "not found" in error_lower or "does not exist" in error_lower:
            return "Check that all required files exist in the specified directories."
        elif "empty" in error_lower or "no data" in error_lower:
            return "Verify that the selected experiments contain valid measurement data."
        else:
            return "Check your configuration and try again."
