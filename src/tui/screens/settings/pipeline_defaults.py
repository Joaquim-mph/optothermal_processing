"""Pipeline Defaults Configuration Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label, Select, Checkbox
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class PipelineDefaultsScreen(WizardScreen):
    """Pipeline defaults configuration screen."""

    SCREEN_TITLE = "⚙️  Pipeline Defaults"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #defaults-form {
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
        yield Static("Main Menu > Settings > Pipeline Defaults", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="defaults-form"):
            yield Label("Staging:", classes="section-label")
            yield Label("  Parallel Workers:")
            yield Select(
                options=[("2", "2"), ("4", "4"), ("6", "6"), ("8", "8"), ("12", "12")],
                value="6",
                id="workers",
                classes="form-row"
            )
            yield Checkbox("Force Overwrite by default", id="force-overwrite")
            yield Checkbox("Strict Mode by default", id="strict-mode")

            yield Label("\nMetrics Extraction:", classes="section-label")
            yield Checkbox("Auto-update enriched histories", id="auto-enrich", value=True)
            yield Checkbox("Extract CNP (IVg)", id="extract-cnp", value=True)
            yield Checkbox("Extract Photoresponse (It)", id="extract-pr", value=True)
            yield Checkbox("Extract Relaxation Times (It)", id="extract-tau", value=True)

            yield Label("\nPlotting:", classes="section-label")
            yield Label("  Default Legend By:")
            yield Select(
                options=[
                    ("Wavelength", "wavelength"),
                    ("Gate Voltage", "vg_v"),
                    ("Power", "irradiated_power"),
                ],
                value="wavelength",
                id="legend-by",
                classes="form-row"
            )

        yield Button("💾 Save Defaults", id="save-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#save-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.app.notify("Pipeline defaults saved!", severity="information")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
