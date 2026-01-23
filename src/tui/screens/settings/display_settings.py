"""Display Settings Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label, Select, Checkbox
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class DisplaySettingsScreen(WizardScreen):
    """Display settings screen."""

    SCREEN_TITLE = "🖥️  Display Settings"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #display-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .form-row {
        height: 3;
        margin: 0 0 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Settings > Display", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="display-form"):
            yield Label("Tables:", classes="section-label")
            yield Label("  Rows per page:")
            yield Select(
                options=[("25", "25"), ("50", "50"), ("100", "100"), ("All", "-1")],
                value="100",
                id="table-rows",
                classes="form-row"
            )
            yield Checkbox("Show row numbers", id="show-row-numbers", value=True)
            yield Checkbox("Zebra striping", id="zebra-striping", value=True)

            yield Label("\nProgress Bars:", classes="section-label")
            yield Checkbox("Show ETA", id="show-eta", value=True)
            yield Checkbox("Show percentage", id="show-percentage", value=True)

            yield Label("\nTerminal Plots (plotext):", classes="section-label")
            yield Checkbox("Enable terminal plots", id="enable-plotext", value=True)
            yield Label("  Plot width:")
            yield Select(
                options=[("80 chars", "80"), ("100 chars", "100"), ("120 chars", "120")],
                value="100",
                id="plot-width",
                classes="form-row"
            )

        yield Button("💾 Save Display Settings", id="save-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#save-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.app.notify("Display settings saved!", severity="information")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
