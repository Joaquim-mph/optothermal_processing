"""Extract Derived Metrics Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label, Checkbox
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class ExtractMetricsScreen(WizardScreen):
    """Extract derived metrics screen."""

    SCREEN_TITLE = "✨ Extract Derived Metrics"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #config-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Process > Extract Metrics", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="config-form"):
            yield Label("Chip(s):", classes="section-label")
            yield Checkbox("All Chips", id="all-chips", value=True)
            yield Checkbox("Specific Chip(s)", id="specific-chips")

            yield Label("\nProcedures to Process:", classes="section-label")
            yield Checkbox("IVg (CNP extraction)", id="proc-ivg", value=True)
            yield Checkbox("It (Photoresponse, Relaxation)", id="proc-it", value=True)
            yield Checkbox("VVg", id="proc-vvg")
            yield Checkbox("LaserCalibration (Power matching)", id="proc-laser", value=True)

            yield Label("\nOptions:", classes="section-label")
            yield Checkbox("Force Re-extract", id="force-extract")
            yield Checkbox("Update Enriched Histories", id="update-enriched", value=True)

            yield Label("\n💡 Estimated: ~350 measurements to process", classes="muted")

        yield Button("▶️  Start Extraction", id="start-extract", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#start-extract", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-extract":
            self.app.notify("Extracting derived metrics...", severity="information")
            # TODO: Implement actual extraction
            self.app.notify("Extraction complete! 350 metrics extracted.", severity="information")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
