"""Data Paths Configuration Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label, Input
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class DataPathsScreen(WizardScreen):
    """Data paths configuration screen."""

    SCREEN_TITLE = "📁 Data Paths"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #paths-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .path-row {
        margin: 0 0 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Settings > Data Paths", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="paths-form"):
            yield Label("Raw Data:", classes="section-label")
            yield Input(value="data/01_raw", id="raw-path", classes="path-row")

            yield Label("\nStaged Data:", classes="section-label")
            yield Input(value="data/02_stage", id="stage-path", classes="path-row")

            yield Label("\nDerived Metrics:", classes="section-label")
            yield Input(value="data/03_derived", id="derived-path", classes="path-row")

            yield Label("\nOutput (Plots):", classes="section-label")
            yield Input(value="figs", id="output-path", classes="path-row")

            yield Label("\nConfiguration:", classes="section-label")
            yield Input(value="config", id="config-path", classes="path-row")

            yield Label("\n💡 Changes require restart", classes="muted")

        yield Button("💾 Save Paths", id="save-btn", variant="primary")
        yield Button("🔄 Reset to Defaults", id="reset-btn", variant="default")

    def on_mount(self) -> None:
        self.query_one("#save-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.app.notify("Data paths saved!", severity="information")
        elif event.button.id == "reset-btn":
            self.app.notify("Reset to defaults", severity="information")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
