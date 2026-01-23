"""
Export History Screen.

Export chip history data to various formats (CSV, JSON, Parquet).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Label, Select, Checkbox, Input
from textual.binding import Binding

from src.tui.screens.base import WizardScreen

if TYPE_CHECKING:
    from textual.widgets import Button as ButtonType


class ExportHistoryScreen(WizardScreen):
    """Export chip history screen."""

    SCREEN_TITLE = "📤 Export History"
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

    #export-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .form-row {
        height: 3;
        margin: 0 0 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .action-button {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header."""
        yield Static("Main Menu > Histories > Export History", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose export form."""
        with Vertical(id="export-form"):
            yield Label("Select Chip(s):", classes="section-label")
            with Horizontal(classes="form-row"):
                yield Select(
                    options=[
                        ("Alisson67", "67"),
                        ("Encap81", "81"),
                        ("All Chips", "all"),
                    ],
                    value="67",
                    id="chip-select"
                )

            yield Label("\nExport Type:", classes="section-label")
            with Horizontal(classes="form-row"):
                yield Select(
                    options=[
                        ("Standard History", "standard"),
                        ("Enriched History", "enriched"),
                        ("Both", "both"),
                    ],
                    value="standard",
                    id="type-select"
                )

            yield Label("\nOutput Format:", classes="section-label")
            with Horizontal(classes="form-row"):
                yield Select(
                    options=[
                        ("CSV", "csv"),
                        ("JSON", "json"),
                        ("Parquet", "parquet"),
                    ],
                    value="csv",
                    id="format-select"
                )

            yield Label("\nOutput Path:", classes="section-label")
            with Horizontal(classes="form-row"):
                yield Input(
                    value="exports/",
                    placeholder="Output directory...",
                    id="path-input"
                )

            yield Label("")
            yield Checkbox("Export all experiments", id="export-all", value=True)

        with Vertical():
            yield Button(
                "📤 Export",
                id="export",
                variant="primary",
                classes="action-button"
            )

    def on_mount(self) -> None:
        """Focus export button."""
        self.query_one("#export", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "export":
            self._execute_export()

    def _execute_export(self) -> None:
        """Execute history export."""
        chip = self.query_one("#chip-select", Select).value
        export_type = self.query_one("#type-select", Select).value
        format_type = self.query_one("#format-select", Select).value
        output_path = self.query_one("#path-input", Input).value

        self.app.notify(
            f"Exporting {export_type} history for chip {chip} as {format_type}...",
            severity="information"
        )

        # TODO: Implement actual export logic
        self.app.notify(
            f"Export feature - Coming soon! Would export to: {output_path}",
            severity="information"
        )

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
