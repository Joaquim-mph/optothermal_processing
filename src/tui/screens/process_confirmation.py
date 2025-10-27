"""
Process Confirmation Dialog.

Simple confirmation dialog before running the full data processing pipeline.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.binding import Binding


class ProcessConfirmationScreen(Screen):
    """Confirmation dialog for processing new data."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "confirm", "Start", priority=True),
    ]

    CSS = """
    ProcessConfirmationScreen {
        align: center middle;
    }

    #dialog-container {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }

    #description {
        width: 100%;
        color: $text;
        margin-bottom: 2;
        padding: 1;
        background: $panel;
    }

    #command {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 2;
    }

    #warning {
        width: 100%;
        color: $warning;
        text-style: italic;
        margin-bottom: 2;
        content-align: center middle;
    }

    #status {
        width: 100%;
        content-align: center middle;
        color: $accent;
        text-style: bold;
        margin-bottom: 2;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        margin-top: 1;
    }

    .dialog-button {
        width: 1fr;
        margin: 0 1;
        min-height: 3;
    }

    .dialog-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }
    """

    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        """Create confirmation dialog widgets."""
        yield Header()

        with Container(id="dialog-container"):
            yield Static("Process New Data?", id="title")

            yield Static(
                "This will run the full processing pipeline:\n\n"
                "• Parse all metadata from raw CSV files\n"
                "• Rebuild chip histories\n"
                "• Process all chips\n"
                "• Overwrite existing metadata and history files",
                id="description"
            )

            yield Static("Running full pipeline directly", id="command")

            yield Static("⚠ This may take a while", id="warning")

            yield Static("", id="status")

            with Vertical(id="button-container"):
                yield Button("Cancel", id="cancel-button", variant="default", classes="dialog-button")
                yield Button("Start Processing", id="confirm-button", variant="primary", classes="dialog-button")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the confirm button on mount."""
        self.query_one("#confirm-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-button":
            self.action_cancel()
        elif event.button.id == "confirm-button":
            self.action_confirm()

    def action_cancel(self) -> None:
        """Cancel and return to main menu."""
        self.app.pop_screen()

    def action_confirm(self) -> None:
        """Start processing with loading screen."""
        from src.tui.screens.process_loading import ProcessLoadingScreen

        # Replace this screen with the loading screen
        self.app.pop_screen()
        self.app.push_screen(ProcessLoadingScreen())
