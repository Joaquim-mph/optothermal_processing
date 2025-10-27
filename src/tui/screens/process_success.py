"""
Data Processing Success Screen.

Shows results after successful data processing.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.binding import Binding
from textual import events


class ProcessSuccessScreen(Screen):
    """Success screen after data processing."""

    def __init__(
        self,
        elapsed: float,
        files_processed: int,
        experiments: int,
        histories: int,
        total_chips: int,
    ):
        super().__init__()
        self.elapsed = elapsed
        self.files_processed = files_processed
        self.experiments = experiments
        self.histories = histories
        self.total_chips = total_chips

    BINDINGS = [
        Binding("escape", "main_menu", "Main Menu", priority=True),
        Binding("enter", "main_menu", "Main Menu", priority=True),
    ]

    CSS = """
    ProcessSuccessScreen {
        align: center middle;
    }

    #main-container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $success;
        padding: 2 4;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $success;
        margin-bottom: 2;
    }

    .info-row {
        color: $text;
        margin-left: 2;
        margin-bottom: 0;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
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
        """Create success screen widgets."""
        yield Header()

        with Container(id="main-container"):
            yield Static("Processing Complete! ✓", id="title")

            yield Static("Results:", classes="section-title")
            yield Static(f"Files processed: {self.files_processed}", classes="info-row")
            yield Static(f"Experiments found: {self.experiments}", classes="info-row")
            yield Static(f"Chip histories created: {self.histories}/{self.total_chips}", classes="info-row")
            yield Static(f"Processing time: {self.elapsed:.1f}s", classes="info-row")

            yield Static("", classes="info-row")
            yield Static("Output directories:", classes="section-title")
            yield Static("• metadata/ — Experiment metadata CSV files", classes="info-row")
            yield Static("• chip_histories/ — Chip history files", classes="info-row")

            yield Static("", classes="info-row")
            yield Static("You can now use the plotting tools to visualize your data.", classes="info-row")

            with Horizontal(id="button-container"):
                yield Button("Main Menu", id="menu-button", variant="primary", classes="nav-button")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the main menu button."""
        self.query_one("#menu-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "menu-button":
            self.action_main_menu()

    def action_main_menu(self) -> None:
        """Return to main menu."""
        # Pop all screens until we're back at the main menu (keep base + MainMenuScreen)
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()
