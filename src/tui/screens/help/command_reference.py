"""Command Reference Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, Label, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class CommandReferenceScreen(WizardScreen):
    """Command reference screen."""

    SCREEN_TITLE = "📖 Command Reference"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #reference-content {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
        height: 35;
    }

    .section-header {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .command-row {
        margin: 0 0 0 2;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Help > Command Reference", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with VerticalScroll(id="reference-content"):
            yield Label("💡 CLI COMMANDS (from terminal)\n", classes="section-header")
            yield Label("stage-all: Stage raw CSVs to Parquet", classes="command-row")
            yield Label("build-all-histories: Generate chip histories", classes="command-row")
            yield Label("derive-all-metrics: Extract derived metrics", classes="command-row")
            yield Label("enrich-history <chip>: Enrich specific chip", classes="command-row")
            yield Label("show-history <chip>: View chip experiments\n", classes="command-row")

            yield Label("plot-its <chip> --seq <nums>: Current vs time", classes="command-row")
            yield Label("plot-ivg <chip> --seq <nums>: Gate sweeps", classes="command-row")
            yield Label("plot-vvg <chip> --seq <nums>: Voltage sweeps", classes="command-row")
            yield Label("plot-vt <chip> --seq <nums>: Voltage vs time", classes="command-row")
            yield Label("plot-transconductance <chip> --seq <nums>: dI/dVg\n", classes="command-row")

            yield Label("batch-plot <config.yaml>: Multi-plot generation", classes="command-row")
            yield Label("validate-manifest: Check data integrity\n", classes="command-row")

            yield Label("📊 TUI NAVIGATION\n", classes="section-header")
            yield Label("Plots Hub:", classes="command-row")
            yield Label("  • New Plot: Start plot wizard", classes="command-row")
            yield Label("  • Batch Mode: Multi-plot from YAML", classes="command-row")
            yield Label("  • Recent Configs: Re-run saved configs", classes="command-row")
            yield Label("  • Presets: Quick plot templates", classes="command-row")
            yield Label("  • Browse Plots: View generated plots\n", classes="command-row")

            yield Label("Chip Histories Hub:", classes="command-row")
            yield Label("  • Standard History: Basic experiment list", classes="command-row")
            yield Label("  • Enriched History: With derived metrics", classes="command-row")
            yield Label("  • Metrics Explorer: CNP, photoresponse, τ", classes="command-row")
            yield Label("  • Experiment Browser: Advanced search", classes="command-row")
            yield Label("  • Export History: Save to CSV/JSON\n", classes="command-row")

            yield Label("Process New Data Hub:", classes="command-row")
            yield Label("  • Stage Raw Data: CSV → Parquet", classes="command-row")
            yield Label("  • Build Histories: From manifest", classes="command-row")
            yield Label("  • Extract Metrics: CNP, PR, τ", classes="command-row")
            yield Label("  • Full Pipeline: All steps", classes="command-row")

        yield Button("🏠 Return to Main Menu", id="home-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#home-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "home-btn":
            self.action_home()

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
