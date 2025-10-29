"""
Data Processing Success Screen.

Shows results after successful data processing.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import SuccessScreen


class ProcessSuccessScreen(SuccessScreen):
    """Success screen after data processing."""

    SCREEN_TITLE = "Processing Complete! ✓"

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

    BINDINGS = SuccessScreen.BINDINGS + [
        Binding("enter", "main_menu", "Main Menu", priority=True),
    ]

    def compose_content(self) -> ComposeResult:
        """Compose success screen content."""
        yield Static("Pipeline Results:", classes="section-title")
        yield Static(f"CSV files staged: {self.files_processed}", classes="info-row")
        yield Static(f"Experiments in manifest: {self.experiments}", classes="info-row")
        yield Static(f"Chip histories generated: {self.histories}/{self.total_chips} chips", classes="info-row")
        yield Static(f"Total processing time: {self.elapsed:.1f}s", classes="info-row")

        yield Static("", classes="info-row")
        yield Static("Output Locations:", classes="section-title")
        yield Static("• data/02_stage/raw_measurements/ — Staged Parquet files", classes="info-row")
        yield Static("• data/02_stage/raw_measurements/_manifest/ — Manifest & events", classes="info-row")
        yield Static("• data/02_stage/chip_histories/ — Chip history Parquet files", classes="info-row")

        yield Static("", classes="info-row")
        yield Static("Next Steps:", classes="section-title")
        yield Static("• Use 'New Plot' to generate ITS, IVg, or transconductance plots", classes="info-row")
        yield Static("• Use 'View Chip Histories' to browse experiment timelines", classes="info-row")

        with Horizontal(id="button-container"):
            yield Button("Main Menu", id="menu-button", variant="primary", classes="nav-button")

    def on_mount(self) -> None:
        """Focus the main menu button."""
        self.query_one("#menu-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "menu-button":
            self.action_main_menu()

    def action_main_menu(self) -> None:
        """Return to main menu using router."""
        self.app.router.return_to_main_menu()
