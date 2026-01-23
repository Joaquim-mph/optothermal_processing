"""
Experiment Browser Screen.

Advanced search and filter for experiments across multiple chips.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Label, Checkbox
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class ExperimentBrowserScreen(WizardScreen):
    """Advanced experiment browser and search screen."""

    SCREEN_TITLE = "🔍 Experiment Browser"
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

    #filters-container {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
        height: 25;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .checkbox-row {
        margin: 0 0 0 2;
    }

    .action-button {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header."""
        yield Static("Main Menu > Histories > Experiment Browser", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose experiment browser."""
        with Vertical(id="filters-container"):
            yield Label("🔍 ADVANCED SEARCH", classes="section-label")

            yield Label("\nChip(s):", classes="section-label")
            yield Checkbox("Alisson67", id="chip-67", classes="checkbox-row")
            yield Checkbox("Encap81", id="chip-81", classes="checkbox-row")
            yield Checkbox("All Chips", id="chip-all", classes="checkbox-row")

            yield Label("\nProcedure(s):", classes="section-label")
            yield Checkbox("IVg", id="proc-ivg", classes="checkbox-row")
            yield Checkbox("It", id="proc-it", classes="checkbox-row")
            yield Checkbox("VVg", id="proc-vvg", classes="checkbox-row")
            yield Checkbox("Vt", id="proc-vt", classes="checkbox-row")

            yield Label("\nDerived Metrics:", classes="section-label")
            yield Checkbox("Has CNP", id="metric-cnp", classes="checkbox-row")
            yield Checkbox("Has Photoresponse", id="metric-pr", classes="checkbox-row")

        with Vertical():
            yield Button(
                "🔍 Search",
                id="search",
                variant="primary",
                classes="action-button"
            )
            yield Button(
                "🧹 Clear Filters",
                id="clear",
                variant="default",
                classes="action-button"
            )

    def on_mount(self) -> None:
        """Focus search button."""
        self.query_one("#search", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "search":
            self._execute_search()
        elif event.button.id == "clear":
            self._clear_filters()

    def _execute_search(self) -> None:
        """Execute advanced search."""
        self.app.notify(
            "Advanced search execution - Coming soon!",
            severity="information"
        )
        # TODO: Navigate to search results screen

    def _clear_filters(self) -> None:
        """Clear all filter checkboxes."""
        for checkbox in self.query(Checkbox):
            checkbox.value = False

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
