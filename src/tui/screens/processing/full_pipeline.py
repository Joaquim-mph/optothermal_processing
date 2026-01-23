"""Full Pipeline Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label, Select, Checkbox
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class FullPipelineScreen(WizardScreen):
    """Full pipeline orchestration screen."""

    SCREEN_TITLE = "🔄 Full Pipeline"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #pipeline-steps {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .step-label {
        margin: 0 0 0 2;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Process > Full Pipeline", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="pipeline-steps"):
            yield Label("Pipeline Steps:", classes="section-label")
            yield Label("1️⃣  Stage Raw Data", classes="step-label")
            yield Label("2️⃣  Build Chip Histories", classes="step-label")
            yield Label("3️⃣  Extract Derived Metrics", classes="step-label")
            yield Label("4️⃣  Validate Manifest\n", classes="step-label")

            yield Label("Configuration:", classes="section-label")
            yield Checkbox("Strict Mode", id="strict")
            yield Checkbox("Force Overwrite", id="force")

            yield Label("\nWorkers:", classes="section-label")
            yield Select(
                options=[("2", "2"), ("4", "4"), ("6", "6"), ("8", "8")],
                value="6",
                id="workers"
            )

            yield Label("\n💡 Estimated time: ~3-5 minutes", classes="muted")

        yield Button("▶️  Start Pipeline", id="start-pipeline", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#start-pipeline", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-pipeline":
            self.app.notify("Starting full pipeline...", severity="information")
            # TODO: Implement pipeline orchestration
            self.app.notify("Pipeline would run all 4 steps sequentially", severity="information")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
