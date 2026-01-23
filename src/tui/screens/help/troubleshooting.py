"""Troubleshooting Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, Label, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class TroubleshootingScreen(WizardScreen):
    """Troubleshooting guide screen."""

    SCREEN_TITLE = "🔧 Troubleshooting"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #troubleshooting-content {
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

    .problem-row {
        margin: 0 0 0 2;
    }

    .solution-row {
        margin: 0 0 0 4;
        color: $success;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Help > Troubleshooting", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with VerticalScroll(id="troubleshooting-content"):
            yield Label("❓ COMMON ISSUES\n", classes="section-header")

            yield Label("❌ \"History not found for chip X\"", classes="problem-row")
            yield Label("✅ Run: build-all-histories or Process > Build Histories\n", classes="solution-row")

            yield Label("❌ \"No enriched history found\"", classes="problem-row")
            yield Label("✅ Run: enrich-history <chip> or Process > Extract Metrics\n", classes="solution-row")

            yield Label("❌ \"File not found: manifest.parquet\"", classes="problem-row")
            yield Label("✅ Run: stage-all or Process > Stage Raw Data\n", classes="solution-row")

            yield Label("❌ \"Validation errors during staging\"", classes="problem-row")
            yield Label("✅ Check CSV headers match procedures.yml", classes="solution-row")
            yield Label("✅ Use --strict to see detailed errors\n", classes="solution-row")

            yield Label("❌ \"No experiments match filters\"", classes="problem-row")
            yield Label("✅ Check procedure/light/date filters", classes="solution-row")
            yield Label("✅ Try 'All' to see available experiments\n", classes="solution-row")

            yield Label("❌ Plots are empty or missing data", classes="problem-row")
            yield Label("✅ Check parquet files exist in data/02_stage/", classes="solution-row")
            yield Label("✅ Run validate-manifest to check integrity\n", classes="solution-row")

            yield Label("🗂️  DATA LOCATION\n", classes="section-header")
            yield Label("• Raw CSVs:           data/01_raw/", classes="problem-row")
            yield Label("• Staged Parquet:     data/02_stage/raw_measurements/", classes="problem-row")
            yield Label("• Manifest:           data/02_stage/_manifest/manifest.parquet", classes="problem-row")
            yield Label("• Chip Histories:     data/02_stage/chip_histories/", classes="problem-row")
            yield Label("• Enriched Histories: data/03_derived/chip_histories_enriched/", classes="problem-row")
            yield Label("• Metrics:            data/03_derived/_metrics/metrics.parquet", classes="problem-row")
            yield Label("• Generated Plots:    figs/\n", classes="problem-row")

            yield Label("🔍 DEBUGGING\n", classes="section-header")
            yield Label("• Check logs:        logs/tui.log", classes="problem-row")
            yield Label("• Validate manifest: Process > Validate Manifest", classes="problem-row")
            yield Label("• Check status:      Process > Pipeline Status", classes="problem-row")

        yield Button("🏠 Return to Main Menu", id="home-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#home-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "home-btn":
            self.action_home()

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
